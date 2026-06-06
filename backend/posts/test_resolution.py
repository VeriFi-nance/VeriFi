from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch, MagicMock
from django.test import TestCase
from posts.models import Asset, Post, HardClaim, HardClaimEvent, OHLCData
from posts.resolution import (
    _effective_direction,
    _fetch_binance_price,
    _normalize_direction_and_value_type,
    reconcile_claim_fields,
    display_percentage,
    normalize_claim_for_resolution,
    preview_resolution,
    resolve_hard_claim,
    reassess_hard_claim,
    capture_reference_price,
    fetch_reference_price,
    ResolutionError,
)
from posts.ohlc_fetcher import OHLCFetchError

from accounts.models import WalletUser
from django.utils import timezone

class ResolutionTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
            kucoin_symbol="BTC-USDT",
            kraken_pair="XBTUSD",
        )
        self.author = WalletUser.objects.create(address="0x123")
        self.post = Post.objects.create(
            author=self.author,
            content="Content",
        )
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage="10.00",
            until=(timezone.now() + timedelta(days=1)).date(), # initially future to pass create
            status=HardClaim.Status.UNDETERMINED,
        )
        # Backdate so it counts as due; midnight UTC so mixed resolution can use daily bars.
        created_at = (timezone.now() - timedelta(days=5)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        HardClaim.objects.filter(id=self.claim.id).update(
            created_at=created_at,
            until=(timezone.now() - timedelta(days=2)).date(),
        )
        self.claim.refresh_from_db()

    def test_normalize_already_resolved(self):
        self.claim.status = HardClaim.Status.CONFIRMED
        with self.assertRaisesMessage(ResolutionError, "Claim is already resolved."):
            normalize_claim_for_resolution(self.claim)
            
    def test_normalize_not_due(self):
        self.claim.until = date.today() + timedelta(days=1)
        with self.assertRaisesMessage(ResolutionError, "Claim cannot be resolved before its due date."):
            normalize_claim_for_resolution(self.claim)

    def test_normalize_unsupported_direction(self):
        self.claim.direction = "sideways"
        self.claim.value_type = ""
        self.claim.save()
        with self.assertRaisesMessage(ResolutionError, "Only bullish and bearish"):
            normalize_claim_for_resolution(self.claim)

    def test_normalize_derives_direction_from_value_type(self):
        self.claim.direction = ""
        self.claim.value_type = "PERCENTAGE_DOWN"
        self.claim.save()
        payload = normalize_claim_for_resolution(self.claim)
        self.assertEqual(payload["target"]["direction"], "bearish")

    def test_effective_direction_prefers_bearish_over_mismatched_value_type(self):
        self.claim.direction = "Bearish"
        self.claim.value_type = "PERCENTAGE_UP"
        self.claim.save()
        self.assertEqual(_effective_direction(self.claim), "bearish")
        direction, value_type = _normalize_direction_and_value_type(
            self.claim.direction,
            self.claim.value_type,
        )
        self.assertEqual(direction, "bearish")
        self.assertEqual(value_type, "PERCENTAGE_DOWN")

    def test_price_claim_infers_bearish_when_target_below_reference(self):
        self.claim.value_type = "PRICE"
        self.claim.direction = "bullish"
        self.claim.percentage = 50000.0
        self.claim.payda = "USD"
        self.claim.reference_price = 100000.0
        self.claim.save()
        direction, value_type = reconcile_claim_fields(self.claim)
        self.assertEqual(value_type, "PRICE")
        self.assertEqual(direction, "bearish")

    def test_display_percentage_for_percent_claim(self):
        self.claim.percentage = 10.0
        self.claim.save()
        self.assertEqual(display_percentage(self.claim), 10.0)

    @patch("posts.resolution.fetch_reference_price")
    def test_display_percentage_converts_price_target(self, mock_ref):
        self.claim.value_type = "PRICE"
        self.claim.direction = "bearish"
        self.claim.percentage = 50000.0
        self.claim.reference_price = 60000.0
        self.claim.save()
        self.assertEqual(display_percentage(self.claim), 16.7)

    @patch("posts.resolution.get_ohlc_data")
    @patch("posts.resolution.fetch_reference_price")
    def test_bearish_target_is_below_reference_with_mismatched_value_type(
        self, mock_ref, mock_ohlc
    ):
        self.claim.direction = "bearish"
        self.claim.value_type = "PERCENTAGE_UP"
        self.claim.percentage = 10.0
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        self._seed_ohlc(base_price=1000.0, days=5, trend_pct=0.0)
        mock_ohlc.return_value = list(
            OHLCData.objects.filter(asset=self.asset).order_by("timestamp")
        )
        result = preview_resolution(self.claim)
        self.assertEqual(result["prices"]["reference"], 1000.0)
        self.assertEqual(result["prices"]["target"], 900.0)

    @patch("posts.resolution.get_ohlc_data")
    @patch("posts.resolution.fetch_reference_price")
    def test_preview_resolution_maps_ohlc_fetch_error(self, mock_ref, mock_ohlc):
        mock_ref.return_value = (1000.0, "http://mock.ref")
        mock_ohlc.side_effect = OHLCFetchError("all sources failed")
        with self.assertRaises(ResolutionError) as ctx:
            preview_resolution(self.claim)
        self.assertEqual(ctx.exception.code, "NO_OHLC_DATA")

    def _seed_ohlc(self, base_price=1000.0, days=5, trend_pct=2.0):
        """Create OHLC rows for the claim period with a simple uptrend."""
        start = self.claim.created_at.date()
        rows = []
        for i in range(days):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = base_price * (1 + trend_pct * i / 100)
            rows.append(OHLCData(
                asset=self.asset,
                timestamp=d,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price * 1.01,
            ))
        OHLCData.objects.bulk_create(rows)
        return rows

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bullish_confirmed(self, mock_ohlc_fetch, mock_ref):
        """If OHLC high reaches target, claim is confirmed."""
        mock_ref.return_value = (1000.0, "http://mock.ref")
        # Seed OHLC where high on day 4 exceeds 10% target (1100)
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 30  # 1000, 1030, 1060, 1090, 1120
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 10,
            )
        mock_ohlc_fetch.return_value = []  # Already in DB, won't be called

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertGreater(len(result["hit_days"]), 0)
        self.assertIsNotNone(result["target_reached_at"])

        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, HardClaim.Status.CONFIRMED)

        events = self.claim.events.all()
        self.assertEqual(events.count(), 1)
        evt = events.last()
        self.assertEqual(evt.event_type, HardClaimEvent.EventType.RESOLUTION)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bullish_rejected(self, mock_ohlc_fetch, mock_ref):
        """If OHLC high never reaches 10% target, claim is rejected."""
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 10  # 1000, 1010, 1020, 1030, 1040 — max high = 1060
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.assertEqual(len(result["hit_days"]), 0)
        self.assertIsNone(result["target_reached_at"])
        # Closest price should exist
        self.assertIsNotNone(result["prices"]["closest"])

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_bearish_confirmed(self, mock_ohlc_fetch, mock_ref):
        """Bearish claim: low goes below target → confirmed."""
        self.claim.direction = "bearish"
        self.claim.value_type = "PERCENTAGE_DOWN"
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 - i * 30  # 1000, 970, 940, 910, 880
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 10, low=price - 20, close=price - 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)

    def test_normalize_price_claim(self):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1500.0
        self.claim.save()
        payload = normalize_claim_for_resolution(self.claim)
        self.assertEqual(payload["target"]["kind"], "price")
        self.assertEqual(payload["target"]["value"], 1500.0)
        self.assertEqual(payload["target"]["unit"], "USD")

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_price_bullish_confirmed(self, mock_ohlc_fetch, mock_ref):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1100.0
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 30
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 10,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["prices"]["target"], 1100.0)

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_resolve_price_bullish_rejected(self, mock_ohlc_fetch, mock_ref):
        self.claim.value_type = "PRICE"
        self.claim.percentage = 1200.0
        self.claim.save()
        mock_ref.return_value = (1000.0, "http://mock.ref")
        start = self.claim.created_at.date()
        for i in range(5):
            d = start + timedelta(days=i)
            if d > self.claim.until:
                break
            price = 1000 + i * 10
            OHLCData.objects.create(
                asset=self.asset, timestamp=d,
                open=price, high=price + 20, low=price - 20, close=price + 5,
            )
        mock_ohlc_fetch.return_value = []

        result = resolve_hard_claim(self.claim)
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.assertEqual(result["prices"]["target"], 1200.0)


class ResolveClaimsCommandTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
        )
        self.author = WalletUser.objects.create(address="0xabc")
        self.post = Post.objects.create(author=self.author, content="test")

    def test_due_claims_excludes_until_today(self):
        from posts.management.commands.resolve_claims import due_claims_queryset

        today_claim = HardClaim.objects.create(
            author=self.author,
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=5.0,
            until=date.today() + timedelta(days=1),
            status=HardClaim.Status.UNDETERMINED,
        )
        past = HardClaim.objects.create(
            author=self.author,
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=5.0,
            until=date.today() + timedelta(days=1),
            status=HardClaim.Status.UNDETERMINED,
        )
        HardClaim.objects.filter(id=today_claim.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=date.today(),
        )
        HardClaim.objects.filter(id=past.id).update(
            created_at=timezone.now() - timedelta(days=5),
            until=date.today() - timedelta(days=1),
        )
        due_ids = list(due_claims_queryset().values_list("id", flat=True))
        self.assertEqual(due_ids, [past.id])


class ReferencePriceTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
        )
        self.author = WalletUser.objects.create(address="0xabc")
        self.post = Post.objects.create(author=self.author, content="test")
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=3)).date(),
        )
        HardClaimEvent.objects.create(
            hard_claim=self.claim,
            event_type=HardClaimEvent.EventType.CREATION,
            details={},
        )

    @patch("posts.resolution._http_get_json")
    def test_fetch_binance_price_interpolates_within_minute(self, mock_http):
        mock_http.return_value = [[
            1780420700000,
            "67507.18000000",
            "67806.00000000",
            "67460.00000000",
            "67740.01000000",
            "0",
            1780420759999,
            "0",
            0,
            "0",
            "0",
            "0",
        ]]
        at_dt = datetime(2026, 6, 2, 17, 18, 20, tzinfo=dt_timezone.utc)
        price, url = _fetch_binance_price("BTCUSDT", at_dt)
        expected = 67507.18 + (67740.01 - 67507.18) * (20 / 60)
        self.assertAlmostEqual(price, expected, places=2)
        self.assertIn("interval=1m", url)

    @patch("posts.resolution.fetch_current_price")
    def test_capture_reference_price_persists_on_claim(self, mock_fetch):
        mock_fetch.return_value = (67507.18, "http://mock.ref")
        capture_reference_price(self.claim)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.reference_price, 67507.18)
        self.assertEqual(self.claim.reference_price_url, "http://mock.ref")
        creation = self.claim.events.get(event_type=HardClaimEvent.EventType.CREATION)
        self.assertEqual(creation.details["reference_price"], 67507.18)

    def test_fetch_reference_price_prefers_stored_value(self):
        self.claim.reference_price = 12345.67
        self.claim.reference_price_url = "stored"
        self.claim.save()
        price, url = fetch_reference_price(self.claim)
        self.assertEqual(price, 12345.67)
        self.assertEqual(url, "stored")

    @patch("posts.resolution.get_ohlc_data")
    def test_preview_resolution_uses_stored_reference_price(self, mock_ohlc):
        past_until = (timezone.now() - timedelta(days=1)).date()
        HardClaim.objects.filter(pk=self.claim.pk).update(
            created_at=timezone.now() - timedelta(days=5),
            until=past_until,
            reference_price=1000.0,
            reference_price_url="stored",
        )
        self.claim.refresh_from_db()
        start = self.claim.created_at.date()
        mock_ohlc.return_value = [
            OHLCData(
                asset=self.asset,
                timestamp=datetime.combine(start, datetime.min.time(), tzinfo=dt_timezone.utc),
                open=1000.0,
                high=1120.0,
                low=980.0,
                close=1100.0,
            )
        ]
        result = preview_resolution(self.claim)
        self.assertEqual(result["prices"]["reference"], 1000.0)
        self.assertEqual(result["prices"]["target"], 1100.0)


class CreationDayResolutionTests(TestCase):
    """Target hits must not count price action before created_at."""

    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
        )
        self.author = WalletUser.objects.create(address="0xabc")
        self.post = Post.objects.create(author=self.author, content="test")
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=1.0,
            until=(timezone.now() + timedelta(days=1)).date(),
            status=HardClaim.Status.UNDETERMINED,
            reference_price=67519.91,
            reference_price_url="stored",
        )
        created_at = datetime(2026, 6, 2, 17, 18, 20, tzinfo=dt_timezone.utc)
        HardClaim.objects.filter(pk=self.claim.pk).update(
            created_at=created_at,
            until=date(2026, 6, 3),
        )
        self.claim.refresh_from_db()

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_pre_creation_daily_high_does_not_confirm(self, mock_fetch, mock_ref):
        """Claim 32 pattern: daily high before entry must not count."""
        mock_ref.return_value = (67519.91, "stored")
        mock_fetch.return_value = []

        # Full-day bar would confirm if counted; post-entry hourly bars do not.
        OHLCData.objects.create(
            asset=self.asset,
            timestamp=datetime(2026, 6, 2, 0, 0, tzinfo=dt_timezone.utc),
            interval="1d",
            open=71315.5,
            high=71315.5,
            low=67530.1,
            close=67800.9,
        )
        OHLCData.objects.create(
            asset=self.asset,
            timestamp=datetime(2026, 6, 2, 18, 0, tzinfo=dt_timezone.utc),
            interval="1h",
            open=67500.0,
            high=67545.0,
            low=67029.5,
            close=67200.0,
        )
        OHLCData.objects.create(
            asset=self.asset,
            timestamp=datetime(2026, 6, 2, 19, 0, tzinfo=dt_timezone.utc),
            interval="1h",
            open=67200.0,
            high=67366.5,
            low=66327.3,
            close=66500.0,
        )
        OHLCData.objects.create(
            asset=self.asset,
            timestamp=datetime(2026, 6, 3, 0, 0, tzinfo=dt_timezone.utc),
            interval="1d",
            open=66669.7,
            high=67420.0,
            low=65379.8,
            close=67118.3,
        )

        result = preview_resolution(self.claim)

        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.assertEqual(result["hit_days"], [])
        self.assertEqual(result["prices"]["target"], 68195.11)
        self.assertLess(result["prices"]["closest"], result["prices"]["target"])

    @patch("posts.resolution.fetch_reference_price")
    @patch("posts.ohlc_fetcher.fetch_ohlc_for_asset")
    def test_post_creation_intraday_hit_still_confirms(self, mock_fetch, mock_ref):
        mock_ref.return_value = (1000.0, "stored")
        mock_fetch.return_value = []
        created_at = datetime(2026, 6, 2, 10, 0, tzinfo=dt_timezone.utc)
        HardClaim.objects.filter(pk=self.claim.pk).update(
            created_at=created_at,
            until=date(2026, 6, 3),
            reference_price=1000.0,
            percentage=5.0,
        )
        self.claim.refresh_from_db()

        OHLCData.objects.create(
            asset=self.asset,
            timestamp=datetime(2026, 6, 2, 11, 0, tzinfo=dt_timezone.utc),
            interval="1h",
            open=1000.0,
            high=1060.0,
            low=990.0,
            close=1050.0,
        )

        result = preview_resolution(self.claim)

        self.assertEqual(result["status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["hit_days"], ["2026-06-02"])


class ReassessResolvedClaimTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.BINANCE,
            provider_symbol="bitcoin",
            quote_currency="USD",
            binance_symbol="BTCUSDT",
        )
        self.author = WalletUser.objects.create(address="0xabc")
        self.post = Post.objects.create(author=self.author, content="test")
        self.claim = HardClaim.objects.create(
            post=self.post,
            asset=self.asset,
            direction="bullish",
            percentage=10.0,
            until=(timezone.now() + timedelta(days=3)).date(),
            status=HardClaim.Status.CONFIRMED,
            reference_price=900.0,
            reference_price_url="stored",
        )
        HardClaim.objects.filter(pk=self.claim.pk).update(
            created_at=timezone.now() - timedelta(days=5),
            until=(timezone.now() - timedelta(days=1)).date(),
        )
        self.claim.refresh_from_db()
        HardClaimEvent.objects.create(
            hard_claim=self.claim,
            event_type=HardClaimEvent.EventType.CREATION,
            details={},
        )
        HardClaimEvent.objects.create(
            hard_claim=self.claim,
            event_type=HardClaimEvent.EventType.RESOLUTION,
            details={"prices": {"reference": 900.0, "target": 990.0}},
        )

    @patch("posts.resolution.get_ohlc_data")
    def test_reassess_updates_status_and_replaces_resolution_event(self, mock_ohlc):
        start = self.claim.created_at.date()
        mock_ohlc.return_value = [
            OHLCData(
                asset=self.asset,
                timestamp=datetime.combine(start, datetime.min.time(), tzinfo=dt_timezone.utc),
                open=1000.0,
                high=1050.0,
                low=980.0,
                close=1020.0,
            )
        ]
        HardClaim.objects.filter(pk=self.claim.pk).update(reference_price=1000.0)
        self.claim.refresh_from_db()

        result = reassess_hard_claim(self.claim)

        self.assertTrue(result["status_changed"])
        self.assertEqual(result["previous_status"], HardClaim.Status.CONFIRMED)
        self.assertEqual(result["status"], HardClaim.Status.REJECTED)
        self.claim.refresh_from_db()
        self.assertEqual(self.claim.status, HardClaim.Status.REJECTED)
        self.assertEqual(
            self.claim.events.filter(event_type=HardClaimEvent.EventType.RESOLUTION).count(),
            1,
        )
        resolution = self.claim.events.get(event_type=HardClaimEvent.EventType.RESOLUTION)
        self.assertEqual(resolution.details["prices"]["reference"], 1000.0)

    def test_reassess_command_dry_run_lists_changes(self):
        from posts.management.commands.reassess_resolved_claims import Command

        with patch("posts.resolution.preview_resolution") as mock_preview:
            mock_preview.return_value = {"status": HardClaim.Status.REJECTED}
            Command().handle(dry_run=True)
            self.assertTrue(mock_preview.called)
