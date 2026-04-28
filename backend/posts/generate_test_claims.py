import os
import sys
import django
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 1. Initialize Django setup so we can use the ORM in a standalone script
# Add the project root (backend/) to sys.path so Python can find the 'core' package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

# Import your models and resolution functions
from accounts.models import WalletUser
from posts.models import Asset, Post, HardClaim, HardClaimEvent
from posts.resolution import fetch_price_for_time, fetch_peak_price, ResolutionError

def generate_and_save_historical_claims():
    now = datetime.now(timezone.utc)
    two_months_ago = now - timedelta(days=60)
    one_month_ago = now - timedelta(days=30)
    
    # Define the assets we want to query
    asset_symbols = ["BTC", "ETH"]

    # 2. Get or create a system user to author these automated claims
    author, _ = WalletUser.objects.get_or_create(
        address="0xsystem_automated_generator"
    )

    for symbol in asset_symbols:
        try:
            # Fetch the actual Asset model from the database
            asset = Asset.objects.get(symbol=symbol)
        except Asset.DoesNotExist:
            print(f"⚠️ Asset {symbol} not found in DB. Skipping.")
            continue

        # Format instrument for the resolution fetchers
        instrument = {
            "symbol": asset.symbol,
            "provider": asset.provider,
            "provider_symbol": asset.provider_symbol,
            "quote_currency": asset.quote_currency
        }
        
        try:
            ref_price, _ = fetch_price_for_time(instrument, two_months_ago)
            peak_bullish = fetch_peak_price(instrument, two_months_ago, one_month_ago, "bullish")
            peak_bearish = fetch_peak_price(instrument, two_months_ago, one_month_ago, "bearish")
        except ResolutionError as e:
            print(f"❌ Error fetching data for {symbol}: {e.message}")
            continue

        actual_bullish_pct = ((peak_bullish - ref_price) / ref_price) * 100
        actual_bearish_pct = ((peak_bearish - ref_price) / ref_price) * 100
        
        # Add a dummy future date at the top of the loop to bypass the initial DB constraint
        dummy_future_date = (now + timedelta(days=1)).date()

        # --- GENERATE CLAIM 1 (Guaranteed to be Confirmed later) ---
        if actual_bullish_pct > abs(actual_bearish_pct):
            direction_1 = "bullish"
            target_pct_1 = round(actual_bullish_pct / 2, 2)
        else:
            direction_1 = "bearish"
            target_pct_1 = round(abs(actual_bearish_pct) / 2, 2)

        # Create a parent Post so the claim appears in the frontend feed
        post_1 = Post.objects.create(
            author=author,
            content=f"I'm {direction_1} on {symbol} — expecting at least {target_pct_1}% move."
        )
        Post.objects.filter(id=post_1.id).update(created_at=two_months_ago)

        claim_1 = HardClaim.objects.create(
            author=author,
            post=post_1,
            asset=asset,
            direction=direction_1,
            percentage=target_pct_1,
            until=dummy_future_date,  # Use future date to satisfy creation constraint
            status=HardClaim.Status.UNDETERMINED
        )
        
        # Now backdate BOTH fields directly in the DB (bypassing auto_now_add)
        HardClaim.objects.filter(id=claim_1.id).update(
            created_at=two_months_ago,
            until=one_month_ago.date()
        )
        
        HardClaimEvent.objects.create(
            hard_claim=claim_1,
            event_type=HardClaimEvent.EventType.CREATION,
            details={"note": "Auto-generated historical claim (Target: Will pass)"}
        )
        print(f"Saved Correct Claim with ID {claim_1.id} (Post {post_1.id}): {symbol} {direction_1} {target_pct_1}%")

        # --- GENERATE CLAIM 2 (Guaranteed to be Rejected later) ---
        direction_2 = "bullish"
        target_pct_2 = round(actual_bullish_pct + 10.0, 2)
        if target_pct_2 <= 0: 
            target_pct_2 = 5.0 

        # Create a parent Post so the claim appears in the frontend feed
        post_2 = Post.objects.create(
            author=author,
            content=f"Calling a big {direction_2} move on {symbol} — at least {target_pct_2}% upside."
        )
        Post.objects.filter(id=post_2.id).update(created_at=two_months_ago)

        claim_2 = HardClaim.objects.create(
            author=author,
            post=post_2,
            asset=asset,
            direction=direction_2,
            percentage=target_pct_2,
            until=dummy_future_date,  # Use future date to satisfy creation constraint
            status=HardClaim.Status.UNDETERMINED
        )
        
        # Backdate both fields simultaneously 
        HardClaim.objects.filter(id=claim_2.id).update(
            created_at=two_months_ago,
            until=one_month_ago.date()
        )

        HardClaimEvent.objects.create(
            hard_claim=claim_2,
            event_type=HardClaimEvent.EventType.CREATION,
            details={"note": "Auto-generated historical claim (Target: Will fail)"}
        )
        print(f"Saved Incorrect Claim with ID {claim_2.id} (Post {post_2.id}): {symbol} {direction_2} {target_pct_2}%")
        print("-" * 40)

if __name__ == "__main__":
    generate_and_save_historical_claims()
    print("\nDone! Claims are now in the database as 'undetermined'.")
    print("You can now test the resolution endpoint on them.")