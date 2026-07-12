from rest_framework.routers import DefaultRouter

from .views import StockMovementViewSet, StockViewSet, WarehouseViewSet

router = DefaultRouter()
router.register("warehouses", WarehouseViewSet)
router.register("stocks", StockViewSet)
router.register("movements", StockMovementViewSet)

urlpatterns = router.urls
