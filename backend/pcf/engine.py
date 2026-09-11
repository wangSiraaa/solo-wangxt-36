"""碳足迹计算引擎。

规则（首版边界：原材料入厂 → 产品出厂）：
1. 每条活动 = 活动量 × 排放因子，结果行完整记录换算过程与因子版本，可追溯。
2. 单位不相容（量纲不同）→ 硬性拒绝，整次计算不产出总量。
3. 因子过期 / 未生效 / 活动类型不匹配 → 硬性拒绝。
4. 缺失因子（活动未指定且无法解析）→ 列为“未核算”，
   总量标记为不完整（is_complete=False），绝不悄悄排除后给出完整总量。
"""

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from rest_framework import serializers

from .models import Activity, EmissionFactor

KG = Decimal("0.000001")  # 结果保留 6 位小数
BASE = Decimal("0.000001")  # 基准单位下活动量精度


class CalcError(serializers.ValidationError):
    """硬性核算错误：单位不相容、因子过期等，拒绝给出结果。"""


ACTIVITY_TYPE_LABELS = {
    "electricity": "电力",
    "fuel": "燃料",
    "auxiliary": "辅料",
}


def _q(value):
    return Decimal(value).quantize(KG, rounding=ROUND_HALF_UP)


def resolve_factor(code, activity_type, as_of):
    """按因子编码 + 活动类型 + 基准日解析“当前有效”的最新版本。"""
    if not code:
        return None, "未指定因子编码"
    candidates = EmissionFactor.objects.filter(
        code=code, activity_type=activity_type
    ).order_by("-valid_from", "-version")
    valid = [f for f in candidates if f.status_on(as_of) == "valid"]
    if not valid:
        return None, f"因子 {code} 在 {as_of} 无有效版本"
    factor = valid[0]
    note = f"解析到最新有效版本 {factor.version}（{factor.region.code}）"
    return factor, note


def _line_payload(activity, factor, status, amount_base, emissions):
    return {
        "activity_id": activity.id,
        "activity_name": activity.name,
        "activity_type": activity.activity_type,
        "raw_amount": str(activity.amount),
        "raw_unit": activity.unit.code,
        "unit_factor_to_base": str(activity.unit.factor_to_base),
        "amount_in_base": str(amount_base),
        "factor_id": factor.id,
        "factor_code": factor.code,
        "factor_version": factor.version,
        "factor_name": factor.name,
        "factor_region": factor.region.code,
        "factor_value": str(factor.value),
        "factor_denominator_dimension": factor.denominator_dimension,
        "factor_status_at_calc": status,
        "formula": (
            f"{activity.amount} {activity.unit.code} × "
            f"{activity.unit.factor_to_base} = {amount_base} 基准单位；"
            f"{amount_base} × {factor.value} kgCO2e = {emissions} kgCO2e"
        ),
        "emissions_kg": str(emissions),
    }


def compute_scenario(scenario, as_of=None, persist_resolution=False):
    """对情景执行核算，返回结构化结果。硬性问题抛 CalcError（HTTP 400）。"""
    as_of = as_of or scenario.as_of
    activities = list(
        scenario.activities.select_related("unit", "factor", "factor__region")
    )
    if not activities:
        raise CalcError({"non_field_errors": ["情景下没有任何活动数据，无法核算。"]})

    lines = []
    unaccounted = []

    for act in activities:
        factor = act.factor
        note = ""
        if factor is None and act.factor_code:
            # 仅在活动未绑定具体因子版本时按编码解析当前有效版本；
            # 已显式绑定的因子（含历史版本）必须原样保留，以支持快照追溯。
            factor, note = resolve_factor(act.factor_code, act.activity_type, as_of)
            if persist_resolution and factor is not None:
                act.factor = factor
                act.factor_resolution_note = note
                act.save(update_fields=["factor", "factor_resolution_note"])

        if factor is None:
            unaccounted.append(
                {
                    "activity_id": act.id,
                    "activity_name": act.name,
                    "activity_type": act.activity_type,
                    "raw_amount": str(act.amount),
                    "raw_unit": act.unit.code,
                    "requested_factor_code": act.factor_code,
                    "reason_code": "MISSING_FACTOR",
                    "reason_detail": note
                    or f"该{ACTIVITY_TYPE_LABELS.get(act.activity_type, act.activity_type)}活动未配置可用排放因子",
                }
            )
            continue

        # 硬性校验：活动类型必须与因子适用类型一致
        if factor.activity_type != act.activity_type:
            raise CalcError(
                {
                    "non_field_errors": [
                        f"活动「{act.name}」类型为"
                        f"{ACTIVITY_TYPE_LABELS.get(act.activity_type)}，"
                        f"但因子 {factor.code} 仅适用于"
                        f"{ACTIVITY_TYPE_LABELS.get(factor.activity_type)}，拒绝核算。"
                    ]
                }
            )

        # 硬性校验：因子在基准日必须有效（过期/未生效都拒绝）
        status = factor.status_on(as_of)
        if status == "expired":
            raise CalcError(
                {
                    "non_field_errors": [
                        f"活动「{act.name}」使用的因子 {factor.code} v{factor.version}"
                        f"已于 {factor.valid_to} 过期（基准日 {as_of}），"
                        f"请改用当前有效版本后重新核算。"
                    ]
                }
            )
        if status == "future":
            raise CalcError(
                {
                    "non_field_errors": [
                        f"活动「{act.name}」使用的因子 {factor.code} v{factor.version}"
                        f"自 {factor.valid_from} 才生效（基准日 {as_of}），拒绝核算。"
                    ]
                }
            )

        # 硬性校验：量纲必须相容，跨量纲折算一律拒绝
        if act.unit.dimension != factor.denominator_dimension:
            raise CalcError(
                {
                    "non_field_errors": [
                        f"单位不相容：活动「{act.name}」的单位 {act.unit.code}"
                        f"（量纲 {act.unit.get_dimension_display()}）与因子 "
                        f"{factor.code} 的分母量纲"
                        f"（{factor.get_denominator_dimension_display()}）不一致，"
                        f"拒绝折算。"
                    ]
                }
            )

        amount_base = (act.amount * act.unit.factor_to_base).quantize(BASE)
        emissions = _q(amount_base * factor.value)
        lines.append(_line_payload(act, factor, status, amount_base, emissions))

    accounted = sum((Decimal(ln["emissions_kg"]) for ln in lines), Decimal("0"))
    accounted = _q(accounted)

    tree = _build_tree(lines, unaccounted, accounted)

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "product": scenario.product,
        "functional_unit": scenario.functional_unit,
        "boundary": scenario.boundary_note,
        "as_of": str(as_of),
        "accounted_kg": str(accounted),
        "accounted_t": str(_q(accounted / Decimal("1000"))),
        "is_complete": len(unaccounted) == 0,
        "activity_count": len(activities),
        "accounted_count": len(lines),
        "unaccounted_count": len(unaccounted),
        "lines": lines,
        "unaccounted": unaccounted,
        "tree": tree,
        "completeness_notice": (
            None
            if not unaccounted
            else f"有 {len(unaccounted)} 条活动因缺失因子未核算，"
            "以下合计仅为部分总量，不能视为完整产品碳足迹。"
        ),
    }


def _build_tree(lines, unaccounted, accounted):
    type_nodes = []
    for code, label in ACTIVITY_TYPE_LABELS.items():
        children = [ln for ln in lines if ln["activity_type"] == code]
        if not children:
            continue
        subtotal = sum(
            (Decimal(ln["emissions_kg"]) for ln in children), Decimal("0")
        )
        subtotal = _q(subtotal)
        share = (
            (_q(subtotal / accounted * Decimal("100"))) if accounted > 0 else Decimal("0")
        )
        type_nodes.append(
            {
                "code": code,
                "name": label,
                "emissions_kg": str(subtotal),
                "share_pct": str(share),
                "children": [
                    {
                        "name": ln["activity_name"],
                        "emissions_kg": ln["emissions_kg"],
                        "factor": f"{ln['factor_code']} v{ln['factor_version']}",
                        "formula": ln["formula"],
                    }
                    for ln in children
                ],
            }
        )

    root = {
        "name": "已核算合计（部分总量）" if unaccounted else "产品碳足迹合计",
        "emissions_kg": str(accounted),
        "children": type_nodes,
    }
    if unaccounted:
        root["children"].append(
            {
                "code": "unaccounted",
                "name": f"未核算（{len(unaccounted)} 条，缺失因子，不计入总量）",
                "emissions_kg": None,
                "share_pct": None,
                "children": [
                    {
                        "name": f"{u['activity_name']}（{u['raw_amount']} "
                        f"{u['raw_unit']}）",
                        "emissions_kg": None,
                        "factor": u["requested_factor_code"] or "未指定",
                        "formula": u["reason_detail"],
                    }
                    for u in unaccounted
                ],
            }
        )
    return root
