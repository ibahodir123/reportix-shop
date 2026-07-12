from rest_framework.routers import DefaultRouter

from .views import (
    ReceiptViewSet,
    StockMovementViewSet,
    StockViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()
router.register("warehouses", WarehouseViewSet)
router.register("stocks", StockViewSet)
router.register("movements", StockMovementViewSet)
router.register("receipts", ReceiptViewSet)

urlpatterns = router.urls
