from django.urls import path
from .views import (
    RegisterView, ChallengeView, LoginView, FollowToggleView, ProfileView,
    ProfitabilityView, UpdateProfileView, AccountExistsView, OtpStartView, OtpCheckView,
)

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("challenge/", ChallengeView.as_view()),
    path("login/", LoginView.as_view()),
    path("exists/", AccountExistsView.as_view()),
    path("otp/start/", OtpStartView.as_view()),
    path("otp/check/", OtpCheckView.as_view()),
    path("follow/", FollowToggleView.as_view()),
    path("profile/update/", UpdateProfileView.as_view()),
    path("profile/<str:lookup>/", ProfileView.as_view()),
    path("profitability/<str:address>/", ProfitabilityView.as_view()),
]
