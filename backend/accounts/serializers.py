from rest_framework import serializers


class RegisterSerializer(serializers.Serializer):
    public_key = serializers.CharField(max_length=66)


class ChallengeResponseSerializer(serializers.Serializer):
    nonce = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    public_key = serializers.CharField(max_length=66)
    signature = serializers.CharField()
    nonce = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField()
