import os
import django
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import RequestFactory
from posts.views import HardClaimResolveView
from posts.models import HardClaim
from accounts.models import WalletUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

admin_address = settings.ADMIN_ADDRESSES[0] if settings.ADMIN_ADDRESSES else "0x0"
admin_user, _ = WalletUser.objects.get_or_create(address=admin_address.lower(), defaults={'username': 'admin'})
refresh = RefreshToken.for_user(admin_user)
access_token = refresh.access_token
access_token["address"] = admin_user.address

claim = HardClaim.objects.filter(status='undetermined').first()
if claim:
    print(f"Testing resolve endpoint for claim {claim.id} (until: {claim.until})...")
    factory = RequestFactory()
    request = factory.post(f'/api/posts/hard-claims/{claim.id}/resolve/', HTTP_AUTHORIZATION=f'Bearer {str(access_token)}')
    view = HardClaimResolveView.as_view()
    
    try:
        response = view(request, pk=claim.id)
        print("Status code:", response.status_code)
        if hasattr(response, 'data'):
            print("Response Data:", response.data)
        else:
            print("Response:", response.content)
    except Exception as e:
        import traceback
        traceback.print_exc()
else:
    print("No undetermined claims.")
