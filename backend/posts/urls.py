from django.urls import path
from .views import HardClaimView, HardClaimResolveView, HardClaimChartDataView, PostListCreateView, ExtractClaimsView, AssetListView

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post-list-create"),
    path("extract-claims/", ExtractClaimsView.as_view(), name="extract-claims"),
    path("hard-claims/", HardClaimView.as_view(), name="hard-claims"),
    path("hard-claims/<int:pk>/update-status/", HardClaimView.as_view(), name="hard-claim-update-status"),
    path("hard-claims/<int:pk>/resolve/", HardClaimResolveView.as_view(), name="hard-claim-resolve"),
    path("hard-claims/<int:pk>/chart-data/", HardClaimChartDataView.as_view(), name="hard-claim-chart-data"),
    path("assets/", AssetListView.as_view(), name="assets-list"),
]
