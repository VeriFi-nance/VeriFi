from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from accounts.models import WalletUser
from .models import Post, Claim, HardClaim, Asset, OHLCData, Community, CommunityMembership, AssetSubscription, ClaimMarket, ClaimStake
from .serializers import PostSerializer, ClaimInputSerializer, HardClaimInputSerializer, HardClaimSerializer, AssetSerializer, CommunitySerializer, CommunityMembershipSerializer
from .claim_extraction import rule_based_claims_from_prompt
from django.shortcuts import get_object_or_404
from .resolution import CONTRACT_VERSION, ResolutionError, preview_resolution, resolve_hard_claim
from . import rep_market
from accounts.energy import grant_energy, spend, CLAIM_ENERGY_COST

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _posts_queryset():
    return (
        Post.objects.select_related("author", "author__profitability")
        .prefetch_related(
            "claims",
            Prefetch(
                "hard_claims",
                HardClaim.objects.select_related("author", "author__profitability").prefetch_related(
                    "events"
                ),
            ),
        )
        .order_by("-created_at")
    )


def _filter_posts_queryset(qs, request):
    community_id = request.query_params.get("community")
    if community_id:
        qs = qs.filter(community_id=community_id)
        community = get_object_or_404(Community, id=community_id)
        if community.privacy_type == Community.PrivacyType.PRIVATE:
            user = _get_wallet_user(request)
            if not user or not CommunityMembership.objects.filter(
                community=community, user=user, status=CommunityMembership.Status.APPROVED
            ).exists():
                return None, Response(
                    {"detail": "You must be an approved member to view this community's posts."},
                    status=status.HTTP_403_FORBIDDEN,
                )
    else:
        qs = qs.filter(community__isnull=True)

    feed_type = request.query_params.get("feed")
    if feed_type == "following":
        user = _get_wallet_user(request)
        if user:
            following_ids = user.following_set.values_list("following_id", flat=True)
            qs = qs.filter(author_id__in=following_ids)
        else:
            return None, Response(
                {"detail": "Authentication required for following feed."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

    return qs, None


def _paginate_queryset(qs, request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = min(
            MAX_PAGE_SIZE,
            max(1, int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))),
        )
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE

    count = qs.count()
    offset = (page - 1) * page_size
    results = qs[offset : offset + page_size]
    has_next = offset + page_size < count
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "results": results,
    }


def _can_view_post(post, request) -> bool | Response:
    if not post.community_id:
        return True

    community = post.community
    if community.privacy_type != Community.PrivacyType.PRIVATE:
        return True

    user = _get_wallet_user(request)
    if user and CommunityMembership.objects.filter(
        community=community, user=user, status=CommunityMembership.Status.APPROVED
    ).exists():
        return True

    return Response(
        {"detail": "You must be an approved member to view this post."},
        status=status.HTTP_403_FORBIDDEN,
    )


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
        qs, error_response = _filter_posts_queryset(_posts_queryset(), request)
        if error_response is not None:
            return error_response

        page = _paginate_queryset(qs, request)
        return Response(
            {
                "count": page["count"],
                "page": page["page"],
                "page_size": page["page_size"],
                "has_next": page["has_next"],
                "results": PostSerializer(page["results"], many=True).data,
            }
        )

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
                membership = CommunityMembership.objects.filter(community=community_obj, user=user).first()
                if membership and membership.status == CommunityMembership.Status.BANNED:
                    return Response({"detail": "You are banned from this community."}, status=status.HTTP_403_FORBIDDEN)
                
                if community_obj.privacy_type == Community.PrivacyType.PRIVATE:
                    if not membership or membership.status != CommunityMembership.Status.APPROVED:
                        return Response({"detail": "You must be an approved member to post in this private community."}, status=status.HTTP_403_FORBIDDEN)
                
                if community_obj.post_permission == Community.PostPermission.CREATOR_ONLY and user != community_obj.creator:
                    return Response({"detail": "Only the community creator can post in this community."}, status=status.HTTP_403_FORBIDDEN)
            except Community.DoesNotExist:
                return Response({"detail": f"Community {community_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        claims_data = request.data.get("claims", [])
        serializer = ClaimInputSerializer(data=claims_data, many=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        hard_claims_data = request.data.get("hard_claims", [])

        with transaction.atomic():
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
            
            for hc_data in hard_claims_data:
                hc_serializer = HardClaimInputSerializer(data=hc_data)
                if not hc_serializer.is_valid():
                    transaction.set_rollback(True)
                    return Response(hc_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                valid_hc = hc_serializer.validated_data

                try:
                    asset = Asset.objects.get(id=valid_hc["asset_id"])
                except Asset.DoesNotExist:
                    transaction.set_rollback(True)
                    return Response({"detail": "Invalid asset reference."}, status=status.HTTP_400_BAD_REQUEST)
                
                market_block = hc_data.get("market") if isinstance(hc_data, dict) else None
                if market_block is not None:
                    try:
                        m_side = str(market_block.get("side", "")).upper()
                        m_stake = float(market_block.get("stake_rep", 0))
                    except (TypeError, ValueError):
                        transaction.set_rollback(True)
                        return Response({"detail": "Invalid market block."}, status=status.HTTP_400_BAD_REQUEST)
                    if m_side not in ("YES", "NO"):
                        transaction.set_rollback(True)
                        return Response({"detail": "market.side must be YES or NO."}, status=status.HTTP_400_BAD_REQUEST)
                    if not (rep_market.CREATOR_MIN_STAKE <= m_stake <= rep_market.CREATOR_MAX_STAKE):
                        transaction.set_rollback(True)
                        return Response(
                            {"detail": f"market.stake_rep must be in [{rep_market.CREATOR_MIN_STAKE}, {rep_market.CREATOR_MAX_STAKE}]."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if user.rep < rep_market.LISTING_FEE + m_stake:
                        transaction.set_rollback(True)
                        return Response({"detail": "Insufficient rep for listing fee + stake."}, status=status.HTTP_400_BAD_REQUEST)
                    if not spend(user, CLAIM_ENERGY_COST):
                        transaction.set_rollback(True)
                        return Response({"detail": "Insufficient energy to create market."}, status=status.HTTP_400_BAD_REQUEST)
                else:
                    m_side = None
                    m_stake = None
                
                try:
                    hard_claim = HardClaim.objects.create(
                        author=user,
                        post=post,
                        community=community_obj,
                        asset=asset,
                        direction=valid_hc.get("direction", ""),
                        percentage=valid_hc["percentage"],
                        until=valid_hc["until"],
                        status=valid_hc.get("status", "undetermined"),
                    )
                    from .models import HardClaimEvent
                    HardClaimEvent.objects.create(
                        hard_claim=hard_claim,
                        event_type=HardClaimEvent.EventType.CREATION,
                        details={}
                    )
                    if market_block is not None:
                        rep_market.init_market(hard_claim, user, m_side, m_stake)
                except rep_market.MarketError as e:
                    transaction.set_rollback(True)
                    return Response({"detail": f"market: {e}"}, status=status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    transaction.set_rollback(True)
                    return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PostSerializer(post).data, status=status.HTTP_201_CREATED)


class PostDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            post = _posts_queryset().get(pk=pk)
        except Post.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        permission = _can_view_post(post, request)
        if isinstance(permission, Response):
            return permission

        return Response(PostSerializer(post).data)


class ExtractClaimsView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "content is required."}, status=status.HTTP_400_BAD_REQUEST)

        claims = rule_based_claims_from_prompt(content)
        return Response({"version": CONTRACT_VERSION, "claims": [c.to_dict() for c in claims]})
    
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
                membership = CommunityMembership.objects.filter(community=community_obj, user=user).first()
                if membership and membership.status == CommunityMembership.Status.BANNED:
                    return Response({"detail": "You are banned from this community."}, status=status.HTTP_403_FORBIDDEN)

                if community_obj.privacy_type == Community.PrivacyType.PRIVATE:
                    if not membership or membership.status != CommunityMembership.Status.APPROVED:
                        return Response({"detail": "You must be an approved member to post in this private community."}, status=status.HTTP_403_FORBIDDEN)
                
                if community_obj.post_permission == Community.PostPermission.CREATOR_ONLY and user != community_obj.creator:
                    return Response({"detail": "Only the community creator can post claims in this community."}, status=status.HTTP_403_FORBIDDEN)
            except Community.DoesNotExist:
                return Response({"detail": f"Community {community_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        # Optional Model G market block.
        market_block = request.data.get("market") if isinstance(request.data, dict) else None
        if market_block is not None:
            try:
                m_side = str(market_block.get("side", "")).upper()
                m_stake = float(market_block.get("stake_rep", 0))
            except (TypeError, ValueError):
                return Response({"detail": "Invalid market block."}, status=status.HTTP_400_BAD_REQUEST)
            if m_side not in ("YES", "NO"):
                return Response({"detail": "market.side must be YES or NO."}, status=status.HTTP_400_BAD_REQUEST)
            if not (rep_market.CREATOR_MIN_STAKE <= m_stake <= rep_market.CREATOR_MAX_STAKE):
                return Response(
                    {"detail": f"market.stake_rep must be in [{rep_market.CREATOR_MIN_STAKE}, {rep_market.CREATOR_MAX_STAKE}]."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if user.rep < rep_market.LISTING_FEE + m_stake:
                return Response({"detail": "Insufficient rep for listing fee + stake."}, status=status.HTTP_400_BAD_REQUEST)
            if not spend(user, CLAIM_ENERGY_COST):
                return Response({"detail": "Insufficient energy to create market."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            m_side = None
            m_stake = None

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
            if market_block is not None:
                rep_market.init_market(hard_claim, user, m_side, m_stake)
        except rep_market.MarketError as e:
            return Response({"detail": f"market: {e}"}, status=status.HTTP_400_BAD_REQUEST)
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


class HardClaimDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            hard_claim = HardClaim.objects.get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if hard_claim.community_id:
            community = hard_claim.community
            if community.privacy_type == Community.PrivacyType.PRIVATE:
                user = _get_wallet_user(request)
                if not user or not CommunityMembership.objects.filter(
                    community=community,
                    user=user,
                    status=CommunityMembership.Status.APPROVED,
                ).exists():
                    return Response(
                        {"detail": "You must be an approved member to view this claim."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

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
        # get_ohlc_data requires aligned UTC datetime objects
        from datetime import datetime, timezone
        start_time = datetime.combine(hard_claim.created_at.date(), datetime.min.time(), tzinfo=timezone.utc)
        end_time = datetime.combine(hard_claim.until, datetime.min.time(), tzinfo=timezone.utc)

        # Get or fetch OHLC data
        from .ohlc_fetcher import get_ohlc_data, OHLCFetchError
        try:
            ohlc_rows = get_ohlc_data(asset, start_time, end_time)
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
                "date": row.timestamp.isoformat(),
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
        post_permission = request.data.get("post_permission", Community.PostPermission.ALL)
        
        if not name:
            return Response({"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        community = Community.objects.create(
            name=name,
            description=description,
            creator=user,
            privacy_type=privacy_type,
            post_permission=post_permission
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

    def patch(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        community = get_object_or_404(Community, pk=pk)
        if community.creator != user:
            return Response({"detail": "Only the creator can update community settings."}, status=status.HTTP_403_FORBIDDEN)

        allowed_fields = {"post_permission"}
        updated = False
        for field in allowed_fields:
            if field in request.data:
                value = request.data[field]
                if field == "post_permission" and value not in (Community.PostPermission.ALL, Community.PostPermission.CREATOR_ONLY):
                    return Response({"detail": f"Invalid value for {field}."}, status=status.HTTP_400_BAD_REQUEST)
                setattr(community, field, value)
                updated = True

        if updated:
            community.save()
        return Response(CommunitySerializer(community).data)

class CommunityJoinView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        community = get_object_or_404(Community, pk=pk)
        
        membership = CommunityMembership.objects.filter(community=community, user=user).first()
        if membership:
            if membership.status == CommunityMembership.Status.BANNED:
                return Response({"detail": "You are banned from this community."}, status=status.HTTP_403_FORBIDDEN)
            return Response({"detail": f"Already have a membership with status: {membership.status}."}, status=status.HTTP_400_BAD_REQUEST)
            
        membership = CommunityMembership.objects.create(
            community=community,
            user=user,
            status=CommunityMembership.Status.APPROVED if community.privacy_type == Community.PrivacyType.PUBLIC else CommunityMembership.Status.PENDING
        )
            
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

class CommunityBanView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        community = get_object_or_404(Community, pk=pk)
        if community.creator != user:
            return Response({"detail": "Only the community creator can ban members."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        if target_user == user:
            return Response({"detail": "You cannot ban yourself."}, status=status.HTTP_400_BAD_REQUEST)

        membership, _ = CommunityMembership.objects.get_or_create(
            community=community,
            user=target_user
        )
        membership.status = CommunityMembership.Status.BANNED
        membership.save()
        return Response(CommunityMembershipSerializer(membership).data)

class CommunityMemberListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        community = get_object_or_404(Community, pk=pk)
        
        if community.privacy_type == Community.PrivacyType.PRIVATE:
            user = _get_wallet_user(request)
            if not user or (community.creator != user and not CommunityMembership.objects.filter(community=community, user=user, status=CommunityMembership.Status.APPROVED).exists()):
                return Response({"detail": "You must be a member to view this list."}, status=status.HTTP_403_FORBIDDEN)
                
        memberships = CommunityMembership.objects.filter(community=community, status=CommunityMembership.Status.APPROVED).order_by('created_at')
        return Response(CommunityMembershipSerializer(memberships, many=True).data)

from django.core.cache import cache as django_cache
import time

RESOLVE_COOLDOWN_SECONDS = 3600  # 1 hour

class PositionResolveView(APIView):
    """
    GET  → returns cooldown metadata for the position (author-only).
    POST → attempts to resolve a single PENDING/ACTIVE position (author-only, 1×/hour).
    """
    authentication_classes = []
    permission_classes = []

    def _cooldown_data(self, cache_key):
        last_run = django_cache.get(cache_key)
        if last_run:
            next_allowed = last_run + RESOLVE_COOLDOWN_SECONDS
            remaining = max(0, int(next_allowed - time.time()))
        else:
            next_allowed = None
            remaining = 0
        return last_run, next_allowed, remaining

    def get(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        position = get_object_or_404(Position, pk=pk)
        if position.author != user:
            return Response({"detail": "Only the position author can view resolve status."}, status=status.HTTP_403_FORBIDDEN)

        last_run, next_allowed, remaining = self._cooldown_data(f"resolve_position:{pk}")
        return Response({"last_run": last_run, "next_allowed": next_allowed, "remaining_seconds": remaining})

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        position = get_object_or_404(Position, pk=pk)
        if position.author != user:
            return Response({"detail": "Only the position author can trigger resolution."}, status=status.HTTP_403_FORBIDDEN)

        if position.status not in (Position.Status.PENDING, Position.Status.ACTIVE):
            return Response(
                {"detail": f"Position is already resolved (status: {position.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"resolve_position:{pk}"
        last_run = django_cache.get(cache_key)
        now_ts = time.time()

        if last_run and (now_ts - last_run) < RESOLVE_COOLDOWN_SECONDS:
            remaining = int(RESOLVE_COOLDOWN_SECONDS - (now_ts - last_run))
            return Response(
                {
                    "detail": "Rate limit exceeded. Try again later.",
                    "remaining_seconds": remaining,
                    "last_run": last_run,
                    "next_allowed": last_run + RESOLVE_COOLDOWN_SECONDS,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Run resolution for this single position
        from .position_resolution import _resolve_pending, _resolve_active
        from .profitability import recalculate_profitability
        now = timezone.now()
        try:
            if position.status == Position.Status.PENDING:
                _resolve_pending(position, now)
            else:
                _resolve_active(position, now)
        except Exception as e:
            return Response({"detail": f"Resolution failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Record rate-limit timestamp
        django_cache.set(cache_key, now_ts, timeout=RESOLVE_COOLDOWN_SECONDS)

        # Recalculate profitability in case the position resolved
        position.refresh_from_db()
        recalculate_profitability(user)

        return Response({
            "position": PositionSerializer(position).data,
            "last_run": now_ts,
            "next_allowed": now_ts + RESOLVE_COOLDOWN_SECONDS,
            "remaining_seconds": RESOLVE_COOLDOWN_SECONDS,
        })

from .models import Position, PositionEvent
from .serializers import PositionSerializer, PositionInputSerializer
from .resolution import fetch_current_price
from django.utils import timezone


class PositionListCreateView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return []
        return super().get_permissions()

    def get(self, request):
        community_id = request.query_params.get("community")
        if not community_id:
            return Response({"detail": "community parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        community = get_object_or_404(Community, pk=community_id)
        
        # Privacy check
        if community.privacy_type == Community.PrivacyType.PRIVATE:
            user = _get_wallet_user(request)
            if not user or (community.creator != user and not CommunityMembership.objects.filter(community=community, user=user, status=CommunityMembership.Status.APPROVED).exists()):
                return Response({"detail": "You must be an approved member to view positions in this private community."}, status=status.HTTP_403_FORBIDDEN)
                
        positions = Position.objects.filter(community=community).order_by("-created_at")
        return Response(PositionSerializer(positions, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = PositionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        community = get_object_or_404(Community, pk=data["community_id"])
        
        # Permission checks
        membership = CommunityMembership.objects.filter(community=community, user=user).first()
        if membership and membership.status == CommunityMembership.Status.BANNED:
            return Response({"detail": "You are banned from this community."}, status=status.HTTP_403_FORBIDDEN)

        if community.privacy_type == Community.PrivacyType.PRIVATE:
            if not membership or membership.status != CommunityMembership.Status.APPROVED:
                return Response({"detail": "You must be an approved member to post positions in this private community."}, status=status.HTTP_403_FORBIDDEN)
                
        if community.post_permission == Community.PostPermission.CREATOR_ONLY and user != community.creator:
            return Response({"detail": "Only the creator can post in this community."}, status=status.HTTP_403_FORBIDDEN)

        asset = get_object_or_404(Asset, pk=data["asset_id"])
        
        position = Position.objects.create(
            author=user,
            community=community,
            asset=asset,
            direction=data["direction"],
            entry_price=data["entry_price"],
            entry_interval=data["entry_interval"],
            stop_loss=data["stop_loss"],
            take_profit=data["take_profit"],
            lifetime=data["lifetime"],
            status=Position.Status.PENDING
        )
        
        PositionEvent.objects.create(
            position=position,
            event_type=PositionEvent.EventType.CREATION,
            details={"message": "Position created"}
        )

        # Observer Pattern: subscribe this position to the asset
        AssetSubscription.objects.create(asset=asset, position=position)
        
        return Response(PositionSerializer(position).data, status=status.HTTP_201_CREATED)

class PositionCloseView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        position = get_object_or_404(Position, pk=pk)
        
        if position.author != user:
            return Response({"detail": "Only the author can close this position."}, status=status.HTTP_403_FORBIDDEN)
            
        if position.status not in [Position.Status.ACTIVE, Position.Status.PENDING]:
            return Response({"detail": f"Position cannot be closed manually. Current status: {position.status}."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if position.status == Position.Status.PENDING:
                position.status = Position.Status.CLOSED_EARLY
                position.exit_price = None
                position.pnl_percentage = 0.0
                position.save()
                
                PositionEvent.objects.create(
                    position=position,
                    event_type=PositionEvent.EventType.MANUAL_CLOSE,
                    details={
                        "message": "Manually cancelled by author before entry"
                    }
                )
            else:
                now = timezone.now()
                current_price, source_url = fetch_current_price(position.asset, now)
                
                position.exit_price = current_price
                
                if position.direction == Position.Direction.LONG:
                    position.pnl_percentage = ((current_price - position.entry_price) / position.entry_price) * 100
                else:
                    position.pnl_percentage = ((position.entry_price - current_price) / position.entry_price) * 100
                    
                position.status = Position.Status.CLOSED_EARLY
                position.save()
                
                PositionEvent.objects.create(
                    position=position,
                    event_type=PositionEvent.EventType.MANUAL_CLOSE,
                    details={
                        "exit_price": current_price,
                        "pnl_percentage": position.pnl_percentage,
                        "source": source_url,
                        "message": "Manually closed by author"
                    }
                )
            
            # Observer Pattern: unsubscribe from asset on manual close
            AssetSubscription.objects.filter(position=position).delete()

            from .profitability import recalculate_profitability
            recalculate_profitability(user)

            return Response(PositionSerializer(position).data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": f"Failed to close position: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ---------------------------------------------------------------------------
# Model G — reputation market endpoints
# ---------------------------------------------------------------------------


def _serialize_market(market: ClaimMarket, viewer: WalletUser | None) -> dict:
    your_stake = None
    if viewer is not None:
        st = ClaimStake.objects.filter(market=market, user=viewer).first()
        if st is not None:
            your_stake = {
                "side": st.side,
                "shares": st.shares,
                "rep_paid_gross": st.rep_paid_gross,
                "entry_price": st.entry_price,
                "is_creator": st.is_creator,
                "locked_payout_if_win": st.shares,
            }
    return {
        "claim_id": market.hard_claim_id,
        "yes_price": rep_market.yes_price(market),
        "y_reserve": market.y_reserve,
        "n_reserve": market.n_reserve,
        "yes_outstanding": market.yes_outstanding,
        "no_outstanding": market.no_outstanding,
        "escrow": market.escrow,
        "total_burned": market.total_burned,
        "creator_side": market.creator_side,
        "creator_stake_rep": market.creator_stake_rep,
        "listing_fee_burned": market.listing_fee_burned,
        "resolved": market.resolved,
        "refunded_trivial": market.refunded_trivial,
        "stake_count": market.stakes.count(),
        "your_stake": your_stake,
        "trader_stake": rep_market.TRADER_STAKE,
        "burn_fee": rep_market.BURN_FEE,
        "min_loser_voters": rep_market.MIN_LOSER_VOTERS,
        "min_total_voters": rep_market.MIN_TOTAL_VOTERS,
    }


class HardClaimMarketView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            market = ClaimMarket.objects.get(hard_claim_id=pk)
        except ClaimMarket.DoesNotExist:
            return Response({"detail": "No market."}, status=status.HTTP_404_NOT_FOUND)
        viewer = _get_wallet_user(request)
        return Response(_serialize_market(market, viewer))


class HardClaimMarketCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            hard_claim = HardClaim.objects.get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Claim not found."}, status=status.HTTP_404_NOT_FOUND)
        if hard_claim.author_id != user.pk:
            return Response({"detail": "Only the claim author can create its market."}, status=status.HTTP_403_FORBIDDEN)
        side = str(request.data.get("side", "")).upper()
        try:
            stake_rep = float(request.data.get("stake_rep", 0))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid stake_rep."}, status=status.HTTP_400_BAD_REQUEST)
        if side not in ("YES", "NO"):
            return Response({"detail": "side must be YES or NO."}, status=status.HTTP_400_BAD_REQUEST)
        if not (rep_market.CREATOR_MIN_STAKE <= stake_rep <= rep_market.CREATOR_MAX_STAKE):
            return Response(
                {"detail": f"stake_rep must be in [{rep_market.CREATOR_MIN_STAKE}, {rep_market.CREATOR_MAX_STAKE}]."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if hasattr(hard_claim, "market"):
            return Response({"detail": "Market already exists."}, status=status.HTTP_409_CONFLICT)
        if user.rep < rep_market.LISTING_FEE + stake_rep:
            return Response({"detail": "Insufficient rep."}, status=status.HTTP_400_BAD_REQUEST)
        if not spend(user, CLAIM_ENERGY_COST):
            return Response({"detail": "Insufficient energy."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            market = rep_market.init_market(hard_claim, user, side, stake_rep)
        except rep_market.MarketError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize_market(market, user), status=status.HTTP_201_CREATED)


class HardClaimMarketBuyView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            market = ClaimMarket.objects.get(hard_claim_id=pk)
        except ClaimMarket.DoesNotExist:
            return Response({"detail": "No market."}, status=status.HTTP_404_NOT_FOUND)
        if market.resolved:
            return Response({"detail": "Market resolved."}, status=status.HTTP_400_BAD_REQUEST)
        side = str(request.data.get("side", "")).upper()
        if side not in ("YES", "NO"):
            return Response({"detail": "side must be YES or NO."}, status=status.HTTP_400_BAD_REQUEST)
        if user.rep < rep_market.TRADER_STAKE:
            return Response({"detail": "Insufficient rep."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            stake = rep_market.buy(market, user, side)
        except rep_market.MarketError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "market": _serialize_market(market, user),
                "stake": {
                    "side": stake.side,
                    "shares": stake.shares,
                    "rep_paid_gross": stake.rep_paid_gross,
                    "rep_paid_net": stake.rep_paid_net,
                    "entry_price": stake.entry_price,
                    "locked_payout_if_win": stake.shares,
                },
                "user_rep": user.rep,
                "user_energy": user.energy,
            },
            status=status.HTTP_201_CREATED,
        )


class HardClaimMarketPreviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            market = ClaimMarket.objects.get(hard_claim_id=pk)
        except ClaimMarket.DoesNotExist:
            return Response({"detail": "No market."}, status=status.HTTP_404_NOT_FOUND)
        side = request.query_params.get("side", "").upper()
        if side not in ("YES", "NO"):
            return Response({"detail": "side must be YES or NO."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            preview = rep_market.preview_buy(market, side, rep_market.TRADER_STAKE)
        except rep_market.MarketError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "side": side,
                "rep_amount": rep_market.TRADER_STAKE,
                "shares": preview.shares,
                "entry_price": preview.entry_price,
                "locked_payout_if_win": preview.locked_payout_if_win,
                "new_yes_price": preview.new_yes_price,
            }
        )


