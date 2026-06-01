import re
from rest_framework import serializers
from .models import WalletUser


def validate_username_format(value):
    if not value:
        return None
    if not re.match(r"^[a-zA-Z0-9_]+$", value):
        return "Username can only contain letters, numbers, and underscores."
    if value.lower().startswith("0x"):
        return "Username cannot start with '0x'."
    if value.lower() in {"update", "follow", "register", "login", "challenge", "profitability"}:
        return "This username is reserved."
    return None


class RegisterSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)
    username = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_username(self, value):
        if not value:
            return value
            
        error = validate_username_format(value)
        if error:
            raise serializers.ValidationError(error)
            
        if WalletUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username is already taken.")
            
        return value


class ChallengeResponseSerializer(serializers.Serializer):
    nonce = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    address = serializers.CharField(max_length=42)
    signature = serializers.CharField()
    nonce = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()
    username = serializers.CharField()


class FollowSerializer(serializers.Serializer):
    target_address = serializers.CharField(max_length=42)

class ProfileSerializer(serializers.Serializer):
    address = serializers.CharField()
    username = serializers.CharField()
    followers_count = serializers.IntegerField()
    following_count = serializers.IntegerField()
    followers = serializers.ListField(child=serializers.CharField())
    following = serializers.ListField(child=serializers.CharField())
    is_following = serializers.BooleanField(required=False)
