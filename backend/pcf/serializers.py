from rest_framework import serializers

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


class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "code", "name"]


class UnitSerializer(serializers.ModelSerializer):
    dimension_display = serializers.CharField(source="get_dimension_display", read_only=True)

    class Meta:
        model = Unit
        fields = ["id", "code", "name", "dimension", "dimension_display", "factor_to_base"]


class FactorSerializer(serializers.ModelSerializer):
    region_code = serializers.CharField(source="region.code", read_only=True)
    region_name = serializers.CharField(source="region.name", read_only=True)
    activity_type_display = serializers.CharField(
        source="get_activity_type_display", read_only=True
    )
    denominator_dimension_display = serializers.CharField(
        source="get_denominator_dimension_display", read_only=True
    )

    class Meta:
        model = EmissionFactor
        fields = [
            "id",
            "code",
            "version",
            "name",
            "activity_type",
            "activity_type_display",
            "region",
            "region_code",
            "region_name",
            "denominator_dimension",
            "denominator_dimension_display",
            "value",
            "valid_from",
            "valid_to",
            "source",
            "is_fictional",
            "notes",
        ]


class ActivitySerializer(serializers.ModelSerializer):
    unit_code = serializers.CharField(source="unit.code", read_only=True)
    unit_dimension = serializers.CharField(source="unit.dimension", read_only=True)
    factor_label = serializers.SerializerMethodField()

    class Meta:
        model = Activity
        fields = [
            "id",
            "scenario",
            "activity_type",
            "name",
            "amount",
            "unit",
            "unit_code",
            "unit_dimension",
            "factor",
            "factor_code",
            "factor_label",
            "factor_resolution_note",
            "external_ref",
            "created_at",
        ]
        read_only_fields = ["factor_resolution_note", "created_at"]

    def get_factor_label(self, obj):
        if obj.factor_id:
            return f"{obj.factor.code} v{obj.factor.version}"
        return None

    def validate(self, attrs):
        scenario = attrs.get("scenario") or getattr(self.instance, "scenario", None)
        if scenario and scenario.status == "confirmed":
            raise serializers.ValidationError("情景已确认并冻结，不能修改活动；请复制情景后调整。")
        return attrs


class ScenarioSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Scenario
        fields = [
            "id",
            "name",
            "product",
            "functional_unit",
            "boundary_note",
            "as_of",
            "status",
            "status_display",
            "source_scenario",
            "created_at",
        ]
        read_only_fields = ["status", "source_scenario", "created_at"]


class ScenarioDetailSerializer(ScenarioSerializer):
    activities = ActivitySerializer(many=True, read_only=True)

    class Meta(ScenarioSerializer.Meta):
        fields = ScenarioSerializer.Meta.fields + ["activities"]


class ReportLineSerializer(serializers.ModelSerializer):
    activity_type_display = serializers.SerializerMethodField()

    class Meta:
        model = ReportLine
        exclude = ["id", "report"]

    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display()


class UnaccountedLineSerializer(serializers.ModelSerializer):
    activity_type_display = serializers.SerializerMethodField()

    class Meta:
        model = UnaccountedLine
        exclude = ["id", "report"]

    def get_activity_type_display(self, obj):
        return obj.get_activity_type_display()


class ReportSummarySerializer(serializers.ModelSerializer):
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)
    product = serializers.CharField(source="scenario.product", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "scenario",
            "scenario_name",
            "product",
            "is_complete",
            "accounted_kg",
            "unaccounted_count",
            "confirmed",
            "confirmed_at",
            "created_at",
        ]


class ReportDetailSerializer(ReportSummarySerializer):
    lines = ReportLineSerializer(many=True, read_only=True)
    unaccounted_lines = UnaccountedLineSerializer(
        source="unaccounted", many=True, read_only=True
    )
    tree = serializers.SerializerMethodField()
    completeness_notice = serializers.SerializerMethodField()
    accounted_t = serializers.SerializerMethodField()
    activity_count = serializers.SerializerMethodField()
    accounted_count = serializers.SerializerMethodField()
    boundary = serializers.CharField(source="scenario.boundary_note", read_only=True)
    functional_unit = serializers.CharField(source="scenario.functional_unit", read_only=True)
    as_of = serializers.SerializerMethodField()

    class Meta(ReportSummarySerializer.Meta):
        fields = ReportSummarySerializer.Meta.fields + [
            "boundary",
            "functional_unit",
            "as_of",
            "accounted_t",
            "activity_count",
            "accounted_count",
            "completeness_notice",
            "lines",
            "unaccounted_lines",
            "tree",
        ]

    def get_tree(self, obj):
        return obj.result_json.get("tree")

    def get_completeness_notice(self, obj):
        return obj.result_json.get("completeness_notice")

    def get_accounted_t(self, obj):
        return obj.result_json.get("accounted_t")

    def get_activity_count(self, obj):
        return obj.result_json.get("activity_count")

    def get_accounted_count(self, obj):
        return obj.result_json.get("accounted_count")

    def get_as_of(self, obj):
        return obj.result_json.get("as_of")
