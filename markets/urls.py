"""
Markets app URL configuration
"""

from django.urls import path
from .views import MarketsPage, markets_api

urlpatterns = [
    path("", MarketsPage.as_view(), name="markets_page"),
    path("api/markets", markets_api, name="markets_api"),
]
