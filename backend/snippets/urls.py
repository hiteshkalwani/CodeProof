from rest_framework.routers import DefaultRouter

from snippets.views import SnippetViewSet

router = DefaultRouter(trailing_slash=True)
router.register("snippets", SnippetViewSet, basename="snippet")
urlpatterns = router.urls
