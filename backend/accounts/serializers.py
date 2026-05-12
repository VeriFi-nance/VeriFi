from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)


class ChallengeResponseSerializer(serializers.Serializer):
    nonce = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)
    signature = serializers.CharField()
    nonce = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()


class FollowSerializer(serializers.Serializer):
    target_address = serializers.CharField(max_length=42)

class ProfileSerializer(serializers.Serializer):
    address = serializers.CharField()
    followers_count = serializers.IntegerField()
    following_count = serializers.IntegerField()
    followers = serializers.ListField(child=serializers.CharField())
    following = serializers.ListField(child=serializers.CharField())
    is_following = serializers.BooleanField(required=False)
