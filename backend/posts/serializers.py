from datetime import date
from rest_framework import serializers
from accounts.serializers import avatar_delivery_url, post_image_delivery_url
from .models import Asset, Post, HardClaim, HardClaimEvent, OHLCData, Channel, ChannelMembership, Position, PositionEvent, PostComment

# ─────────────────────────────────────────────────────────────────────────────
# Asset
# ─────────────────────────────────────────────────────────────────────────────

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id",
            "name",
            "symbol",
            "description",
            "market_type",
            "provider",
            "provider_symbol",
            "quote_currency",
            "binance_symbol",
            "kucoin_symbol",
            "kraken_pair",
            "twelvedata_symbol",
        ]


# ─────────────────────────────────────────────────────────────────────────────
# HardClaim
# ─────────────────────────────────────────────────────────────────────────────

class HardClaimInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    post_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    channel_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    direction = serializers.CharField(allow_blank=True, default="")
    value_type = serializers.ChoiceField(
        choices=["PRICE", "PERCENTAGE_UP", "PERCENTAGE_DOWN"],
        default="PERCENTAGE_UP",
    )
    percentage = serializers.FloatField(min_value=0)
    until = serializers.DateField()
    status = serializers.ChoiceField(choices=["confirmed", "undetermined", "rejected"], default="undetermined")
    signature = serializers.CharField(required=True)
    claim_payload = serializers.JSONField(required=True)

    def validate(self, data):
        value_type = (data.get("value_type") or "PERCENTAGE_UP").upper()
        direction = (data.get("direction") or "").strip().lower()
        pct = float(data.get("percentage", 0))

        if value_type == "PRICE":
            if direction not in {"bullish", "bearish"}:
                raise serializers.ValidationError(
                    {"direction": "PRICE claims require direction (bullish or bearish)."}
                )
        elif pct > 150:
            raise serializers.ValidationError(
                {
                    "percentage": (
                        "Values above 150 look like absolute prices — use value_type PRICE instead."
                    )
                }
            )

        return data

    def validate_until(self, value):
        if value <= date.today():
            raise serializers.ValidationError("'until' must be a future date.")
        return value


class HardClaimEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = HardClaimEvent
        fields = ["id", "event_type", "timestamp", "details"]


class HardClaimSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True, allow_null=True)
    author_username = serializers.CharField(source="author.username", read_only=True, allow_null=True)
    author_avatar_url = serializers.SerializerMethodField()
    events = HardClaimEventSerializer(many=True, read_only=True)
    profitability = serializers.SerializerMethodField()

    class Meta:
        model = HardClaim
        fields = [
            "id", "author_address", "author_username", "author_avatar_url", "post_id", "channel",
            "asset", "direction", "value_type", "percentage",
            "until", "created_at", "reference_price", "reference_price_url",
            "status", "events", "profitability",
            "signature", "claim_payload"
        ]

    def get_author_avatar_url(self, obj):
        avatar = getattr(obj.author, "avatar", None) if obj.author else None
        return avatar_delivery_url(avatar)

    def to_representation(self, instance):
        from .resolution import reconcile_claim_fields, display_percentage, claim_target_price

        data = super().to_representation(instance)
        direction, value_type = reconcile_claim_fields(instance)
        data["direction"] = direction
        data["value_type"] = value_type
        pct = display_percentage(instance)
        if pct is not None:
            data["display_percentage"] = pct
        target = claim_target_price(instance)
        if target is not None:
            data["target_price"] = target

        # Inject nested asset object for UI rendering
        data["asset_obj"] = AssetSerializer(instance.asset).data

        return data

    def get_profitability(self, obj):
        try:
            cache = obj.author.profitability
            return {
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all
            }
        except Exception:
            return None


# ─────────────────────────────────────────────────────────────────────────────
# Position (defined before PostSerializer to avoid forward-reference issues)
# ─────────────────────────────────────────────────────────────────────────────

class PositionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionEvent
        fields = ["id", "event_type", "timestamp", "details"]


class PositionSummarySerializer(serializers.ModelSerializer):
    """Slim serializer for embedding inside PostSerializer (no events/heavy fields)."""
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    asset_obj = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "id", "author_address", "author_username", "post", "channel", "asset", "asset_obj",
            "direction", "entry_price", "stop_loss", "take_profit",
            "status", "pnl_percentage", "created_at", "lifetime",
        ]

    def get_asset_obj(self, obj):
        return AssetSerializer(obj.asset).data


class PositionSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    events = PositionEventSerializer(many=True, read_only=True)
    profitability = serializers.SerializerMethodField()
    asset_obj = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "id", "author_address", "author_username", "post", "channel", "asset", "asset_obj", "direction",
            "entry_price", "entry_interval", "stop_loss", "take_profit",
            "lifetime", "exit_price", "pnl_percentage", "status", "created_at", "events", "profitability",
            "signature", "position_payload"
        ]

    def get_profitability(self, obj):
        try:
            cache = obj.author.profitability
            return {
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all
            }
        except Exception:
            return None

    def get_asset_obj(self, obj):
        return AssetSerializer(obj.asset).data


from django.utils import timezone


class PositionInputSerializer(serializers.Serializer):
    channel_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    post_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    asset_id = serializers.IntegerField(required=True)
    direction = serializers.ChoiceField(choices=Position.Direction.choices, required=True)
    entry_price = serializers.FloatField(required=True)
    entry_interval = serializers.DateTimeField(required=True)
    stop_loss = serializers.FloatField(required=True)
    take_profit = serializers.FloatField(required=True)
    lifetime = serializers.DateTimeField(required=True)
    signature = serializers.CharField(required=True)
    position_payload = serializers.JSONField(required=True)

    def validate(self, data):
        now = timezone.now()

        if data["entry_interval"] <= now:
            raise serializers.ValidationError({"entry_interval": "entry_interval must be in the future."})

        if data["lifetime"] <= data["entry_interval"]:
            raise serializers.ValidationError({"lifetime": "lifetime must be after entry_interval."})

        entry = data["entry_price"]
        sl = data["stop_loss"]
        tp = data["take_profit"]

        if data["direction"] == Position.Direction.LONG:
            if not (sl < entry < tp):
                raise serializers.ValidationError("For LONG positions, stop_loss must be < entry_price < take_profit.")
        elif data["direction"] == Position.Direction.SHORT:
            if not (tp < entry < sl):
                raise serializers.ValidationError("For SHORT positions, take_profit must be < entry_price < stop_loss.")

        return data


class PostCommentSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    author_avatar_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = PostComment
        fields = [
            "id", "post", "parent", "author_address", "author_username", "author_avatar_url",
            "content", "image_url", "created_at", "like_count", "liked_by_me", "replies"
        ]
        read_only_fields = ["id", "post", "author_address", "author_username", "created_at"]

    def get_author_avatar_url(self, obj):
        avatar = getattr(obj.author, "avatar", None) if obj.author else None
        return avatar_delivery_url(avatar)

    def get_image_url(self, obj):
        return post_image_delivery_url(obj.image)

    def get_like_count(self, obj):
        return getattr(obj, "like_count", obj.likes.count())

    def get_liked_by_me(self, obj):
        return bool(getattr(obj, "liked_by_me", False))

    def get_replies(self, obj):
        replies = getattr(obj, "prefetched_replies", None)
        if replies is None:
            replies = obj.replies.select_related("author").order_by("created_at")
        return PostCommentSerializer(replies, many=True, context=self.context).data


# ─────────────────────────────────────────────────────────────────────────────
# Post (defined after Position so get_positions has no forward-reference)
# ─────────────────────────────────────────────────────────────────────────────

class PostSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    author_avatar_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    hard_claims = HardClaimSerializer(many=True, read_only=True)
    positions = serializers.SerializerMethodField()
    profitability = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    saved_proof_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()
    saved_proof_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id", "author_address", "author_username", "author_avatar_url", "content", "image_url", "channel",
            "created_at", "hard_claims", "positions", "profitability",
            "like_count", "comment_count", "saved_proof_count", "liked_by_me", "saved_proof_by_me",
        ]

    def get_author_avatar_url(self, obj):
        avatar = getattr(obj.author, "avatar", None) if obj.author else None
        return avatar_delivery_url(avatar)

    def get_image_url(self, obj):
        return post_image_delivery_url(obj.image)

    def get_profitability(self, obj):
        try:
            cache = obj.author.profitability
            return {
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all
            }
        except Exception:
            return None

    def get_positions(self, obj):
        return PositionSummarySerializer(obj.positions.all(), many=True).data

    def get_like_count(self, obj):
        return getattr(obj, "like_count", obj.likes.count())

    def get_comment_count(self, obj):
        return getattr(obj, "comment_count", obj.comments.count())

    def get_saved_proof_count(self, obj):
        return getattr(obj, "saved_proof_count", obj.saved_proofs.count())

    def get_liked_by_me(self, obj):
        return bool(getattr(obj, "liked_by_me", False))

    def get_saved_proof_by_me(self, obj):
        return bool(getattr(obj, "saved_proof_by_me", False))


# ─────────────────────────────────────────────────────────────────────────────
# Misc
# ─────────────────────────────────────────────────────────────────────────────

class OHLCDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = OHLCData
        fields = ["date", "open", "high", "low", "close"]


class ChannelSerializer(serializers.ModelSerializer):
    creator_address = serializers.CharField(source="creator.address", read_only=True)
    creator_username = serializers.CharField(source="creator.username", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = ["id", "name", "description", "creator_address", "creator_username", "post_permission", "created_at", "member_count"]

    def get_member_count(self, obj):
        if hasattr(obj, "member_count_annotated"):
            return obj.member_count_annotated
        return obj.memberships.filter(status="approved").count()


class ChannelMembershipSerializer(serializers.ModelSerializer):
    user_address = serializers.CharField(source="user.address", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    profitability = serializers.SerializerMethodField()

    class Meta:
        model = ChannelMembership
        fields = ["id", "channel", "user_address", "user_username", "status", "role", "created_at", "profitability"]

    def get_profitability(self, obj):
        try:
            cache = obj.user.profitability
            return {
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all
            }
        except Exception:
            return None
