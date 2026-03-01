import os
import binascii

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from eth_account import Account
from eth_account.messages import encode_defunct

from .models import WalletUser
from .serializers import RegisterSerializer, LoginSerializer


def _make_jwt(user: WalletUser) -> str:
    refresh = RefreshToken()
    refresh["address"] = user.address
    return str(refresh.access_token)


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        address = serializer.validated_data["address"].lower()

        if WalletUser.objects.filter(address=address).exists():
            return Response(
                {"detail": "Address already registered."},
                status=status.HTTP_409_CONFLICT,
            )

        user = WalletUser.objects.create(address=address)
        return Response({"access": _make_jwt(user)}, status=status.HTTP_201_CREATED)


class ChallengeView(APIView):
    def get(self, request):
        address = request.query_params.get("address", "").strip().lower()
        if not address:
            return Response(
                {"detail": "address query param required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not WalletUser.objects.filter(address=address).exists():
            return Response(
                {"detail": "Unknown address."},
                status=status.HTTP_404_NOT_FOUND,
            )

        nonce = binascii.hexlify(os.urandom(32)).decode()
        cache_key = f"nonce:{address}"
        cache.set(cache_key, nonce, timeout=300)  # 5 minutes
        return Response({"nonce": nonce})


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        address = serializer.validated_data["address"].lower()
        signature_hex = serializer.validated_data["signature"]
        nonce = serializer.validated_data["nonce"]

        # Verify nonce matches cached one
        cache_key = f"nonce:{address}"
        expected_nonce = cache.get(cache_key)
        if expected_nonce is None or expected_nonce != nonce:
            return Response(
                {"detail": "Invalid or expired nonce."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Delete nonce so it can't be replayed
        cache.delete(cache_key)

        try:
            user = WalletUser.objects.get(address=address)
        except WalletUser.DoesNotExist:
            return Response(
                {"detail": "Unknown address."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Recover address from EIP-191 personal_sign signature
        try:
            msg = encode_defunct(text=nonce)
            recovered = Account.recover_message(msg, signature=bytes.fromhex(signature_hex))
            if recovered.lower() != address:
                raise ValueError("Address mismatch")
        except Exception:
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({"access": _make_jwt(user)})
