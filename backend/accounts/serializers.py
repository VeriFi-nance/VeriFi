import re
from rest_framework import serializers
from .models import WalletUser


# Cloudinary's free plan rejects uploads larger than 10 MB; we accept up to that
# and let Cloudinary downscale dimensions on delivery (see *_delivery_url below),
# so users never have to manually shrink an image.
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_image_upload(file):
    """Return an error string if the uploaded file is not an acceptable image, else None."""
    if file is None:
        return None
    content_type = getattr(file, "content_type", "") or ""
    if not content_type.startswith("image/"):
        return "Uploaded file must be an image."
    if file.size > MAX_IMAGE_UPLOAD_BYTES:
        return "Image must be 10 MB or smaller."
    return None


def avatar_delivery_url(resource):
    """Cloudinary URL for a profile picture: 256x256 face-aware square, auto format/quality."""
    if not resource:
        return None
    return resource.build_url(
        width=256, height=256, crop="fill", gravity="face",
        quality="auto", fetch_format="auto", secure=True,
    )


def post_image_delivery_url(resource):
    """Cloudinary URL for a post image: width-capped at 1280px, auto format/quality."""
    if not resource:
        return None
    return resource.build_url(
        width=1280, crop="limit",
        quality="auto", fetch_format="auto", secure=True,
    )


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
    avatar_url = serializers.CharField(required=False, allow_null=True)
    followers_count = serializers.IntegerField()
    following_count = serializers.IntegerField()
    followers = serializers.ListField(child=serializers.CharField())
    following = serializers.ListField(child=serializers.CharField())
    is_following = serializers.BooleanField(required=False)
