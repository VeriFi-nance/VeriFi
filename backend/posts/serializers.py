from rest_framework import serializers
from .models import Post, Claim


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = ["id", "text", "asset", "direction", "status"]


class PostSerializer(serializers.ModelSerializer):
    author_address = serializers.CharField(source="author.address", read_only=True)
    claims = ClaimSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = ["id", "author_address", "content", "created_at", "claims"]


class ClaimInputSerializer(serializers.Serializer):
    text = serializers.CharField()
    asset = serializers.CharField(allow_blank=True, default="")
    direction = serializers.CharField(allow_blank=True, default="")
    status = serializers.ChoiceField(choices=["confirmed", "rejected"], default="confirmed")
