from datetime import date
from rest_framework import serializers
from .models import Asset, Post, Claim, HardClaim, HardClaimEvent


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
        ]

class HardClaimInputSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField()
    post_id = serializers.IntegerField(required=False, allow_null=True, default=None)
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
        fields = ["id", "author_address", "post_id", "asset", "direction", "percentage", "until", "created_at", "status", "events"]

class PostSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)
    hard_claims = HardClaimSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author_address", "content", "created_at", "claims", "hard_claims"]
