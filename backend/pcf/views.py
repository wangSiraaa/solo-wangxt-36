import csv
import io
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .engine import CalcError, compute_scenario
from .models import (
    Activity,
    EmissionFactor,
    Region,
    Report,
    ReportLine,
    Scenario,
    Unit,
    UnaccountedLine,
)
from .serializers import (
    ActivitySerializer,
    FactorSerializer,
    RegionSerializer,
    ReportDetailSerializer,
    ReportSummarySerializer,
    ScenarioDetailSerializer,
    ScenarioSerializer,
    UnitSerializer,
)

CSV_COLUMNS = ["external_ref", "activity_type", "name", "amount", "unit_code", "factor_code"]


def _save_snapshot(report, result):
    """把计算结果固化为报告行，确认后不再受因子改版影响。"""
    ReportLine.objects.bulk_create(
        [
            ReportLine(
                report=report,
                activity_name=ln["activity_name"],
                activity_type=ln["activity_type"],
                raw_amount=ln["raw_amount"],
                raw_unit_code=ln["raw_unit"],
                amount_in_base=ln["amount_in_base"],
                factor_id=ln["factor_id"],
                factor_code=ln["factor_code"],
                factor_version=ln["factor_version"],
                factor_name=ln["factor_name"],
                factor_region_code=ln["factor_region"],
                factor_value=ln["factor_value"],
                factor_status_at_calc=ln["factor_status_at_calc"],
                emissions_kg=ln["emissions_kg"],
            )
            for ln in result["lines"]
        ]
    )
    UnaccountedLine.objects.bulk_create(
        [
            UnaccountedLine(
                report=report,
                activity_name=u["activity_name"],
                activity_type=u["activity_type"],
                raw_amount=u["raw_amount"],
                raw_unit_code=u["raw_unit"],
                requested_factor_code=u["requested_factor_code"],
                reason_code=u["reason_code"],
                reason_detail=u["reason_detail"],
            )
            for u in result["unaccounted"]
        ]
    )


class ScenarioViewSet(viewsets.ModelViewSet):
    queryset = Scenario.objects.all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ScenarioDetailSerializer
        return ScenarioSerializer

    def update(self, request, *args, **kwargs):
        scenario = self.get_object()
        if scenario.status == "confirmed":
            return Response(
                {"non_field_errors": ["情景已确认并冻结；请复制情景后在副本上调整。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        scenario = self.get_object()
        if scenario.status == "confirmed":
            return Response(
                {"non_field_errors": ["已确认情景不能删除。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def copy(self, request, pk=None):
        """复制情景：深拷贝活动数据，因子仍指向因子库当前版本。"""
        source = self.get_object()
        with transaction.atomic():
            clone = Scenario.objects.create(
                name=f"{source.name}（副本）",
                product=source.product,
                functional_unit=source.functional_unit,
                boundary_note=source.boundary_note,
                as_of=source.as_of,
                source_scenario=source,
            )
            for act in source.activities.all():
                Activity.objects.create(
                    scenario=clone,
                    activity_type=act.activity_type,
                    name=act.name,
                    amount=act.amount,
                    unit=act.unit,
                    factor=act.factor,
                    factor_code=act.factor_code,
                    external_ref="",  # 副本是新情景，不继承外部单据去重键
                    factor_resolution_note=act.factor_resolution_note,
                )
        return Response(
            ScenarioDetailSerializer(clone).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="calculate")
    def calculate(self, request, pk=None):
        """试算：返回贡献树与可追溯结果行；可重复试算，不冻结情景。"""
        scenario = self.get_object()
        result = compute_scenario(scenario, persist_resolution=True)
        with transaction.atomic():
            report = Report.objects.create(
                scenario=scenario,
                is_complete=result["is_complete"],
                accounted_kg=result["accounted_kg"],
                unaccounted_count=result["unaccounted_count"],
                result_json=result,
                confirmed=False,
            )
            _save_snapshot(report, result)
        return Response(ReportDetailSerializer(report).data)

    @action(detail=True, methods=["post"], url_path="import-activities")
    def import_activities(self, request, pk=None):
        """批量导入活动（JSON rows 或 CSV 文本）。

        external_ref 相同视为重复导入，跳过而非累加，防止总量被重复计算。
        """
        scenario = self.get_object()
        if scenario.status == "confirmed":
            return Response(
                {"non_field_errors": ["情景已冻结，不能导入活动。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows, parse_errors = _parse_rows(request.data)
        if parse_errors:
            return Response(
                {"non_field_errors": parse_errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_refs = set(
            scenario.activities.exclude(external_ref="").values_list(
                "external_ref", flat=True
            )
        )
        units = {u.code: u for u in Unit.objects.all()}

        created, skipped, errors = [], [], []
        for idx, row in enumerate(rows, start=1):
            ref = (row.get("external_ref") or "").strip()
            if not ref:
                errors.append(f"第 {idx} 行缺少 external_ref（批量导入必须提供，用于防重复）")
                continue
            if ref in existing_refs:
                skipped.append({"external_ref": ref, "reason": "重复导入，已跳过"})
                continue

            act_type = (row.get("activity_type") or "").strip()
            from .models import ActivityType

            if act_type not in ActivityType.values:
                errors.append(f"第 {idx} 行 activity_type 非法：{act_type}")
                continue
            unit = units.get((row.get("unit_code") or "").strip())
            if unit is None:
                errors.append(f"第 {idx} 行单位不存在：{row.get('unit_code')}")
                continue
            try:
                amount = Decimal(str(row.get("amount")))
            except Exception:
                errors.append(f"第 {idx} 行活动量非法：{row.get('amount')}")
                continue

            factor = None
            factor_code = (row.get("factor_code") or "").strip()
            note = ""
            if factor_code:
                factor, note = _pick_factor(factor_code, act_type, scenario.as_of, unit)
                if isinstance(factor, str):  # 错误信息
                    errors.append(f"第 {idx} 行：{factor}")
                    continue

            existing_refs.add(ref)
            created.append(
                Activity(
                    scenario=scenario,
                    activity_type=act_type,
                    name=(row.get("name") or "").strip() or ref,
                    amount=amount,
                    unit=unit,
                    factor=factor,
                    factor_code=factor_code,
                    external_ref=ref,
                    factor_resolution_note=note,
                )
            )

        if errors:
            # 整批拒绝：不写入任何一条，避免部分导入造成的口径混乱
            return Response(
                {"non_field_errors": errors, "imported": 0, "skipped": len(skipped)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Activity.objects.bulk_create(created)
        return Response(
            {
                "imported": len(created),
                "skipped": skipped,
                "message": f"导入 {len(created)} 条，跳过重复 {len(skipped)} 条",
            },
            status=status.HTTP_201_CREATED,
        )


def _pick_factor(code, activity_type, as_of, unit):
    """导入时解析因子：类型/基准日/量纲全部通过才采用，否则整行拒绝。"""
    from .engine import resolve_factor

    factor, note = resolve_factor(code, activity_type, as_of)
    if factor is None:
        return note, None
    if factor.denominator_dimension != unit.dimension:
        return (
            f"因子 {code} 的分母量纲与单位 {unit.code} 不相容，拒绝导入",
            None,
        )
    return factor, note


def _parse_rows(data):
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"], []
    csv_text = data.get("csv") if isinstance(data, dict) else None
    if not csv_text:
        return None, ["请提供 rows（JSON 数组）或 csv（CSV 文本）"]
    reader = csv.DictReader(io.StringIO(csv_text))
    missing = set(CSV_COLUMNS) - set(reader.fieldnames or [])
    if missing:
        return None, [f"CSV 缺少列：{', '.join(sorted(missing))}"]
    return list(reader), []


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related("unit", "factor", "scenario")
    serializer_class = ActivitySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        scenario_id = self.request.query_params.get("scenario")
        if scenario_id:
            qs = qs.filter(scenario_id=scenario_id)
        return qs

    def _check_locked(self, activity):
        if activity.scenario.status == "confirmed":
            return Response(
                {"non_field_errors": ["所属情景已确认冻结，不能修改活动。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        locked = self._check_locked(self.get_object())
        return locked or super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        locked = self._check_locked(self.get_object())
        return locked or super().destroy(request, *args, **kwargs)


class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Report.objects.select_related("scenario")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReportDetailSerializer
        return ReportSummarySerializer

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """确认报告：快照生效，情景冻结；即便有未核算项也可确认，
        但 is_complete=False 会明确展示这是部分总量。"""
        report = self.get_object()
        if report.confirmed:
            return Response(
                {"non_field_errors": ["该报告已确认，不能重复确认。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            report.confirmed = True
            report.confirmed_at = timezone.now()
            report.save(update_fields=["confirmed", "confirmed_at"])
            report.scenario.status = "confirmed"
            report.scenario.save(update_fields=["status"])
        return Response(ReportDetailSerializer(report).data)


class UnitViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.all()
    serializer_class = RegionSerializer


class FactorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmissionFactor.objects.select_related("region")
    serializer_class = FactorSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for field in ("activity_type", "region", "code"):
            value = params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs
