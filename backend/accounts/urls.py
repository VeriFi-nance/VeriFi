from django.urls import path
from .views import RegisterView, ChallengeView, LoginView

urlpatterns = [
    path("register/", RegisterView.as_view()),
    path("challenge/", ChallengeView.as_view()),
    path("login/", LoginView.as_view()),
]
