from django.db.models import F

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import WalletUser

from .models import Notification
from .serializers import NotificationSerializer
from .services import mark_all_read, mark_read

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _get_wallet_user(request) -> WalletUser | None:
    auth = JWTAuthentication()
    try:
        raw = auth.get_raw_token(auth.get_header(request))
        token = auth.get_validated_token(raw)
        return WalletUser.objects.get(address=token.get("address", "").lower())
    except Exception:
        return None


def _paginate(qs, request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(MAX_PAGE_SIZE, max(1, int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    count = qs.count()
    offset = (page - 1) * page_size
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "has_next": offset + page_size < count,
        "results": qs[offset: offset + page_size],
    }


class NotificationListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        qs = Notification.objects.filter(recipient=user).select_related("actor", "recipient").order_by(
            F("read_at").asc(nulls_first=True), "-created_at"
        )
        page = _paginate(qs, request)
        return Response(
            {
                "count": page["count"],
                "page": page["page"],
                "page_size": page["page_size"],
                "has_next": page["has_next"],
                "results": NotificationSerializer(page["results"], many=True).data,
            }
        )


class UnreadCountView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        count = Notification.objects.filter(recipient=user, read_at__isnull=True).count()
        return Response({"unread_count": count})


class NotificationReadView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            notification = Notification.objects.select_related("actor").get(pk=pk, recipient=user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        mark_read(notification)
        return Response(NotificationSerializer(notification).data)


class MarkAllReadView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        updated = mark_all_read(user)
        return Response({"updated": updated})
