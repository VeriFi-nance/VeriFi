import os
import binascii

from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from eth_account import Account
from eth_account.messages import encode_defunct

from .models import WalletUser, Follow
from .serializers import RegisterSerializer, LoginSerializer, FollowSerializer, validate_username_format
from .energy import grant_energy, ENERGY_CAP


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
        username = serializer.validated_data.get("username")
        
        if WalletUser.objects.filter(address=address).exists():
            return Response(
                {"detail": "Address already registered."},
                status=status.HTTP_409_CONFLICT,
            )
            
        if not username:
            base_username = address[:6]
            username = base_username
            counter = 1
            while WalletUser.objects.filter(username__iexact=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

        user = WalletUser.objects.create(address=address, username=username)
        return Response({"access": _make_jwt(user), "username": user.username}, status=status.HTTP_201_CREATED)


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

        return Response({"access": _make_jwt(user), "username": user.username})


class ProfileView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, lookup):
        """
        Retrieve profile stats for a user.
        The `lookup` parameter is polymorphic and can be either:
        1. A hex-encoded Ethereum wallet address (e.g., '0x123...')
        2. A user's custom username (e.g., 'john_doe')
        
        To prevent MultipleObjectsReturned (shadowing 500s) if a username matches another
        user's address, we prioritize wallet address lookup first, and then fall back to username lookup.
        """
        lookup_lower = lookup.lower()
        target_user = WalletUser.objects.filter(address=lookup_lower).first()
        if not target_user:
            target_user = get_object_or_404(WalletUser, username__iexact=lookup_lower)
        grant_energy(target_user)

        followers = target_user.follower_set.all().select_related("follower")
        following = target_user.following_set.all().select_related("following")

        followers_list = [f.follower.address for f in followers]
        following_list = [f.following.address for f in following]

        is_following = False

        # Import dynamically to avoid circular import issues
        from posts.models import Community
        from posts.serializers import CommunitySerializer

        owned_qs = Community.objects.filter(creator=target_user)
        member_qs = Community.objects.filter(memberships__user=target_user, memberships__status="approved")

        data = {
            "address": target_user.address,
            "username": target_user.username,
            "followers_count": len(followers_list),
            "following_count": len(following_list),
            "followers": followers_list,
            "following": following_list,
            "rep": target_user.rep,
            "energy": target_user.energy,
            "energy_cap": ENERGY_CAP,
            "communities_owned": CommunitySerializer(owned_qs, many=True).data,
            "communities_member_of": CommunitySerializer(member_qs, many=True).data,
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

class UpdateProfileView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return Response({"detail": "Authentication credentials were not provided."}, status=status.HTTP_401_UNAUTHORIZED)
            
        token = auth_header.split(" ")[1]
        try:
            access = AccessToken(token)
            req_address = access.get("address", "").lower()
            current_user = WalletUser.objects.get(address=req_address)
        except Exception:
            return Response({"detail": "Invalid token."}, status=status.HTTP_401_UNAUTHORIZED)

        new_username = request.data.get("username")
        if not new_username:
            return Response({"detail": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        error = validate_username_format(new_username)
        if error:
            return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)
            
        if WalletUser.objects.filter(username__iexact=new_username).exclude(pk=current_user.pk).exists():
            return Response({"detail": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)
            
        current_user.username = new_username
        current_user.save()
        return Response({"username": current_user.username})
