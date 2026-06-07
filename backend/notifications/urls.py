from django.urls import path

from .views import MarkAllReadView, NotificationListView, NotificationReadView, UnreadCountView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", UnreadCountView.as_view(), name="notification-unread-count"),
    path("<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
    path("mark-all-read/", MarkAllReadView.as_view(), name="notification-mark-all-read"),
]
