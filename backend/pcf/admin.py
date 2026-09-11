from django.contrib import admin

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


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "dimension", "factor_to_base")
    list_filter = ("dimension",)


@admin.register(EmissionFactor)
class FactorAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "version",
        "name",
        "activity_type",
        "region",
        "denominator_dimension",
        "value",
        "valid_from",
        "valid_to",
        "is_fictional",
    )
    list_filter = ("activity_type", "region", "is_fictional")


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "as_of", "status", "source_scenario")
    list_filter = ("status",)
    inlines = [ActivityInline]


class ReportLineInline(admin.TabularInline):
    model = ReportLine
    extra = 0


class UnaccountedInline(admin.TabularInline):
    model = UnaccountedLine
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "scenario",
        "is_complete",
        "accounted_kg",
        "unaccounted_count",
        "confirmed",
        "created_at",
    )
    list_filter = ("confirmed", "is_complete")
    inlines = [ReportLineInline, UnaccountedInline]
