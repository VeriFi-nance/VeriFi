from datetime import date
from rest_framework import serializers
from .models import Asset, Post, Claim, HardClaim, HardClaimEvent, OHLCData, Community, CommunityMembership


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
    community_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    direction = serializers.CharField(allow_blank=True, default="")
    percentage = serializers.FloatField(min_value=0)
    until = serializers.DateField()
    status = serializers.ChoiceField(choices=["confirmed", "undetermined", "rejected"], default="undetermined")


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
    events = HardClaimEventSerializer(many=True, read_only=True)

    class Meta:
        model = HardClaim
        fields = ["id", "author_address", "post_id", "community", "asset", "direction", "percentage", "until", "created_at", "status", "events"]

class PostSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)
    hard_claims = HardClaimSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author_address", "content", "community", "created_at", "claims", "hard_claims"]


class OHLCDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = OHLCData
        fields = ["date", "open", "high", "low", "close"]

class CommunitySerializer(serializers.ModelSerializer):
    creator_address = serializers.CharField(source="creator.address", read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ["id", "name", "description", "creator_address", "privacy_type", "post_permission", "created_at", "member_count"]

    def get_member_count(self, obj):
        return obj.memberships.filter(status="approved").count()

class CommunityMembershipSerializer(serializers.ModelSerializer):
    user_address = serializers.CharField(source="user.address", read_only=True)

    class Meta:
        model = CommunityMembership
        fields = ["id", "community", "user_address", "status", "created_at"]

from .models import Position, PositionEvent

class PositionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = PositionEvent
        fields = ["id", "event_type", "timestamp", "details"]

class PositionSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    events = PositionEventSerializer(many=True, read_only=True)

    class Meta:
        model = Position
        fields = [
            "id", "author_address", "community", "asset", "direction",
            "entry_price", "entry_interval", "stop_loss", "take_profit",
            "lifetime", "exit_price", "pnl_percentage", "status", "created_at", "events"
        ]

from django.utils import timezone

class PositionInputSerializer(serializers.Serializer):
    community_id = serializers.IntegerField(required=True)
    asset_id = serializers.IntegerField(required=True)
    direction = serializers.ChoiceField(choices=Position.Direction.choices, required=True)
    entry_price = serializers.FloatField(required=True)
    entry_interval = serializers.DateTimeField(required=True)
    stop_loss = serializers.FloatField(required=True)
    take_profit = serializers.FloatField(required=True)
    lifetime = serializers.DateTimeField(required=True)

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
