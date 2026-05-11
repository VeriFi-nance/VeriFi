from django.urls import path
from .views import RegisterView, ChallengeView, LoginView, FollowToggleView, ProfileView

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("challenge/", ChallengeView.as_view()),
    path("login/", LoginView.as_view()),
    path("follow/", FollowToggleView.as_view()),
    path("profile/<str:address>/", ProfileView.as_view()),
]
