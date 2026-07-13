from rest_framework.routers import DefaultRouter

from .views import (
    CashierShiftViewSet,
    CashRegisterViewSet,
    ReturnViewSet,
    SaleViewSet,
)

router = DefaultRouter()
router.register("registers", CashRegisterViewSet)
router.register("shifts", CashierShiftViewSet)
router.register("sales", SaleViewSet)
router.register("returns", ReturnViewSet)

urlpatterns = router.urls
