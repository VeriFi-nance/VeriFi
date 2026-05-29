from django.urls import path
from .views import (
    HardClaimView, HardClaimResolveView, HardClaimChartDataView,
    PostListCreateView, ExtractClaimsView, AssetListView,
    CommunityListView, CommunityDetailView, CommunityJoinView, CommunityApproveView, CommunityBanView,
    CommunityMemberListView, PositionListCreateView, PositionCloseView, PositionResolveView,
    HardClaimMarketView, HardClaimMarketCreateView, HardClaimMarketBuyView, HardClaimMarketPreviewView,
)

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post-list-create"),
    path("extract-claims/", ExtractClaimsView.as_view(), name="extract-claims"),
    path("hard-claims/", HardClaimView.as_view(), name="hard-claims"),
    path("hard-claims/<int:pk>/update-status/", HardClaimView.as_view(), name="hard-claim-update-status"),
    path("hard-claims/<int:pk>/resolve/", HardClaimResolveView.as_view(), name="hard-claim-resolve"),
    path("hard-claims/<int:pk>/chart-data/", HardClaimChartDataView.as_view(), name="hard-claim-chart-data"),
    path("hard-claims/<int:pk>/market/", HardClaimMarketView.as_view(), name="hard-claim-market"),
    path("hard-claims/<int:pk>/market/create/", HardClaimMarketCreateView.as_view(), name="hard-claim-market-create"),
    path("hard-claims/<int:pk>/market/buy/", HardClaimMarketBuyView.as_view(), name="hard-claim-market-buy"),
    path("hard-claims/<int:pk>/market/preview/", HardClaimMarketPreviewView.as_view(), name="hard-claim-market-preview"),
    path("assets/", AssetListView.as_view(), name="assets-list"),
    path("communities/", CommunityListView.as_view(), name="community-list"),
    path("communities/<int:pk>/", CommunityDetailView.as_view(), name="community-detail"),
    path("communities/<int:pk>/join/", CommunityJoinView.as_view(), name="community-join"),
    path("communities/<int:pk>/approve/<str:user_address>/", CommunityApproveView.as_view(), name="community-approve"),
    path("communities/<int:pk>/ban/<str:user_address>/", CommunityBanView.as_view(), name="community-ban"),
    path("communities/<int:pk>/members/", CommunityMemberListView.as_view(), name="community-members"),
    path("positions/", PositionListCreateView.as_view(), name="position-list-create"),
    path("positions/<int:pk>/close/", PositionCloseView.as_view(), name="position-close"),
    path("positions/<int:pk>/resolve/", PositionResolveView.as_view(), name="position-resolve"),
]
