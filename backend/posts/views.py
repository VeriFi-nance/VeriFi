import json
import logging
from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from accounts.models import WalletUser, ProfileChangeLog
from .models import Post, HardClaim, Asset, Channel, ChannelMembership, AssetSubscription, ClaimMarket, ClaimStake
from .serializers import PostSerializer, HardClaimInputSerializer, HardClaimSerializer, AssetSerializer, ChannelSerializer, ChannelMembershipSerializer
from .claim_extraction import rule_based_claims_from_prompt
from django.shortcuts import get_object_or_404
from .resolution import (
    CONTRACT_VERSION,
    ResolutionError,
    preview_resolution,
    resolve_hard_claim,
    capture_reference_price,
    claim_target_price,
    _normalize_direction_and_value_type,
    reconcile_claim_fields,
)
from . import rep_market
from .signature_verification import verify_claim_signature, verify_position_signature
from accounts.energy import grant_energy, spend, CLAIM_ENERGY_COST
from accounts.serializers import validate_image_upload

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _normalized_claim_fields(direction: str, value_type: str) -> tuple[str, str]:
    return _normalize_direction_and_value_type(direction, value_type)


def _posts_queryset():
    return (
        Post.objects.select_related("author", "author__profitability")
        .prefetch_related(
            Prefetch(
                "hard_claims",
                HardClaim.objects.select_related("author", "author__profitability", "asset").prefetch_related(
                    "events"
                ),
            ),
        )
        .order_by("-created_at")
    )


def _filter_posts_queryset(qs, request):
    channel_id = request.query_params.get("channel")
    if channel_id:
        qs = qs.filter(channel_id=channel_id)
        channel = get_object_or_404(Channel, id=channel_id)
        user = _get_wallet_user(request)
        if not user or (channel.creator != user and not ChannelMembership.objects.filter(
            channel=channel, user=user, status=ChannelMembership.Status.APPROVED
        ).exists()):
            return None, Response(
                {"detail": "You must be an approved member to view this channel's posts."},
                status=status.HTTP_403_FORBIDDEN,
            )
    else:
        qs = qs.filter(channel__isnull=True)

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
    if not post.channel_id:
        return True

    channel = post.channel

    user = _get_wallet_user(request)
    if user and (channel.creator == user or ChannelMembership.objects.filter(
        channel=channel, user=user, status=ChannelMembership.Status.APPROVED
    ).exists()):
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


def _is_channel_moderator(channel, user) -> bool:
    if channel.creator == user:
        return True
    return ChannelMembership.objects.filter(
        channel=channel,
        user=user,
        status=ChannelMembership.Status.APPROVED,
        role__in=[ChannelMembership.Role.OWNER, ChannelMembership.Role.MODERATOR],
    ).exists()


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

        channel_id = request.data.get("channel_id")
        channel_obj = None
        if channel_id is not None:
            try:
                channel_obj = Channel.objects.get(id=channel_id)
                membership = ChannelMembership.objects.filter(channel=channel_obj, user=user).first()
                if membership and membership.status == ChannelMembership.Status.BANNED:
                    return Response({"detail": "You are banned from this channel."}, status=status.HTTP_403_FORBIDDEN)
                
                if channel_obj.creator != user and (not membership or membership.status != ChannelMembership.Status.APPROVED):
                    return Response({"detail": "You must be an approved member to post in this private channel."}, status=status.HTTP_403_FORBIDDEN)
                
                if channel_obj.post_permission == Channel.PostPermission.CREATOR_ONLY and user != channel_obj.creator:
                    return Response({"detail": "Only the channel creator can post in this channel."}, status=status.HTTP_403_FORBIDDEN)
            except Channel.DoesNotExist:
                return Response({"detail": f"Channel {channel_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

        hard_claims_data = request.data.get("hard_claims", [])
        # Under multipart/form-data (image uploads), nested arrays arrive as a
        # JSON-encoded string rather than a parsed list. Decode it here so both
        # JSON and multipart requests reach the same code path.
        if isinstance(hard_claims_data, str):
            if hard_claims_data.strip():
                try:
                    hard_claims_data = json.loads(hard_claims_data)
                except json.JSONDecodeError:
                    return Response({"detail": "hard_claims must be valid JSON."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                hard_claims_data = []
        if not isinstance(hard_claims_data, list):
            return Response({"detail": "hard_claims must be a list."}, status=status.HTTP_400_BAD_REQUEST)

        image_file = request.FILES.get("image")
        if image_file is not None:
            img_error = validate_image_upload(image_file)
            if img_error:
                return Response({"detail": img_error}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            post = Post.objects.create(author=user, content=content, channel=channel_obj, image=image_file)
            
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
                    # Verify claim signature before persisting
                    hc_sig = valid_hc.get("signature", "")
                    hc_claim_payload = valid_hc.get("claim_payload", {})
                    try:
                        verify_claim_signature(
                            user_address=user.address,
                            user_username=user.username,
                            signature=hc_sig,
                            claim_payload=hc_claim_payload,
                            asset_symbol=asset.symbol,
                        )
                    except Exception as sig_exc:
                        transaction.set_rollback(True)
                        from rest_framework.exceptions import ValidationError as DRFValidationError
                        if isinstance(sig_exc, DRFValidationError):
                            return Response(sig_exc.detail, status=status.HTTP_400_BAD_REQUEST)
                        logger.exception("Unexpected error during claim signature verification")
                        return Response({"detail": "Invalid claim signature."}, status=status.HTTP_400_BAD_REQUEST)

                    hc_direction, hc_value_type = _normalized_claim_fields(
                        valid_hc.get("direction", ""),
                        valid_hc.get("value_type", "PERCENTAGE_UP"),
                    )
                    hard_claim = HardClaim.objects.create(
                        author=user,
                        post=post,
                        channel=channel_obj,
                        asset=asset,
                        direction=hc_direction,
                        value_type=hc_value_type,
                        percentage=valid_hc["percentage"],
                        until=valid_hc["until"],
                        status=valid_hc.get("status", "undetermined"),
                        signature=hc_sig,
                        claim_payload=hc_claim_payload,
                    )
                    from .models import HardClaimEvent
                    HardClaimEvent.objects.create(
                        hard_claim=hard_claim,
                        event_type=HardClaimEvent.EventType.CREATION,
                        details={}
                    )
                    try:
                        capture_reference_price(hard_claim)
                    except ResolutionError as exc:
                        logger.warning(
                            "Reference price not captured for claim %s: %s",
                            hard_claim.id,
                            exc.message,
                        )
                    if market_block is not None:
                        rep_market.init_market(hard_claim, user, m_side, m_stake)
                except rep_market.MarketError:
                    transaction.set_rollback(True)
                    logger.exception("Market initialization failed during post creation.")
                    return Response({"detail": "Unable to initialize market."}, status=status.HTTP_400_BAD_REQUEST)
                except Exception:
                    transaction.set_rollback(True)
                    logger.exception("Unexpected error while creating hard claim.")
                    return Response({"detail": "An internal error has occurred."}, status=status.HTTP_400_BAD_REQUEST)

            ProfileChangeLog.objects.create(
                user=user,
                actor=user,
                event_type=ProfileChangeLog.EventType.POST_CREATED,
                summary="Created a post",
                metadata={
                    "post_id": post.id,
                    "channel_id": post.channel_id,
                    "content_preview": post.content[:120],
                },
            )

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

        from datetime import date
        from django.utils import timezone as django_timezone
        from .resolution import resolve_hard_claim, ResolutionError

        for claim in post.hard_claims.all():
            if claim.status == HardClaim.Status.UNDETERMINED and claim.until < date.today():
                try:
                    resolve_hard_claim(claim)
                except ResolutionError:
                    pass

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
        qs = HardClaim.objects.select_related("author", "author__profitability", "asset").order_by("-id")
        
        channel_id = request.query_params.get("channel")
        if channel_id:
            qs = qs.filter(channel_id=channel_id)
            channel = get_object_or_404(Channel, id=channel_id)
            user = _get_wallet_user(request)
            if not user or (channel.creator != user and not ChannelMembership.objects.filter(channel=channel, user=user, status=ChannelMembership.Status.APPROVED).exists()):
                return Response({"detail": "You must be an approved member to view this channel's claims."}, status=status.HTTP_403_FORBIDDEN)
        else:
            qs = qs.filter(channel__isnull=True)

        address = request.query_params.get("address", "").strip().lower()
        if address:
            qs = qs.filter(author__address=address)
            
        username_q = request.query_params.get("username", "").strip()
        if username_q:
            qs = qs.filter(author__username__iexact=username_q)
            
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

        # Resolve optional channel reference
        channel_obj = None
        channel_id = data.get("channel_id")
        if channel_id is not None:
            try:
                channel_obj = Channel.objects.get(id=channel_id)
                membership = ChannelMembership.objects.filter(channel=channel_obj, user=user).first()
                if membership and membership.status == ChannelMembership.Status.BANNED:
                    return Response({"detail": "You are banned from this channel."}, status=status.HTTP_403_FORBIDDEN)

                if channel_obj.creator != user and (not membership or membership.status != ChannelMembership.Status.APPROVED):
                    return Response({"detail": "You must be an approved member to post in this private channel."}, status=status.HTTP_403_FORBIDDEN)
                
                if channel_obj.post_permission == Channel.PostPermission.CREATOR_ONLY and user != channel_obj.creator:
                    return Response({"detail": "Only the channel creator can post claims in this channel."}, status=status.HTTP_403_FORBIDDEN)
            except Channel.DoesNotExist:
                return Response({"detail": f"Channel {channel_id} not found."}, status=status.HTTP_400_BAD_REQUEST)

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

        # Validate signature before persisting
        sig = request.data.get("signature", "")
        claim_payload = request.data.get("claim_payload", {})
        try:
            verify_claim_signature(
                user_address=user.address,
                user_username=user.username,
                signature=sig,
                claim_payload=claim_payload,
                asset_symbol=asset.symbol,
            )
        except Exception as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(e, DRFValidationError):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            logger.exception("Unexpected error during claim signature verification")
            return Response({"detail": "Invalid claim signature."}, status=status.HTTP_400_BAD_REQUEST)

        # Create HardClaim object in the database with the given data
        try:
            claim_direction, claim_value_type = _normalized_claim_fields(
                data.get("direction", ""),
                data.get("value_type", "PERCENTAGE_UP"),
            )
            hard_claim = HardClaim.objects.create(
                author=user,
                post=post_obj,
                channel=channel_obj,
                asset=asset,
                direction=claim_direction,
                value_type=claim_value_type,
                percentage=data["percentage"],
                until=data["until"],
                status=data.get("status", "undetermined"),
                signature=sig,
                claim_payload=claim_payload,
            )
            from .models import HardClaimEvent
            HardClaimEvent.objects.create(
                hard_claim=hard_claim,
                event_type=HardClaimEvent.EventType.CREATION,
                details={}
            )
            try:
                capture_reference_price(hard_claim)
            except ResolutionError as exc:
                logger.warning(
                    "Reference price not captured for claim %s: %s",
                    hard_claim.id,
                    exc.message,
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
            hard_claim = HardClaim.objects.select_related("asset").get(pk=pk)
        except HardClaim.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if hard_claim.channel_id:
            channel = hard_claim.channel
            user = _get_wallet_user(request)
            if not user or (channel.creator != user and not ChannelMembership.objects.filter(
                channel=channel,
                user=user,
                status=ChannelMembership.Status.APPROVED,
            ).exists()):
                return Response(
                    {"detail": "You must be an approved member to view this claim."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        from datetime import date
        from .resolution import resolve_hard_claim, ResolutionError
        if hard_claim.status == HardClaim.Status.UNDETERMINED and hard_claim.until < date.today():
            try:
                resolve_hard_claim(hard_claim)
            except ResolutionError:
                pass

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


class AssetChartDataView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            asset = Asset.objects.get(pk=pk)
        except Asset.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from datetime import datetime, timedelta, timezone
        from .ohlc_fetcher import (
            get_ohlc_data,
            OHLCFetchError,
            Interval,
            floor_align_datetime,
            CHART_INTERVAL_CHOICES,
        )

        # Default window: Last 30 days
        chart_end = datetime.now(timezone.utc).date()
        chart_start = chart_end - timedelta(days=30)
        default_interval = Interval.FOUR_HOUR

        requested = request.query_params.get("interval")
        if not requested:
            chart_interval = default_interval
        else:
            try:
                chart_interval = Interval(requested)
            except ValueError as exc:
                return Response({"detail": f"Invalid interval: {requested}"}, status=status.HTTP_400_BAD_REQUEST)
            if chart_interval not in CHART_INTERVAL_CHOICES:
                return Response({"detail": f"Interval {requested} not supported for charts."}, status=status.HTTP_400_BAD_REQUEST)

        start_time = floor_align_datetime(
            datetime.combine(chart_start, datetime.min.time(), tzinfo=timezone.utc),
            chart_interval,
        )
        end_time = floor_align_datetime(
            datetime.now(timezone.utc),
            chart_interval,
        )

        try:
            ohlc_rows = get_ohlc_data(asset, start_time, end_time, interval=chart_interval)
        except OHLCFetchError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

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
        
        current_price = None
        if ohlc_data:
            current_price = ohlc_data[-1]["close"]

        return Response({
            "asset_symbol": asset.symbol,
            "interval": chart_interval.value,
            "default_interval": default_interval.value,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "ohlc": ohlc_data,
            "current_price": current_price,
        })


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
        from datetime import datetime, timedelta, timezone
        from .resolution import (
            _effective_direction,
            claim_entry_price,
            claim_target_price,
            ResolutionError,
            _round_decimal,
        )

        claim_start_day = hard_claim.created_at.date()
        claim_end_day = hard_claim.until
        chart_start = claim_start_day - timedelta(days=3)
        chart_end = claim_end_day + timedelta(days=3)
        from .ohlc_fetcher import (
            get_ohlc_data,
            OHLCFetchError,
            resolve_chart_interval,
            floor_align_datetime,
        )
        try:
            chart_interval, default_interval = resolve_chart_interval(
                hard_claim, request.query_params.get("interval")
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        start_time = floor_align_datetime(
            datetime.combine(chart_start, datetime.min.time(), tzinfo=timezone.utc),
            chart_interval,
        )
        end_time = floor_align_datetime(
            datetime.combine(chart_end, datetime.min.time(), tzinfo=timezone.utc),
            chart_interval,
        )

        from datetime import date
        from .resolution import resolve_hard_claim, ResolutionError
        if hard_claim.status == HardClaim.Status.UNDETERMINED and hard_claim.until < date.today():
            try:
                resolve_hard_claim(hard_claim)
            except ResolutionError:
                pass

        if hard_claim.status == HardClaim.Status.UNDETERMINED:
            end_time = floor_align_datetime(
                max(end_time, datetime.now(timezone.utc)),
                chart_interval,
            )

        try:
            ohlc_rows = get_ohlc_data(asset, start_time, end_time, interval=chart_interval)
        except OHLCFetchError as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        # Entry/target from locked reference_price; resolution metadata for hit_days only.
        reference_price = claim_entry_price(hard_claim)
        if reference_price is not None:
            reference_price = _round_decimal(reference_price)

        target_reached_at = None
        hit_days = []
        closest_price = None

        resolution_event = hard_claim.events.filter(event_type="resolution").first()
        if resolution_event and resolution_event.details:
            details = resolution_event.details
            prices = details.get("prices", {})
            closest_price = prices.get("closest")
            target_reached_at = details.get("target_reached_at")
            hit_days = details.get("hit_days", [])

        target_price = claim_target_price(hard_claim, reference_price)

        direction, claim_value_type = reconcile_claim_fields(hard_claim)

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
            "direction": direction,
            "value_type": claim_value_type,
            "reference_price": reference_price,
            "target_price": target_price,
            "percentage": float(hard_claim.percentage),
            "created_at": hard_claim.created_at.isoformat(),
            "until": hard_claim.until.isoformat(),
            "interval": chart_interval.value,
            "default_interval": default_interval.value,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "live": hard_claim.status == HardClaim.Status.UNDETERMINED,
            "ohlc": ohlc_data,
            "hit_days": hit_days,
            "closest_price": closest_price,
            "target_reached_at": target_reached_at,
        })


class PositionChartDataView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        try:
            position = Position.objects.select_related("asset").get(pk=pk)
        except Position.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        asset = position.asset
        from datetime import datetime, timedelta, timezone
        from .ohlc_fetcher import (
            get_ohlc_data,
            OHLCFetchError,
            Interval,
            floor_align_datetime,
            CHART_INTERVAL_CHOICES,
        )

        chart_start = position.created_at.date() - timedelta(days=3)
        chart_end = position.lifetime.date() + timedelta(days=3)

        window_sec = (position.lifetime - position.created_at).total_seconds()
        if window_sec < 7 * 86400:
            default_interval = Interval.FIFTEEN_MIN
        elif window_sec < 30 * 86400:
            default_interval = Interval.FOUR_HOUR
        else:
            default_interval = Interval.ONE_DAY

        requested = request.query_params.get("interval")
        if not requested:
            chart_interval = default_interval
        else:
            try:
                chart_interval = Interval(requested)
            except ValueError as exc:
                return Response({"detail": f"Invalid interval: {requested}"}, status=status.HTTP_400_BAD_REQUEST)
            if chart_interval not in CHART_INTERVAL_CHOICES:
                return Response({"detail": f"Interval {requested} not supported for charts."}, status=status.HTTP_400_BAD_REQUEST)

        start_time = floor_align_datetime(
            datetime.combine(chart_start, datetime.min.time(), tzinfo=timezone.utc),
            chart_interval,
        )
        end_time = floor_align_datetime(
            datetime.combine(chart_end, datetime.min.time(), tzinfo=timezone.utc),
            chart_interval,
        )
        
        if position.status in [Position.Status.PENDING, Position.Status.ACTIVE]:
            from django.utils import timezone as django_timezone
            from .position_resolution import _resolve_pending, _resolve_active
            now = django_timezone.now()
            try:
                if position.status == Position.Status.PENDING:
                    _resolve_pending(position, now)
                if position.status == Position.Status.ACTIVE:
                    _resolve_active(position, now)
            except Exception:
                pass

        if position.status in [Position.Status.PENDING, Position.Status.ACTIVE]:
            end_time = floor_align_datetime(
                max(end_time, datetime.now(timezone.utc)),
                chart_interval,
            )

        try:
            ohlc_rows = get_ohlc_data(asset, start_time, end_time, interval=chart_interval)
        except OHLCFetchError:
            logger.exception(
                "Failed to fetch OHLC data",
                extra={
                    "asset_symbol": asset.symbol,
                    "position_id": position.id,
                    "interval": chart_interval.value,
                },
            )
            return Response(
                {"detail": "Unable to fetch chart data at this time."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

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
            "position_id": position.id,
            "asset_symbol": asset.symbol,
            "direction": position.direction,
            "entry_price": float(position.entry_price),
            "take_profit": float(position.take_profit),
            "stop_loss": float(position.stop_loss),
            "created_at": position.created_at.isoformat(),
            "until": position.lifetime.isoformat(),
            "interval": chart_interval.value,
            "default_interval": default_interval.value,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "live": position.status in [Position.Status.PENDING, Position.Status.ACTIVE],
            "ohlc": ohlc_data,
        })


class ChannelListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        qs = Channel.objects.all().order_by("-created_at")
        data = ChannelSerializer(qs, many=True).data
        
        user = _get_wallet_user(request)
        if user:
            # Build a lookup of channel_id -> membership_status for this user
            memberships = ChannelMembership.objects.filter(
                user=user
            ).values("channel_id", "status")
            membership_map = {m["channel_id"]: m["status"] for m in memberships}
            
            for item in data:
                item["my_membership_status"] = membership_map.get(item["id"])
        
        return Response(data)

    def post(self, request):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        if Channel.objects.filter(creator=user).exists():
            return Response(
                {"detail": "You can only create one channel."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = request.data.get("name")
        description = request.data.get("description", "")
        post_permission = request.data.get("post_permission", Channel.PostPermission.ALL)
        
        if not name:
            return Response({"detail": "Name is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        channel = Channel.objects.create(
            name=name,
            description=description,
            creator=user,
            post_permission=post_permission
        )
        
        ChannelMembership.objects.create(
            channel=channel,
            user=user,
            status=ChannelMembership.Status.APPROVED,
            role=ChannelMembership.Role.OWNER
        )
        
        return Response(ChannelSerializer(channel).data, status=status.HTTP_201_CREATED)

class ChannelDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)
        data = ChannelSerializer(channel).data
        
        user = _get_wallet_user(request)
        membership_status = None
        membership_role = None
        if user:
            membership = ChannelMembership.objects.filter(channel=channel, user=user).first()
            if membership:
                membership_status = membership.status
                membership_role = membership.role
                
        data["my_membership_status"] = membership_status
        data["my_role"] = membership_role
        
        if user and (channel.creator == user or _is_channel_moderator(channel, user)):
            pending_memberships = ChannelMembership.objects.filter(channel=channel, status=ChannelMembership.Status.PENDING)
            data["pending_requests"] = ChannelMembershipSerializer(pending_memberships, many=True).data
            
        return Response(data)

    def patch(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        channel = get_object_or_404(Channel, pk=pk)
        if channel.creator != user:
            return Response({"detail": "Only the creator can update channel settings."}, status=status.HTTP_403_FORBIDDEN)

        allowed_fields = {"post_permission"}
        updated = False
        for field in allowed_fields:
            if field in request.data:
                value = request.data[field]
                if field == "post_permission" and value not in (Channel.PostPermission.ALL, Channel.PostPermission.CREATOR_ONLY):
                    return Response({"detail": f"Invalid value for {field}."}, status=status.HTTP_400_BAD_REQUEST)
                setattr(channel, field, value)
                updated = True

        if updated:
            channel.save()
        return Response(ChannelSerializer(channel).data)

class ChannelJoinView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        channel = get_object_or_404(Channel, pk=pk)
        
        membership = ChannelMembership.objects.filter(channel=channel, user=user).first()
        if membership:
            if membership.status == ChannelMembership.Status.BANNED:
                return Response({"detail": "You are banned from this channel."}, status=status.HTTP_403_FORBIDDEN)
            return Response({"detail": f"Already have a membership with status: {membership.status}."}, status=status.HTTP_400_BAD_REQUEST)
            
        membership = ChannelMembership.objects.create(
            channel=channel,
            user=user,
            status=ChannelMembership.Status.PENDING
        )
            
        return Response(ChannelMembershipSerializer(membership).data, status=status.HTTP_201_CREATED)

class ChannelApproveView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        channel = get_object_or_404(Channel, pk=pk)
        if not _is_channel_moderator(channel, user):
            return Response({"detail": "Only moderators or the owner can approve members."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        membership = get_object_or_404(ChannelMembership, channel=channel, user=target_user)
        
        action = request.data.get("action")
        if action == "approve":
            membership.status = ChannelMembership.Status.APPROVED
            membership.save()
            return Response(ChannelMembershipSerializer(membership).data)
        elif action == "reject":
            membership.delete()
            return Response({"detail": "Request rejected."})
        else:
            return Response({"detail": "Invalid action. Use 'approve' or 'reject'."}, status=status.HTTP_400_BAD_REQUEST)

class ChannelBanView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        channel = get_object_or_404(Channel, pk=pk)
        if not _is_channel_moderator(channel, user):
            return Response({"detail": "Only moderators or the owner can ban members."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        if target_user == user:
            return Response({"detail": "You cannot ban yourself."}, status=status.HTTP_400_BAD_REQUEST)

        # Guard: moderators cannot ban the owner or other moderators of equal/higher rank
        target_membership = ChannelMembership.objects.filter(channel=channel, user=target_user).first()
        if target_membership and target_membership.role in [ChannelMembership.Role.OWNER, ChannelMembership.Role.MODERATOR]:
            if channel.creator != user:  # Only owner can ban moderators
                return Response({"detail": "Moderators cannot ban the owner or other moderators."}, status=status.HTTP_403_FORBIDDEN)

        membership, _ = ChannelMembership.objects.get_or_create(
            channel=channel,
            user=target_user
        )
        membership.status = ChannelMembership.Status.BANNED
        membership.save()
        return Response(ChannelMembershipSerializer(membership).data)

    def delete(self, request, pk, user_address):
        user = _get_wallet_user(request)
        if user is None:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
            
        channel = get_object_or_404(Channel, pk=pk)
        if not _is_channel_moderator(channel, user):
            return Response({"detail": "Only moderators or the owner can unban members."}, status=status.HTTP_403_FORBIDDEN)
            
        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        
        try:
            membership = ChannelMembership.objects.get(channel=channel, user=target_user)
            if membership.status == ChannelMembership.Status.BANNED:
                membership.delete()
                return Response({"detail": "User unbanned."}, status=status.HTTP_204_NO_CONTENT)
            else:
                return Response({"detail": "User is not banned."}, status=status.HTTP_400_BAD_REQUEST)
        except ChannelMembership.DoesNotExist:
            return Response({"detail": "User is not banned."}, status=status.HTTP_400_BAD_REQUEST)

class ChannelMemberListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)
        
        user = _get_wallet_user(request)
        if not user or (channel.creator != user and not ChannelMembership.objects.filter(channel=channel, user=user, status=ChannelMembership.Status.APPROVED).exists()):
            return Response({"detail": "You must be a member to view this list."}, status=status.HTTP_403_FORBIDDEN)
                
        memberships = ChannelMembership.objects.filter(channel=channel, status=ChannelMembership.Status.APPROVED).order_by('created_at')
        return Response(ChannelMembershipSerializer(memberships, many=True).data)

class ChannelBannedListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        channel = get_object_or_404(Channel, pk=pk)
        
        user = _get_wallet_user(request)
        if not user or not _is_channel_moderator(channel, user):
            return Response({"detail": "Only moderators or the owner can view the banned list."}, status=status.HTTP_403_FORBIDDEN)
                
        memberships = ChannelMembership.objects.filter(channel=channel, status=ChannelMembership.Status.BANNED).order_by('created_at')
        return Response(ChannelMembershipSerializer(memberships, many=True).data)

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
        channel_id = request.query_params.get("channel")
        if not channel_id:
            return Response({"detail": "channel parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        channel = get_object_or_404(Channel, pk=channel_id)
        
        # Privacy check
        user = _get_wallet_user(request)
        if not user or (channel.creator != user and not ChannelMembership.objects.filter(channel=channel, user=user, status=ChannelMembership.Status.APPROVED).exists()):
            return Response({"detail": "You must be an approved member to view positions in this private channel."}, status=status.HTTP_403_FORBIDDEN)
                
        positions = Position.objects.filter(channel=channel).select_related("author", "author__profitability", "asset").order_by("-created_at")
        return Response(PositionSerializer(positions, many=True).data)

    def post(self, request):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = PositionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        channel = get_object_or_404(Channel, pk=data["channel_id"])
        
        # Permission checks
        membership = ChannelMembership.objects.filter(channel=channel, user=user).first()
        if membership and membership.status == ChannelMembership.Status.BANNED:
            return Response({"detail": "You are banned from this channel."}, status=status.HTTP_403_FORBIDDEN)

        if channel.creator != user and (not membership or membership.status != ChannelMembership.Status.APPROVED):
            return Response({"detail": "You must be an approved member to post positions in this private channel."}, status=status.HTTP_403_FORBIDDEN)
                
        if channel.creator != user:
            return Response({"detail": "Only the channel owner can share positions."}, status=status.HTTP_403_FORBIDDEN)

        asset = get_object_or_404(Asset, pk=data["asset_id"])

        sig = data.get("signature", "")
        position_payload = data.get("position_payload", {})
        try:
            verify_position_signature(
                user_address=user.address,
                user_username=user.username,
                signature=sig,
                position_payload=position_payload,
                asset_symbol=asset.symbol,
            )
        except Exception as e:
            from rest_framework.exceptions import ValidationError as DRFValidationError
            if isinstance(e, DRFValidationError):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            logger.exception("Unexpected error while verifying position signature")
            return Response({"detail": "Unable to verify position signature."}, status=status.HTTP_400_BAD_REQUEST)

        position = Position.objects.create(
            author=user,
            channel=channel,
            asset=asset,
            direction=data["direction"],
            entry_price=data["entry_price"],
            entry_interval=data["entry_interval"],
            stop_loss=data["stop_loss"],
            take_profit=data["take_profit"],
            lifetime=data["lifetime"],
            signature=sig,
            position_payload=position_payload,
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


class ChannelModeratorView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        """Promote a member to moderator (owner only)."""
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        channel = get_object_or_404(Channel, pk=pk)
        if channel.creator != user:
            return Response({"detail": "Only the owner can promote moderators."}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        if target_user == user:
            return Response({"detail": "You are already the owner."}, status=status.HTTP_400_BAD_REQUEST)

        membership = get_object_or_404(ChannelMembership, channel=channel, user=target_user)
        if membership.status != ChannelMembership.Status.APPROVED:
            return Response({"detail": "User must be an approved member to be promoted."}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = ChannelMembership.Role.MODERATOR
        membership.save()
        return Response(ChannelMembershipSerializer(membership).data)

    def delete(self, request, pk, user_address):
        """Demote a moderator back to member (owner only)."""
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        channel = get_object_or_404(Channel, pk=pk)
        if channel.creator != user:
            return Response({"detail": "Only the owner can demote moderators."}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        membership = get_object_or_404(ChannelMembership, channel=channel, user=target_user)
        if membership.role != ChannelMembership.Role.MODERATOR:
            return Response({"detail": "User is not a moderator."}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = ChannelMembership.Role.MEMBER
        membership.save()
        return Response(ChannelMembershipSerializer(membership).data)


class PostDeleteView(APIView):
    authentication_classes = []
    permission_classes = []

    def delete(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        post = get_object_or_404(Post, pk=pk)

        is_channel_mod = post.channel and _is_channel_moderator(post.channel, user)

        if not is_channel_mod:
            return Response({"detail": "You do not have permission to delete this post."}, status=status.HTTP_403_FORBIDDEN)

        author = post.author
        metadata = {
            "post_id": post.id,
            "channel_id": post.channel_id,
            "content_preview": post.content[:120],
            "deleted_by": user.address,
        }
        with transaction.atomic():
            post.delete()
            ProfileChangeLog.objects.create(
                user=author,
                actor=user,
                event_type=ProfileChangeLog.EventType.POST_DELETED,
                summary="Deleted a post",
                metadata=metadata,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class HardClaimProofView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        claim = get_object_or_404(HardClaim, pk=pk)
        if not claim.signature:
            return Response({"detail": "This claim does not have a signature."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "type": "claim",
            "claim_id": claim.id,
            "wallet_address": claim.author.address,
            "signature": claim.signature,
            "payload": claim.claim_payload,
            "server_timestamp": claim.created_at.isoformat(),
            "reference_price": claim.reference_price,
            "target_price": claim_target_price(claim),
        })


class PositionProofView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        position = get_object_or_404(Position, pk=pk)
        if not position.signature:
            return Response({"detail": "This position does not have a signature."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "type": "position",
            "position_id": position.id,
            "wallet_address": position.author.address,
            "signature": position.signature,
            "payload": position.position_payload,
            "server_timestamp": position.created_at.isoformat()
        })
