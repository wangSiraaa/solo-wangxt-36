"""写入虚构示例数据：单位、地区、因子版本、演示方案。

所有排放因子均为虚构的“Acme 演示因子库”数据，仅用于演示软件功能，
不来自任何付费数据库，未经过任何认证，严禁用于真实碳核算或合规披露。
"""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from pcf.engine import compute_scenario
from pcf.models import (
    Activity,
    Dimension,
    EmissionFactor,
    Region,
    Scenario,
    Unit,
)

DISCLAIMER = (
    "Acme 虚构示例数据，仅用于演示本工作台的计算与追溯功能；"
    "不来自付费/官方数据库，未获得任何认证，不得用于真实碳核算或对外披露。"
)

UNITS = [
    # code, name, dimension, factor_to_base
    ("kWh", "千瓦时", Dimension.ENERGY, "1"),
    ("MWh", "兆瓦时", Dimension.ENERGY, "1000"),
    ("MJ", "兆焦", Dimension.ENERGY, "0.2777777778"),
    ("kg", "千克", Dimension.MASS, "1"),
    ("t", "吨", Dimension.MASS, "1000"),
    ("L", "升", Dimension.VOLUME, "1"),
    ("m3", "立方米", Dimension.VOLUME, "1000"),
    ("pc", "件", Dimension.COUNT, "1"),
]

REGIONS = [
    ("CN-NAT", "全国电网平均"),
    ("CN-EC", "华东电网"),
    ("CN-NO", "华北电网"),
]

# code, version, name, activity_type, region_code, denominator_dimension,
# value, valid_from, valid_to
FACTORS = [
    (
        "EL-CN-GRID", "1", "全国电网平均电力排放因子（虚构）",
        "electricity", "CN-NAT", Dimension.ENERGY,
        "0.5810", date(2019, 1, 1), date(2023, 12, 31),
    ),
    (
        "EL-CN-GRID", "2", "全国电网平均电力排放因子（虚构）",
        "electricity", "CN-NAT", Dimension.ENERGY,
        "0.5360", date(2024, 1, 1), date(2025, 12, 31),
    ),
    (
        "EL-CN-GRID", "3", "全国电网平均电力排放因子（虚构）",
        "electricity", "CN-NAT", Dimension.ENERGY,
        "0.5080", date(2026, 1, 1), None,
    ),
    (
        "EL-CN-EAST", "1", "华东电网电力排放因子（虚构）",
        "electricity", "CN-EC", Dimension.ENERGY,
        "0.5100", date(2024, 1, 1), date(2026, 12, 31),
    ),
    (
        "FU-DIESEL", "1", "柴油燃烧排放因子（虚构）",
        "fuel", "CN-NAT", Dimension.VOLUME,
        "2.6800", date(2020, 1, 1), None,
    ),
    (
        "FU-COAL", "1", "工业煤燃烧排放因子（虚构）",
        "fuel", "CN-NAT", Dimension.MASS,
        "2.4200", date(2020, 1, 1), None,
    ),
    (
        "AUX-LUBE", "1", "切削润滑油投入排放因子（虚构）",
        "auxiliary", "CN-NAT", Dimension.MASS,
        "0.8500", date(2021, 1, 1), None,
    ),
    (
        "AUX-CUTFLUID", "1", "水基切削液投入排放因子（虚构）",
        "auxiliary", "CN-NAT", Dimension.MASS,
        "1.1200", date(2021, 1, 1), None,
    ),
]

# scenario name, product, as_of, source(-) ; activities:
# (type, name, amount, unit, factor_code or None, ext_ref)
S1 = (
    "A型减速箱-基线方案", "A型减速箱", date(2026, 6, 1),
    [
        ("electricity", "机加工车间用电", "12000", "kWh", "EL-CN-GRID", "MTR-001"),
        ("electricity", "热处理车间用电", "2.4", "MWh", "EL-CN-GRID", "HT-001"),
        ("fuel", "叉车柴油", "180", "L", "FU-DIESEL", "LOG-001"),
        ("auxiliary", "切削液投入", "320", "kg", "AUX-CUTFLUID", "AUX-001"),
        ("auxiliary", "工业清洗剂投入", "60", "kg", None, "AUX-002"),
    ],
)
S2 = (
    "A型减速箱-节能改造方案", "A型减速箱", date(2026, 6, 1),
    [
        ("electricity", "机加工车间用电", "9800", "kWh", "EL-CN-EAST", "MTR-101"),
        ("electricity", "热处理车间用电", "1.9", "MWh", "EL-CN-EAST", "HT-101"),
        ("fuel", "叉车柴油", "150", "L", "FU-DIESEL", "LOG-101"),
        ("auxiliary", "切削液投入", "300", "kg", "AUX-CUTFLUID", "AUX-101"),
        ("auxiliary", "工业清洗剂投入", "60", "kg", None, "AUX-102"),
    ],
)
S3 = (
    "演示-因子已过期（拒绝核算）", "A型减速箱", date(2026, 6, 1),
    [
        # @1 表示显式钉在 2023 年已失效的 v1 版本上，核算时必须拒绝
        ("electricity", "仍引用2023版因子的用电", "5000", "kWh", "EL-CN-GRID@1", "EXP-001"),
    ],
)
S4 = (
    "演示-单位不相容（拒绝核算）", "A型减速箱", date(2026, 6, 1),
    [
        ("fuel", "柴油按千克记账但因子分母为体积", "800", "kg", "FU-DIESEL", "DIM-001"),
    ],
)
S5 = (
    "A型减速箱-2025年历史确认报告", "A型减速箱", date(2025, 6, 1),
    [
        # 2025 年当时按 v2 核算并确认；v2 现已过期（2026 起用 v3），
        # 但已确认报告永久保留 v2 原始因子快照，不受改版影响。
        ("electricity", "机加工车间用电", "12000", "kWh", "EL-CN-GRID@2", "H-MTR-001"),
        ("electricity", "热处理车间用电", "2.4", "MWh", "EL-CN-GRID@2", "H-HT-001"),
        ("fuel", "叉车柴油", "180", "L", "FU-DIESEL", "H-LOG-001"),
    ],
)

SCENARIOS = [S1, S2, S3, S4, S5]


class Command(BaseCommand):
    help = "写入虚构演示数据（幂等：已存在则跳过）"

    @transaction.atomic
    def handle(self, *args, **options):
        units = {}
        for code, name, dim, f2b in UNITS:
            obj, _ = Unit.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "dimension": dim,
                    "factor_to_base": Decimal(f2b),
                },
            )
            units[code] = obj

        regions = {}
        for code, name in REGIONS:
            obj, _ = Region.objects.get_or_create(code=code, defaults={"name": name})
            regions[code] = obj

        for (
            code, version, name, atype, rcode, dim, value, vfrom, vto
        ) in FACTORS:
            _, created = EmissionFactor.objects.get_or_create(
                code=code,
                version=version,
                defaults={
                    "name": name,
                    "activity_type": atype,
                    "region": regions[rcode],
                    "denominator_dimension": dim,
                    "value": Decimal(value),
                    "valid_from": vfrom,
                    "valid_to": vto,
                    "source": "Acme 演示因子库（虚构）",
                    "is_fictional": True,
                    "notes": DISCLAIMER,
                },
            )
            if created:
                self.stdout.write(f"因子 {code} v{version} 已创建")

        for name, product, as_of, acts in SCENARIOS:
            if Scenario.objects.filter(name=name).exists():
                continue
            scenario = Scenario.objects.create(
                name=name, product=product, as_of=as_of
            )
            for atype, aname, amount, ucode, fcode, ref in acts:
                factor = None
                note = ""
                pinned_code = fcode
                if fcode and "@" in fcode:
                    # 编码@版本：显式钉住某一历史版本（用于过期拒绝演示）
                    pinned_code, pin_version = fcode.split("@", 1)
                    factor = EmissionFactor.objects.get(
                        code=pinned_code, version=pin_version
                    )
                    note = f"显式指定版本 {pin_version}"
                elif fcode:
                    factor, note = self._resolve(fcode, atype, as_of, units[ucode])
                Activity.objects.create(
                    scenario=scenario,
                    activity_type=atype,
                    name=aname,
                    amount=Decimal(amount),
                    unit=units[ucode],
                    factor=factor,
                    factor_code=pinned_code or "",
                    external_ref=ref,
                    factor_resolution_note=note,
                )

            if name.startswith("A型减速箱-2025"):
                # 历史方案：核算并确认，冻结当时（v1）因子快照
                result = compute_scenario(scenario, persist_resolution=True)
                from pcf.views import _save_snapshot
                from pcf.models import Report

                report = Report.objects.create(
                    scenario=scenario,
                    is_complete=result["is_complete"],
                    accounted_kg=result["accounted_kg"],
                    unaccounted_count=result["unaccounted_count"],
                    result_json=result,
                )
                _save_snapshot(report, result)
                report.confirmed = True
                report.confirmed_at = timezone.now()
                report.save(update_fields=["confirmed", "confirmed_at"])
                scenario.status = "confirmed"
                scenario.save(update_fields=["status"])

            self.stdout.write(f"情景「{name}」已创建（{len(acts)} 条活动）")

        self.stdout.write(self.style.SUCCESS("演示数据就绪。"))

    def _resolve(self, code, atype, as_of, unit):
        from pcf.engine import resolve_factor

        factor, note = resolve_factor(code, atype, as_of)
        if factor is None:
            return None, note
        if factor.denominator_dimension != unit.dimension:
            return None, f"{note}；但量纲与 {unit.code} 不相容，留待核算时拒绝"
        return factor, note
