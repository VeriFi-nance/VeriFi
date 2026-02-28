import os
import hashlib
import binascii

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.util import sigdecode_string

from .models import WalletUser
from .serializers import RegisterSerializer, LoginSerializer


def _make_jwt(user: WalletUser) -> str:
    refresh = RefreshToken()
    refresh["public_key"] = user.public_key
    return str(refresh.access_token)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        public_key_hex = serializer.validated_data["public_key"]

        if WalletUser.objects.filter(public_key=public_key_hex).exists():
            return Response(
                {"detail": "Public key already registered."},
                status=status.HTTP_409_CONFLICT,
            )

        user = WalletUser.objects.create(public_key=public_key_hex)
        return Response({"access": _make_jwt(user)}, status=status.HTTP_201_CREATED)


class ChallengeView(APIView):
    def get(self, request):
        public_key_hex = request.query_params.get("public_key", "").strip()
        if not public_key_hex:
            return Response(
                {"detail": "public_key query param required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not WalletUser.objects.filter(public_key=public_key_hex).exists():
            return Response(
                {"detail": "Unknown public key."},
                status=status.HTTP_404_NOT_FOUND,
            )

        nonce = binascii.hexlify(os.urandom(32)).decode()
        cache_key = f"nonce:{public_key_hex}"
        cache.set(cache_key, nonce, timeout=300)  # 5 minutes
        return Response({"nonce": nonce})


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        public_key_hex = serializer.validated_data["public_key"]
        signature_hex = serializer.validated_data["signature"]
        nonce = serializer.validated_data["nonce"]

        # Verify nonce matches cached one
        cache_key = f"nonce:{public_key_hex}"
        expected_nonce = cache.get(cache_key)
        if expected_nonce is None or expected_nonce != nonce:
            return Response(
                {"detail": "Invalid or expired nonce."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Delete nonce so it can't be replayed
        cache.delete(cache_key)

        try:
            user = WalletUser.objects.get(public_key=public_key_hex)
        except WalletUser.DoesNotExist:
            return Response(
                {"detail": "Unknown public key."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verify secp256k1 signature
        try:
            pub_bytes = bytes.fromhex(public_key_hex)
            vk = VerifyingKey.from_string(pub_bytes, curve=SECP256k1)
            sig_bytes = bytes.fromhex(signature_hex)
            message_hash = hashlib.sha256(nonce.encode()).digest()
            vk.verify_digest(sig_bytes, message_hash, sigdecode=sigdecode_string)
        except (BadSignatureError, Exception):
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({"access": _make_jwt(user)})
