from decimal import Decimal

from django.db import models


class Dimension(models.TextChoices):
    """量纲：单位相容性在量纲层面判断，绝不允许跨量纲折算。"""

    ENERGY = "energy", "能量"
    MASS = "mass", "质量"
    VOLUME = "volume", "体积"
    COUNT = "count", "件数"


class ActivityType(models.TextChoices):
    ELECTRICITY = "electricity", "电力"
    FUEL = "fuel", "燃料"
    AUXILIARY = "auxiliary", "辅料"


class Region(models.Model):
    code = models.CharField("地区编码", max_length=32, unique=True)
    name = models.CharField("地区名称", max_length=64)

    class Meta:
        verbose_name = "适用地区"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.code} {self.name}"


class Unit(models.Model):
    """计量单位。factor_to_base 表示 1 本单位 = factor_to_base 个基准单位。

    例如基准单位为 kWh 时，MWh 的 factor_to_base = 1000。
    """

    code = models.CharField("单位编码", max_length=16, unique=True)
    name = models.CharField("单位名称", max_length=32)
    dimension = models.CharField("量纲", max_length=16, choices=Dimension.choices)
    factor_to_base = models.DecimalField(
        "换算到基准单位的倍数", max_digits=30, decimal_places=10
    )

    class Meta:
        verbose_name = "计量单位"
        verbose_name_plural = verbose_name
        ordering = ["dimension", "code"]

    def __str__(self):
        return self.code


class EmissionFactor(models.Model):
    """排放因子版本。同一 code 可有多个 version，用 valid_from/valid_to 界定适用期。

    因子含义：每 1 个 denominator_unit（denominator_unit 量纲内的基准单位）
    活动量产生 value kgCO2e（按含碳率/氧化率修正因子处理后的值）。
    """

    code = models.CharField("因子编码", max_length=64, db_index=True)
    version = models.CharField("版本", max_length=16)
    name = models.CharField("因子名称", max_length=128)
    activity_type = models.CharField(
        "适用活动类型", max_length=16, choices=ActivityType.choices
    )
    region = models.ForeignKey(
        Region, verbose_name="适用地区", on_delete=models.PROTECT
    )
    denominator_dimension = models.CharField(
        "分母量纲", max_length=16, choices=Dimension.choices
    )
    value = models.DecimalField("因子值 kgCO2e/基准单位", max_digits=20, decimal_places=8)
    valid_from = models.DateField("生效日")
    valid_to = models.DateField("失效日", null=True, blank=True)
    source = models.CharField("来源", max_length=256)
    is_fictional = models.BooleanField("虚构示例因子", default=False)
    notes = models.TextField("用途与免责声明", blank=True)

    class Meta:
        verbose_name = "排放因子"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["code", "version"], name="uq_factor_code_version"
            )
        ]
        ordering = ["code", "-valid_from", "-version"]

    def __str__(self):
        return f"{self.code} v{self.version}"

    def status_on(self, as_of):
        if as_of < self.valid_from:
            return "future"
        if self.valid_to is not None and as_of > self.valid_to:
            return "expired"
        return "valid"


class Scenario(models.Model):
    """生产方案（情景）。确认报告后情景冻结，调整数据请复制为新情景。"""

    name = models.CharField("方案名称", max_length=128)
    product = models.CharField("产品名称", max_length=128)
    functional_unit = models.CharField("功能单位", max_length=64, default="1 件产品")
    boundary_note = models.CharField(
        "系统边界", max_length=256, default="门到门：原材料入厂 → 产品出厂"
    )
    as_of = models.DateField("核算基准日（因子适用日）")
    status = models.CharField(
        "状态",
        max_length=16,
        choices=[("draft", "草稿"), ("confirmed", "已确认")],
        default="draft",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    source_scenario = models.ForeignKey(
        "self",
        verbose_name="复制来源",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="copies",
    )

    class Meta:
        verbose_name = "生产方案"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Activity(models.Model):
    """活动数据：活动量 + 计量单位，可选指定因子（及版本）。"""

    scenario = models.ForeignKey(
        Scenario, on_delete=models.CASCADE, related_name="activities"
    )
    activity_type = models.CharField(
        "活动类型", max_length=16, choices=ActivityType.choices
    )
    name = models.CharField("活动名称", max_length=128)
    amount = models.DecimalField("活动量", max_digits=20, decimal_places=6)
    unit = models.ForeignKey(Unit, verbose_name="活动单位", on_delete=models.PROTECT)
    factor = models.ForeignKey(
        EmissionFactor,
        verbose_name="指定因子",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
    )
    factor_code = models.CharField(
        "导入时请求的因子编码", max_length=64, blank=True
    )
    external_ref = models.CharField(
        "外部单据号（防重复导入）", max_length=128, blank=True
    )
    factor_resolution_note = models.CharField(
        "因子解析说明", max_length=256, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "活动数据"
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "external_ref"],
                condition=models.Q(external_ref__gt=""),
                name="uq_activity_external_ref",
            )
        ]
        ordering = ["activity_type", "id"]

    def __str__(self):
        return f"{self.name} ({self.amount} {self.unit})"


class Report(models.Model):
    """计算结果/确认报告。确认时把每条计算行快照下来，之后因子改版不影响报告。"""

    scenario = models.ForeignKey(
        Scenario, on_delete=models.PROTECT, related_name="reports"
    )
    is_complete = models.BooleanField("总量是否完整（无未核算项）")
    accounted_kg = models.DecimalField(
        "已核算合计 kgCO2e", max_digits=20, decimal_places=6
    )
    unaccounted_count = models.PositiveIntegerField("未核算活动条数", default=0)
    result_json = models.JSONField("完整计算结果", default=dict)
    confirmed = models.BooleanField("是否已确认", default=False)
    confirmed_at = models.DateTimeField("确认时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "核算报告"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]


class ReportLine(models.Model):
    """已核算结果行快照：完整保存“活动量 × 哪个因子”的追溯链。"""

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="lines"
    )
    activity_name = models.CharField(max_length=128)
    activity_type = models.CharField(max_length=16, choices=ActivityType.choices)
    raw_amount = models.DecimalField(max_digits=20, decimal_places=6)
    raw_unit_code = models.CharField(max_length=16)
    amount_in_base = models.DecimalField(max_digits=26, decimal_places=6)
    factor_id = models.PositiveBigIntegerField()
    factor_code = models.CharField(max_length=64)
    factor_version = models.CharField(max_length=16)
    factor_name = models.CharField(max_length=128)
    factor_region_code = models.CharField(max_length=32)
    factor_value = models.DecimalField(max_digits=20, decimal_places=8)
    factor_status_at_calc = models.CharField(max_length=16)
    emissions_kg = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        verbose_name = "报告结果行"
        verbose_name_plural = verbose_name


class UnaccountedLine(models.Model):
    """未核算项快照：缺因子等原因导致无法计算的活动，单列展示，绝不悄悄排除。"""

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="unaccounted"
    )
    activity_name = models.CharField(max_length=128)
    activity_type = models.CharField(max_length=16, choices=ActivityType.choices)
    raw_amount = models.DecimalField(max_digits=20, decimal_places=6)
    raw_unit_code = models.CharField(max_length=16)
    requested_factor_code = models.CharField(max_length=64, blank=True)
    reason_code = models.CharField(max_length=32)
    reason_detail = models.CharField(max_length=256)

    class Meta:
        verbose_name = "未核算项"
        verbose_name_plural = verbose_name
