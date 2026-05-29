import os
import binascii

from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from eth_account import Account
from eth_account.messages import encode_defunct

from .models import WalletUser, Follow
from .serializers import RegisterSerializer, LoginSerializer, FollowSerializer, ProfileSerializer
from django.shortcuts import get_object_or_404


def _make_jwt(user: WalletUser) -> str:
    refresh = RefreshToken()
    refresh["address"] = user.address
    return str(refresh.access_token)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

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
    authentication_classes = []
    permission_classes = []

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

        nonce = "0x" + binascii.hexlify(os.urandom(32)).decode()
        cache_key = f"nonce:{address}"
        cache.set(cache_key, nonce, timeout=300)  # 5 minutes
        return Response({"nonce": nonce})


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

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
            msg = encode_defunct(hexstr=nonce)
            recovered = Account.recover_message(msg, signature=bytes.fromhex(signature_hex))
            if recovered.lower() != address:
                raise ValueError("Address mismatch")
        except Exception:
            return Response(
                {"detail": "Invalid signature."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({"access": _make_jwt(user)})


class ProfileView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, address):
        from .energy import grant_energy, ENERGY_CAP
        address = address.lower()
        target_user = get_object_or_404(WalletUser, address=address)
        grant_energy(target_user)

        followers = target_user.follower_set.all().select_related("follower")
        following = target_user.following_set.all().select_related("following")

        followers_list = [f.follower.address for f in followers]
        following_list = [f.following.address for f in following]

        is_following = False

        data = {
            "address": target_user.address,
            "followers_count": len(followers_list),
            "following_count": len(following_list),
            "followers": followers_list,
            "following": following_list,
            "rep": target_user.rep,
            "energy": target_user.energy,
            "energy_cap": ENERGY_CAP,
        }
        
        try:
            cache = target_user.profitability
            data["profitability"] = {
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all,
                "updated_at": cache.updated_at
            }
        except Exception:
            data["profitability"] = None
        
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from rest_framework_simplejwt.tokens import AccessToken
                access = AccessToken(token)
                req_address = access.get("address", "").lower()
                if req_address:
                    is_following = target_user.follower_set.filter(follower__address=req_address).exists()
                    data["is_following"] = is_following
            except Exception:
                pass
                
        return Response(data)


class FollowToggleView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
            
        token = auth_header.split(" ")[1]
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            access = AccessToken(token)
            req_address = access.get("address", "").lower()
            current_user = WalletUser.objects.get(address=req_address)
        except Exception:
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = FollowSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        target_address = serializer.validated_data["target_address"].lower()
        if req_address == target_address:
            return Response({"detail": "Cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)
            
        target_user = get_object_or_404(WalletUser, address=target_address)
        
        follow_obj, created = Follow.objects.get_or_create(follower=current_user, following=target_user)
        
        if not created:
            # Already following, so unfollow
            follow_obj.delete()
            return Response({"detail": "Unfollowed successfully.", "following": False})
            
        return Response({"detail": "Followed successfully.", "following": True})

class ProfitabilityView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, address):
        address = address.lower()
        user = get_object_or_404(WalletUser, address=address)
        
        try:
            cache = user.profitability
            return Response({
                "pnl_7d": cache.pnl_7d,
                "pnl_30d": cache.pnl_30d,
                "pnl_all": cache.pnl_all,
                "updated_at": cache.updated_at
            })
        except WalletUser.profitability.RelatedObjectDoesNotExist:
            return Response({
                "pnl_7d": 0.0,
                "pnl_30d": 0.0,
                "pnl_all": 0.0,
                "updated_at": None
            })
