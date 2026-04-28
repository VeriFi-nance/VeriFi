from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import WalletUser
from .models import Post, Claim, HardClaim, Asset
from .serializers import PostSerializer, ClaimInputSerializer, HardClaimInputSerializer, HardClaimSerializer, AssetSerializer
from .resolution import CONTRACT_VERSION, ResolutionError, preview_resolution, resolve_hard_claim


MOCK_CLAIMS = [
    {"text": "Bitcoin will reach $200,000 by end of 2025.", "asset": "BTC", "direction": "bullish"},
    {"text": "Ethereum will outperform the market next quarter.", "asset": "ETH", "direction": "bullish"},
]


def _get_wallet_user(request) -> WalletUser | None:
    auth = JWTAuthentication()
    try:
        raw = auth.get_raw_token(auth.get_header(request))
        token = auth.get_validated_token(raw)
        return WalletUser.objects.get(address=token.get("address", "").lower())
    except Exception:
        return None


def _require_admin_user(request) -> WalletUser | Response:
    user = _get_wallet_user(request)
    if user is None:
        return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
    admin_addresses = {address.lower() for address in settings.ADMIN_ADDRESSES}
    if user.address.lower() not in admin_addresses:
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
    return user


class PostListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        posts = Post.objects.prefetch_related("claims", "hard_claims").all()
        return Response(PostSerializer(posts, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "content is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > 500:
            return Response({"detail": "content exceeds 500 characters."}, status=status.HTTP_400_BAD_REQUEST)

        claims_data = request.data.get("claims", [])
        serializer = ClaimInputSerializer(data=claims_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        post = Post.objects.create(author=user, content=content)
        for claim in serializer.validated_data:
            if claim.get("status") != "rejected":
                Claim.objects.create(
                    post=post,
                    text=claim["text"],
                    asset=claim.get("asset", ""),
                    direction=claim.get("direction", ""),
                    status=Claim.Status.CONFIRMED,
                )

        return Response(PostSerializer(post).data, status=status.HTTP_201_CREATED)


class ExtractClaimsView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        # TODO: integrate LLM claim extraction (#29)
        return Response({"version": CONTRACT_VERSION, "claims": []})
    
class AssetListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        assets = Asset.objects.all().order_by("name")
        return Response(AssetSerializer(assets, many=True).data)

class HardClaimView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        qs = HardClaim.objects.all().order_by("-id")
        address = request.query_params.get("address", "").strip().lower()
        if address:
            qs = qs.filter(author__address=address)
        return Response(HardClaimSerializer(qs, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = HardClaimInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        # Validate that asset exists
        try:
            asset = Asset.objects.get(id=data["asset_id"])
        except Asset.DoesNotExist as e:
            return Response({"detail": f"Invalid reference: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve optional post reference
        post_obj = None
        post_id = data.get("post_id")
        if post_id is not None:
            try:
                post_obj = Post.objects.get(id=post_id)
            except Post.DoesNotExist:
                return Response({"detail": f"Post {post_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        # Create HardClaim object in the database with the given data
        try:
            hard_claim = HardClaim.objects.create(
                author=user,
                post=post_obj,
                asset=asset,
                direction=data.get("direction", ""),
                percentage=data["percentage"],
                until=data["until"],
                status=data.get("status", "undetermined"),
            )
            from .models import HardClaimEvent
            HardClaimEvent.objects.create(
                hard_claim=hard_claim,
                event_type=HardClaimEvent.EventType.CREATION,
                details={}
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(HardClaimSerializer(hard_claim).data, status=status.HTTP_201_CREATED)

    def patch(self, request, pk):
        admin_user = _require_admin_user(request)
        if isinstance(admin_user, Response):
            return admin_user

        try:
            hard_claim = HardClaim.objects.get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        if new_status not in HardClaim.Status.values:
            return Response(
                {"detail": f"Invalid status. Choose from: {HardClaim.Status.values}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        hard_claim.status = new_status
        hard_claim.save()
        return Response(HardClaimSerializer(hard_claim).data)


class HardClaimResolveView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        admin_user = _require_admin_user(request)
        if isinstance(admin_user, Response):
            return admin_user

        try:
            hard_claim = HardClaim.objects.select_related("asset").get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        preview_flag = request.data.get("preview", False)
        preview_only = preview_flag is True or str(preview_flag).lower() in {"1", "true", "yes"}

        try:
            result = preview_resolution(hard_claim) if preview_only else resolve_hard_claim(hard_claim)
        except ResolutionError as exc:
            return Response(exc.to_payload(), status=status.HTTP_400_BAD_REQUEST)

        return Response(result)
