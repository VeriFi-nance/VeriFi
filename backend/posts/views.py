from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.models import WalletUser
from .models import Post, Claim, HardClaim, Asset, OHLCData, Community, CommunityMembership
from .serializers import PostSerializer, ClaimInputSerializer, HardClaimInputSerializer, HardClaimSerializer, AssetSerializer, CommunitySerializer, CommunityMembershipSerializer
from django.shortcuts import get_object_or_404
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
        qs = Post.objects.prefetch_related("claims", "hard_claims").order_by("-created_at")
        
        community_id = request.query_params.get("community")
        if community_id:
            qs = qs.filter(community_id=community_id)
            community = get_object_or_404(Community, id=community_id)
            if community.privacy_type == Community.PrivacyType.PRIVATE:
                user = _get_wallet_user(request)
                if not user or not CommunityMembership.objects.filter(community=community, user=user, status=CommunityMembership.Status.APPROVED).exists():
                    return Response({"detail": "You must be an approved member to view this community's posts."}, status=status.HTTP_403_FORBIDDEN)
        else:
            qs = qs.filter(community__isnull=True)
            
        feed_type = request.query_params.get("feed")
        if feed_type == "following":
            user = _get_wallet_user(request)
            if user:
                following_addresses = user.following_set.values_list("following__address", flat=True)
                qs = qs.filter(author__address__in=following_addresses)
            else:
                return Response({"detail": "Authentication required for following feed."}, status=status.HTTP_401_UNAUTHORIZED)
                
        return Response(PostSerializer(qs, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "content is required."}, status=status.HTTP_400_BAD_REQUEST)
        if len(content) > 500:
            return Response({"detail": "content exceeds 500 characters."}, status=status.HTTP_400_BAD_REQUEST)

        community_id = request.data.get("community_id")
        community_obj = None
        if community_id is not None:
            try:
                community_obj = Community.objects.get(id=community_id)
                if community_obj.privacy_type == Community.PrivacyType.PRIVATE:
                    if not CommunityMembership.objects.filter(community=community_obj, user=user, status=CommunityMembership.Status.APPROVED).exists():
                        return Response({"detail": "You must be an approved member to post in this private community."}, status=status.HTTP_403_FORBIDDEN)
            except Community.DoesNotExist:
                return Response({"detail": f"Community {community_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        claims_data = request.data.get("claims", [])
        serializer = ClaimInputSerializer(data=claims_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        post = Post.objects.create(author=user, content=content, community=community_obj)
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
        
        community_id = request.query_params.get("community")
        if community_id:
            qs = qs.filter(community_id=community_id)
            community = get_object_or_404(Community, id=community_id)
            if community.privacy_type == Community.PrivacyType.PRIVATE:
                user = _get_wallet_user(request)
                if not user or not CommunityMembership.objects.filter(community=community, user=user, status=CommunityMembership.Status.APPROVED).exists():
                    return Response({"detail": "You must be an approved member to view this community's claims."}, status=status.HTTP_403_FORBIDDEN)
        else:
            qs = qs.filter(community__isnull=True)

        address = request.query_params.get("address", "").strip().lower()
        if address:
            qs = qs.filter(author__address=address)
            
        feed_type = request.query_params.get("feed")
        if feed_type == "following":
            user = _get_wallet_user(request)
            if user:
                following_addresses = user.following_set.values_list("following__address", flat=True)
                qs = qs.filter(author__address__in=following_addresses)
            else:
                return Response({"detail": "Authentication required for following feed."}, status=status.HTTP_401_UNAUTHORIZED)
                
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

        # Resolve optional community reference
        community_obj = None
        community_id = data.get("community_id")
        if community_id is not None:
            try:
                community_obj = Community.objects.get(id=community_id)
                if community_obj.privacy_type == Community.PrivacyType.PRIVATE:
                    if not CommunityMembership.objects.filter(community=community_obj, user=user, status=CommunityMembership.Status.APPROVED).exists():
                        return Response({"detail": "You must be an approved member to post in this private community."}, status=status.HTTP_403_FORBIDDEN)
            except Community.DoesNotExist:
                return Response({"detail": f"Community {community_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        # Create HardClaim object in the database with the given data
        try:
            hard_claim = HardClaim.objects.create(
                author=user,
                post=post_obj,
                community=community_obj,
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


class HardClaimChartDataView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            hard_claim = HardClaim.objects.select_related("asset").get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        asset = hard_claim.asset
        start_date = hard_claim.created_at.date()
        end_date = hard_claim.until

        # Get or fetch OHLC data
        from .ohlc_fetcher import get_ohlc_data, OHLCFetchError
        try:
            ohlc_rows = get_ohlc_data(asset, start_date, end_date)
        except OHLCFetchError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Compute target price
        reference_price = None
        target_price = None
        target_reached_at = None
        hit_days = []
        closest_price = None

        # Try to get resolution details from events
        resolution_event = hard_claim.events.filter(event_type="resolution").first()
        if resolution_event and resolution_event.details:
            details = resolution_event.details
            prices = details.get("prices", {})
            reference_price = prices.get("reference")
            target_price = prices.get("target")
            closest_price = prices.get("closest")
            target_reached_at = details.get("target_reached_at")
            hit_days = details.get("hit_days", [])
        elif ohlc_rows:
            # Not resolved yet — compute from OHLC
            from .resolution import fetch_reference_price, ResolutionError, _round_decimal
            try:
                reference_price, _ = fetch_reference_price(hard_claim)
                reference_price = _round_decimal(reference_price)
            except ResolutionError:
                reference_price = ohlc_rows[0].open

            direction = hard_claim.direction.lower()
            pct = float(hard_claim.percentage)
            if direction == "bullish":
                target_price = _round_decimal(reference_price * (1 + pct / 100))
            else:
                target_price = _round_decimal(reference_price * (1 - pct / 100))

        ohlc_data = [
            {
                "date": row.date.isoformat(),
                "open": row.open,
                "high": row.high,
                "low": row.low,
                "close": row.close,
            }
            for row in ohlc_rows
        ]

        return Response({
            "claim_id": hard_claim.id,
            "asset_symbol": asset.symbol,
            "direction": hard_claim.direction.lower(),
            "reference_price": reference_price,
            "target_price": target_price,
            "percentage": float(hard_claim.percentage),
            "created_at": hard_claim.created_at.isoformat(),
            "until": hard_claim.until.isoformat(),
            "ohlc": ohlc_data,
            "hit_days": hit_days,
            "closest_price": closest_price,
            "target_reached_at": target_reached_at,
        })


class CommunityListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        qs = Community.objects.all().order_by("-created_at")
        return Response(CommunitySerializer(qs, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        name = request.data.get("name")
        description = request.data.get("description", "")
        privacy_type = request.data.get("privacy_type", Community.PrivacyType.PUBLIC)
        
        if not name:
            return Response({"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        community = Community.objects.create(
            name=name,
            description=description,
            creator=user,
            privacy_type=privacy_type
        )
        
        CommunityMembership.objects.create(
            community=community,
            user=user,
            status=CommunityMembership.Status.APPROVED
        )
        
        return Response(CommunitySerializer(community).data, status=status.HTTP_201_CREATED)

class CommunityDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        community = get_object_or_404(Community, pk=pk)
        data = CommunitySerializer(community).data
        
        user = _get_wallet_user(request)
        membership_status = None
        if user:
            membership = CommunityMembership.objects.filter(community=community, user=user).first()
            if membership:
                membership_status = membership.status
                
        data["my_membership_status"] = membership_status
        
        if user and community.creator == user:
            pending_memberships = CommunityMembership.objects.filter(community=community, status=CommunityMembership.Status.PENDING)
            data["pending_requests"] = CommunityMembershipSerializer(pending_memberships, many=True).data
            
        return Response(data)

class CommunityJoinView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        community = get_object_or_404(Community, pk=pk)
        
        membership, created = CommunityMembership.objects.get_or_create(
            community=community,
            user=user,
            defaults={"status": CommunityMembership.Status.APPROVED if community.privacy_type == Community.PrivacyType.PUBLIC else CommunityMembership.Status.PENDING}
        )
        
        if not created:
            return Response({"detail": f"Already have a membership with status: {membership.status}."}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response(CommunityMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

class CommunityApproveView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        community = get_object_or_404(Community, pk=pk)
        if community.creator != user:
            return Response({"detail": "Only the community creator can approve members."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        membership = get_object_or_404(CommunityMembership, community=community, user=target_user)
        
        action = request.data.get("action")
        if action == "approve":
            membership.status = CommunityMembership.Status.APPROVED
            membership.save()
            return Response(CommunityMembershipSerializer(membership).data)
        elif action == "reject":
            membership.delete()
            return Response({"detail": "Request rejected."})
        else:
            return Response({"detail": "Invalid action. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)
