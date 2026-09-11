from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ActivityViewSet,
    FactorViewSet,
    RegionViewSet,
    ReportViewSet,
    ScenarioViewSet,
    UnitViewSet,
)

router = DefaultRouter()
router.register("scenarios", ScenarioViewSet, basename="scenario")
router.register("activities", ActivityViewSet, basename="activity")
router.register("reports", ReportViewSet, basename="report")
router.register("units", UnitViewSet, basename="unit")
router.register("regions", RegionViewSet, basename="region")
router.register("factors", FactorViewSet, basename="factor")

urlpatterns = [path("", include(router.urls))]
