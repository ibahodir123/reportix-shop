from rest_framework.routers import DefaultRouter

from .views import CashierShiftViewSet, CashRegisterViewSet, SaleViewSet

router = DefaultRouter()
router.register("registers", CashRegisterViewSet)
router.register("shifts", CashierShiftViewSet)
router.register("sales", SaleViewSet)

urlpatterns = router.urls
