from django.urls import path
from .views import PostListCreateView, ExtractClaimsView

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post-list-create"),
    path("extract-claims/", ExtractClaimsView.as_view(), name="extract-claims"),
]
