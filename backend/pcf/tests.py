from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from .engine import CalcError, compute_scenario
from .models import (
    Activity,
    Dimension,
    EmissionFactor,
    Region,
    Report,
    Scenario,
    Unit,
)


class PcFFixture(TestCase):
    def setUp(self):
        self.kwh = Unit.objects.create(
            code="kWh", name="千瓦时", dimension=Dimension.ENERGY, factor_to_base="1"
        )
        self.mwh = Unit.objects.create(
            code="MWh", name="兆瓦时", dimension=Dimension.ENERGY, factor_to_base="1000"
        )
        self.kg = Unit.objects.create(
            code="kg", name="千克", dimension=Dimension.MASS, factor_to_base="1"
        )
        self.liter = Unit.objects.create(
            code="L", name="升", dimension=Dimension.VOLUME, factor_to_base="1"
        )
        self.region = Region.objects.create(code="CN-T", name="测试地区")
        self.el_v1 = EmissionFactor.objects.create(
            code="EL", version="1", name="电v1", activity_type="electricity",
            region=self.region, denominator_dimension=Dimension.ENERGY,
            value="0.6000", valid_from=date(2020, 1, 1), valid_to=date(2023, 12, 31),
            source="虚构", is_fictional=True, notes="测试",
        )
        self.el_v2 = EmissionFactor.objects.create(
            code="EL", version="2", name="电v2", activity_type="electricity",
            region=self.region, denominator_dimension=Dimension.ENERGY,
            value="0.5000", valid_from=date(2024, 1, 1), valid_to=None,
            source="虚构", is_fictional=True, notes="测试",
        )
        self.fuel_vol = EmissionFactor.objects.create(
            code="DSL", version="1", name="柴油", activity_type="fuel",
            region=self.region, denominator_dimension=Dimension.VOLUME,
            value="2.7000", valid_from=date(2020, 1, 1), valid_to=None,
            source="虚构", is_fictional=True, notes="测试",
        )
        self.client = APIClient()


class CalculationTests(PcFFixture):
    def _scenario(self, as_of=date(2026, 1, 1)):
        return Scenario.objects.create(name="s", product="p", as_of=as_of)

    def test_kwh_mwh_conversion_and_total(self):
        """kWh 与 MWh 换算后同口径求和：1000 kWh + 1 MWh = 2000 kWh × 0.5。"""
        s = self._scenario()
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="a1",
            amount="1000", unit=self.kwh, factor=self.el_v2,
        )
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="a2",
            amount="1", unit=self.mwh, factor=self.el_v2,
        )
        r = compute_scenario(s)
        self.assertEqual(r["accounted_kg"], "1000.000000")
        self.assertTrue(r["is_complete"])
        self.assertEqual(r["lines"][1]["amount_in_base"], "1000.000000")

    def test_missing_factor_is_unaccounted_not_silently_dropped(self):
        s = self._scenario()
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="有电",
            amount="1000", unit=self.kwh, factor=self.el_v2,
        )
        Activity.objects.create(
            scenario=s, activity_type="auxiliary", name="缺因子辅料",
            amount="10", unit=self.kg, factor=None,
        )
        r = compute_scenario(s)
        self.assertFalse(r["is_complete"])
        self.assertEqual(r["unaccounted_count"], 1)
        self.assertEqual(r["unaccounted"][0]["reason_code"], "MISSING_FACTOR")
        self.assertEqual(r["accounted_kg"], "500.000000")  # 只含已核算部分
        self.assertIn("不能视为完整产品碳足迹", r["completeness_notice"])

    def test_expired_factor_rejected(self):
        s = self._scenario()
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="旧电",
            amount="1000", unit=self.kwh, factor=self.el_v1,
        )
        with self.assertRaises(CalcError):
            compute_scenario(s)

    def test_incompatible_units_rejected(self):
        """kg(质量) 活动 × 体积分母因子：拒绝折算。"""
        s = self._scenario()
        Activity.objects.create(
            scenario=s, activity_type="fuel", name="柴油按千克",
            amount="500", unit=self.kg, factor=self.fuel_vol,
        )
        with self.assertRaises(CalcError) as ctx:
            compute_scenario(s)
        self.assertIn("单位不相容", str(ctx.exception.detail))

    def test_factor_code_resolves_latest_valid_version(self):
        s = self._scenario()
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="按编码导入",
            amount="2000", unit=self.kwh, factor_code="EL",
        )
        r = compute_scenario(s, persist_resolution=True)
        self.assertEqual(r["lines"][0]["factor_version"], "2")
        self.assertEqual(r["accounted_kg"], "1000.000000")


class WorkflowTests(PcFFixture):
    def test_confirmed_report_keeps_original_factor_after_new_version(self):
        """确认报告后因子改版/过期，报告快照仍保留原始因子。"""
        s = Scenario.objects.create(name="hist", product="p", as_of=date(2023, 6, 1))
        act = Activity.objects.create(
            scenario=s, activity_type="electricity", name="历史用电",
            amount="1000", unit=self.kwh, factor_code="EL",
        )
        res = self.client.post(f"/api/scenarios/{s.id}/calculate/", {})
        self.assertEqual(res.status_code, 200, res.content)
        report_id = res.json()["id"]
        self.assertEqual(res.json()["lines"][0]["factor_version"], "1")

        confirmed = self.client.post(f"/api/reports/{report_id}/confirm/", {})
        self.assertEqual(confirmed.status_code, 200)

        detail = self.client.get(f"/api/reports/{report_id}/").json()
        self.assertEqual(detail["lines"][0]["factor_version"], "1")
        self.assertEqual(detail["lines"][0]["factor_value"], "0.60000000")
        # 情景已冻结，不能再改活动
        blocked = self.client.patch(
            f"/api/activities/{act.id}/", {"amount": "9999"}
        )
        self.assertEqual(blocked.status_code, 400)

    def test_copy_scenario_independent_edit(self):
        s = Scenario.objects.create(name="base", product="p", as_of=date(2026, 1, 1))
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="电",
            amount="1000", unit=self.kwh, factor=self.el_v2,
        )
        res = self.client.post(f"/api/scenarios/{s.id}/copy/", {})
        self.assertEqual(res.status_code, 201, res.content)
        clone_id = res.json()["id"]
        clone = Scenario.objects.get(id=clone_id)
        self.assertEqual(clone.activities.count(), 1)
        self.assertEqual(clone.source_scenario_id, s.id)
        self.assertEqual(clone.status, "draft")

    def test_duplicate_import_skipped(self):
        s = Scenario.objects.create(name="imp", product="p", as_of=date(2026, 1, 1))
        rows = [
            {
                "external_ref": "DOC-1",
                "activity_type": "electricity",
                "name": "电表一月",
                "amount": "1000",
                "unit_code": "kWh",
                "factor_code": "EL",
            }
        ]
        r1 = self.client.post(
            f"/api/scenarios/{s.id}/import-activities/", {"rows": rows}, format="json"
        )
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r1.json()["imported"], 1)

        # 同单据号重复导入：跳过，不追加活动
        r2 = self.client.post(
            f"/api/scenarios/{s.id}/import-activities/", {"rows": rows}, format="json"
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.json()["imported"], 0)
        self.assertEqual(len(r2.json()["skipped"]), 1)
        self.assertEqual(s.activities.count(), 1)

        calc = self.client.post(f"/api/scenarios/{s.id}/calculate/", {}).json()
        self.assertEqual(calc["accounted_kg"], "500.000000")  # 未被翻倍

    def test_import_with_incompatible_dimension_rejected(self):
        s = Scenario.objects.create(name="bad", product="p", as_of=date(2026, 1, 1))
        rows = [
            {
                "external_ref": "DOC-BAD",
                "activity_type": "fuel",
                "name": "柴油按千克",
                "amount": "500",
                "unit_code": "kg",
                "factor_code": "DSL",
            }
        ]
        r = self.client.post(
            f"/api/scenarios/{s.id}/import-activities/", {"rows": rows}, format="json"
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("不相容", str(r.json()["non_field_errors"]))
        self.assertEqual(s.activities.count(), 0)

    def test_calculate_api_rejects_expired(self):
        s = Scenario.objects.create(name="exp", product="p", as_of=date(2026, 1, 1))
        Activity.objects.create(
            scenario=s, activity_type="electricity", name="旧电",
            amount="1000", unit=self.kwh, factor=self.el_v1,
        )
        r = self.client.post(f"/api/scenarios/{s.id}/calculate/", {})
        self.assertEqual(r.status_code, 400)
        self.assertIn("过期", str(r.json()["non_field_errors"]))
