from django.urls import path
from .views import HardClaimView, PostListCreateView, ExtractClaimsView, AssetListView

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post-list-create"),
    path("extract-claims/", ExtractClaimsView.as_view(), name="extract-claims"),
    path("hard-claims/", HardClaimView.as_view(), name="hard-claims"),
    path("hard-claims/<int:pk>/update-status/", HardClaimView.as_view(), name="hard-claim-update-status"),
    path("assets/", AssetListView.as_view(), name="assets-list"),
]
