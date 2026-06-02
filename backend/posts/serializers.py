from datetime import date
from rest_framework import serializers
from .models import Asset, Post, Claim, HardClaim, HardClaimEvent, OHLCData, Channel, ChannelMembership


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ["id", "text", "asset", "direction", "status"]



class ClaimInputSerializer(serializers.Serializer):
    text = serializers.CharField()
    asset = serializers.CharField(allow_blank=True, default="")
    direction = serializers.CharField(allow_blank=True, default="")
    status = serializers.ChoiceField(choices=["confirmed", "rejected"], default="confirmed")

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

class HardClaimInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    post_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    channel_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    direction = serializers.CharField(allow_blank=True, default="")
    value_type = serializers.ChoiceField(
        choices=["PRICE", "PERCENTAGE_UP", "PERCENTAGE_DOWN"],
        default="PERCENTAGE_UP",
    )
    payda = serializers.CharField(allow_blank=True, default="", required=False)
    percentage = serializers.FloatField(min_value=0)
    until = serializers.DateField()
    status = serializers.ChoiceField(choices=["confirmed", "undetermined", "rejected"], default="undetermined")
    signature = serializers.CharField(required=True)
    claim_payload = serializers.JSONField(required=True)


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
    events = HardClaimEventSerializer(many=True, read_only=True)
    profitability = serializers.SerializerMethodField()

    class Meta:
        model = HardClaim
        fields = [
            "id", "author_address", "author_username", "post_id", "channel",
            "asset", "direction", "value_type", "payda", "percentage",
            "until", "created_at", "status", "events", "profitability",
            "signature", "claim_payload"
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

class PostSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)
    hard_claims = HardClaimSerializer(many=True, read_only=True)
    profitability = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "author_address", "author_username", "content", "channel", "created_at", "claims", "hard_claims", "profitability"]

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
        fields = ["id", "name", "description", "creator_address", "creator_username", "privacy_type", "post_permission", "created_at", "member_count"]

    def get_member_count(self, obj):
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

from .models import Position, PositionEvent

class PositionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionEvent
        fields = ["id", "event_type", "timestamp", "details"]

class PositionSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    author_username = serializers.CharField(source="author.username", read_only=True)
    events = PositionEventSerializer(many=True, read_only=True)
    profitability = serializers.SerializerMethodField()

    class Meta:
        model = Position
        fields = [
            "id", "author_address", "author_username", "channel", "asset", "direction",
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

from django.utils import timezone

class PositionInputSerializer(serializers.Serializer):
    channel_id = serializers.IntegerField(required=True)
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
