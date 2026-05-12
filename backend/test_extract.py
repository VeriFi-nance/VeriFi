import sys
import os
import django
sys.path.append('/Users/ardasaygan/Desktop/School_Materials/Signance/Signance/backend')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from posts.claim_extraction import rule_based_claims_from_prompt

claims1 = rule_based_claims_from_prompt("BTC will go up 10% by 2026-12-31")
print("1:", [c.to_dict() for c in claims1])

claims2 = rule_based_claims_from_prompt("BTC will go up 10% by 2026-12-29")
print("2:", [c.to_dict() for c in claims2])
