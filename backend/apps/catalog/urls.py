from rest_framework.routers import DefaultRouter

from .views import BrandViewSet, CategoryViewSet, ProductViewSet, UnitViewSet, VariantViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet)
router.register("brands", BrandViewSet)
router.register("units", UnitViewSet)
router.register("products", ProductViewSet)
router.register("variants", VariantViewSet)

urlpatterns = router.urls
