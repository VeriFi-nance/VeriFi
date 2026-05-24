"""
Tests for the Observer Design Pattern — Asset → Position notification.

Tests cover:
  - Subscription lifecycle (auto-subscribe, OneToOne enforcement, backfill)
  - Notification dispatch (only correct asset's positions are notified)
  - State transitions via notification (PENDING→ACTIVE, ACTIVE→CONFIRMED/REJECTED)
  - Automatic unsubscribe on terminal state
  - Manual close unsubscribe
  - Error isolation (one asset failure doesn't block others)
"""

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from accounts.models import WalletUser
from posts.models import (
    Asset,
    AssetSubscription,
    Community,
    CommunityMembership,
    OHLCData,
    Position,
    PositionEvent,
)
from posts.asset_updater import (
    _notify_position,
    notify_subscribers,
    update_all_assets,
    update_asset_price,
)


class ObserverTestBase(TestCase):
    """Shared setup for Observer pattern tests."""

    def setUp(self):
        # Prevent hitting real external APIs during tests by mocking fetch_ohlc_for_asset
        patcher = patch("posts.ohlc_fetcher.fetch_ohlc_for_asset", return_value=[])
        self.addCleanup(patcher.stop)
        self.mock_fetch = patcher.start()

        self.user = WalletUser.objects.create(address="0x" + "a" * 40)
        self.community = Community.objects.create(
            name="Test Community", creator=self.user
        )
        CommunityMembership.objects.create(
            community=self.community,
            user=self.user,
            status=CommunityMembership.Status.APPROVED,
        )
        self.asset_btc = Asset.objects.create(
            name="Bitcoin",
            symbol="BTC",
            market_type=Asset.MarketType.CRYPTO,
            binance_symbol="BTCUSDT",
        )
        self.asset_eth = Asset.objects.create(
            name="Ethereum",
            symbol="ETH",
            market_type=Asset.MarketType.CRYPTO,
            binance_symbol="ETHUSDT",
        )

    def _create_position(self, asset, direction="long", entry_price=100.0,
                         stop_loss=90.0, take_profit=120.0, status="pending"):
        now = timezone.now()
        pos = Position.objects.create(
            author=self.user,
            community=self.community,
            asset=asset,
            direction=direction,
            entry_price=entry_price,
            entry_interval=now + timedelta(days=7),
            stop_loss=stop_loss,
            take_profit=take_profit,
            lifetime=now + timedelta(days=30),
            status=status,
        )
        return pos


class SubscriptionLifecycleTests(ObserverTestBase):
    """Test subscribe/unsubscribe mechanics."""

    def test_subscription_created_for_position(self):
        """Creating an AssetSubscription links a Position to an Asset."""
        pos = self._create_position(self.asset_btc)
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        self.assertEqual(sub.asset, self.asset_btc)
        self.assertEqual(sub.position, pos)

    def test_one_to_one_enforced(self):
        """A Position cannot have more than one subscription (OneToOne)."""
        pos = self._create_position(self.asset_btc)
        AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        with self.assertRaises(Exception):
            AssetSubscription.objects.create(asset=self.asset_eth, position=pos)

    def test_subscription_deleted_on_position_delete(self):
        """Deleting a Position cascades to its subscription."""
        pos = self._create_position(self.asset_btc)
        AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        pos.delete()
        self.assertEqual(AssetSubscription.objects.count(), 0)

    def test_subscriber_list_on_asset(self):
        """Asset.subscriptions gives the correct subscriber list."""
        pos1 = self._create_position(self.asset_btc)
        pos2 = self._create_position(self.asset_btc)
        pos_eth = self._create_position(self.asset_eth)

        AssetSubscription.objects.create(asset=self.asset_btc, position=pos1)
        AssetSubscription.objects.create(asset=self.asset_btc, position=pos2)
        AssetSubscription.objects.create(asset=self.asset_eth, position=pos_eth)

        btc_subs = AssetSubscription.objects.filter(asset=self.asset_btc)
        eth_subs = AssetSubscription.objects.filter(asset=self.asset_eth)

        self.assertEqual(btc_subs.count(), 2)
        self.assertEqual(eth_subs.count(), 1)


class NotificationScopeTests(ObserverTestBase):
    """Test that notification only affects the correct asset's subscribers."""

    @patch("posts.asset_updater._resolve_pending")
    @patch("posts.asset_updater._resolve_active")
    def test_notify_only_targets_correct_asset(self, mock_active, mock_pending):
        """Notifying Asset BTC should not touch positions subscribed to ETH."""
        pos_btc = self._create_position(self.asset_btc)
        pos_eth = self._create_position(self.asset_eth)
        AssetSubscription.objects.create(asset=self.asset_btc, position=pos_btc)
        AssetSubscription.objects.create(asset=self.asset_eth, position=pos_eth)

        notify_subscribers(self.asset_btc, [])

        # Only BTC position should have been processed
        self.assertEqual(mock_pending.call_count, 1)
        called_position = mock_pending.call_args[0][0]
        self.assertEqual(called_position.id, pos_btc.id)

    @patch("posts.asset_updater._resolve_pending")
    def test_resolved_positions_not_notified(self, mock_pending):
        """Positions in terminal states should not be notified."""
        pos = self._create_position(self.asset_btc, status="confirmed")
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        notify_subscribers(self.asset_btc, [])

        # _resolve_pending should NOT be called (position is already resolved)
        mock_pending.assert_not_called()
        # Stale subscription should be cleaned up
        self.assertFalse(AssetSubscription.objects.filter(id=sub.id).exists())


class StateTransitionTests(ObserverTestBase):
    """Test that notification triggers correct state transitions."""

    def test_pending_to_active_on_entry_hit(self):
        """PENDING position transitions to ACTIVE when entry price is hit in OHLC."""
        pos = self._create_position(
            self.asset_btc, direction="long", entry_price=100.0,
            stop_loss=90.0, take_profit=120.0,
        )
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        # Create OHLC data where low hits entry price
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="1d",
            open=105.0, high=110.0, low=99.0, close=102.0,
        )

        _notify_position(pos, [], sub)
        pos.refresh_from_db()

        self.assertEqual(pos.status, Position.Status.ACTIVE)
        # Subscription should still exist (position is ACTIVE, not terminal)
        self.assertTrue(AssetSubscription.objects.filter(id=sub.id).exists())

    def test_active_to_confirmed_on_tp_hit(self):
        """ACTIVE position transitions to CONFIRMED when take-profit is hit."""
        pos = self._create_position(
            self.asset_btc, direction="long", entry_price=100.0,
            stop_loss=90.0, take_profit=120.0, status="active",
        )
        # Create entry triggered event so resolution knows the trigger date
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_date": date.today().isoformat()},
        )
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        # Create OHLC data where high hits take-profit
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="1d",
            open=105.0, high=125.0, low=102.0, close=122.0,
        )

        _notify_position(pos, [], sub)
        pos.refresh_from_db()

        self.assertEqual(pos.status, Position.Status.CONFIRMED)
        # Subscription should be deleted (terminal state = unsubscribe)
        self.assertFalse(AssetSubscription.objects.filter(id=sub.id).exists())

    def test_active_to_rejected_on_sl_hit(self):
        """ACTIVE position transitions to REJECTED when stop-loss is hit."""
        pos = self._create_position(
            self.asset_btc, direction="long", entry_price=100.0,
            stop_loss=90.0, take_profit=120.0, status="active",
        )
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_date": date.today().isoformat()},
        )
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        # Create OHLC data where low hits stop-loss
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="1d",
            open=95.0, high=97.0, low=88.0, close=89.0,
        )

        _notify_position(pos, [], sub)
        pos.refresh_from_db()

        self.assertEqual(pos.status, Position.Status.REJECTED)
        self.assertFalse(AssetSubscription.objects.filter(id=sub.id).exists())

    def test_ambiguity_fallback_loop(self):
        """If a daily candle hits both SL and TP, it falls back to 1h -> 15m to resolve."""
        pos = self._create_position(
            self.asset_btc, direction="long", entry_price=100.0,
            stop_loss=90.0, take_profit=120.0, status="active",
        )
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_date": timezone.now().date().isoformat()},
        )
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        # 1. Ambiguous Daily Candle
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="1d",
            open=105.0, high=125.0, low=85.0, close=102.0,  # Hits both 90 and 120
        )
        
        # 2. Ambiguous 1h Candle (Still ambiguous!)
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="1h",
            open=105.0, high=125.0, low=85.0, close=102.0,
        )
        
        # 3. Resolving 15m Candle (Hits TP, misses SL)
        OHLCData.objects.create(
            asset=self.asset_btc,
            timestamp=timezone.now(),
            interval="15m",
            open=105.0, high=125.0, low=95.0, close=120.0,
        )

        _notify_position(pos, [], sub)
        pos.refresh_from_db()

        # Should be CONFIRMED because the 15m candle hit TP and not SL
        self.assertEqual(pos.status, Position.Status.CONFIRMED)
        self.assertFalse(AssetSubscription.objects.filter(id=sub.id).exists())

    def test_ambiguity_fallback_worst_case(self):
        """If ambiguous down to 1m, resolves to SL (worst case) and sets ambiguous flag."""
        pos = self._create_position(
            self.asset_btc, direction="long", entry_price=100.0,
            stop_loss=90.0, take_profit=120.0, status="active",
        )
        PositionEvent.objects.create(
            position=pos,
            event_type=PositionEvent.EventType.ENTRY_TRIGGERED,
            details={"trigger_date": timezone.now().date().isoformat()},
        )
        sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

        for interval in ["1d", "1h", "15m", "1m"]:
            OHLCData.objects.create(
                asset=self.asset_btc,
                timestamp=timezone.now(),
                interval=interval,
                open=105.0, high=125.0, low=85.0, close=102.0,  # Ambiguous
            )

        _notify_position(pos, [], sub)
        pos.refresh_from_db()

        self.assertEqual(pos.status, Position.Status.REJECTED)
        
        # Check event for ambiguous flag
        resolution_event = pos.events.filter(event_type=PositionEvent.EventType.RESOLUTION).last()
        self.assertTrue(resolution_event.details.get("ambiguous", False))


class UnsubscribeTests(ObserverTestBase):
    """Test that unsubscribe happens correctly on terminal states."""

    def test_unsubscribe_on_terminal_state(self):
        """Subscription is deleted when position reaches any terminal state."""
        terminal_statuses = ["confirmed", "rejected", "expired", "missed", "closed_early"]

        for status_value in terminal_statuses:
            pos = self._create_position(self.asset_btc, status=status_value)
            sub = AssetSubscription.objects.create(asset=self.asset_btc, position=pos)

            _notify_position(pos, [], sub)

            self.assertFalse(
                AssetSubscription.objects.filter(id=sub.id).exists(),
                f"Subscription should be deleted for terminal status '{status_value}'",
            )


class UpdateAllAssetsTests(ObserverTestBase):
    """Test the full orchestrator."""

    @patch("posts.asset_updater.fetch_ohlc_for_asset")
    def test_update_all_assets_returns_summary(self, mock_fetch):
        """update_all_assets() returns a summary dict with correct counts."""
        mock_fetch.return_value = []

        total_assets = Asset.objects.count()
        results = update_all_assets()

        self.assertIn("assets_updated", results)
        self.assertIn("assets_failed", results)
        self.assertIn("total_notified", results)
        self.assertIn("total_transitioned", results)
        # All assets in the DB should be updated
        self.assertEqual(results["assets_updated"], total_assets)

    @patch("posts.asset_updater.fetch_ohlc_for_asset")
    def test_one_asset_failure_doesnt_block_others(self, mock_fetch):
        """If fetching fails for one asset, other assets should still be updated."""
        from posts.ohlc_fetcher import OHLCFetchError

        # Create a special asset that will fail
        failing_asset = Asset.objects.create(
            name="FailCoin", symbol="FAIL", market_type=Asset.MarketType.CRYPTO,
        )

        def side_effect(asset, start, end, interval=None):
            if asset.id == failing_asset.id:
                raise OHLCFetchError("All providers down")
            return []

        mock_fetch.side_effect = side_effect

        total_assets = Asset.objects.count()
        results = update_all_assets()

        self.assertEqual(results["assets_failed"], 1)
        self.assertEqual(results["assets_updated"], total_assets - 1)
        # Failing asset's last_price_update should be None
        failing_asset.refresh_from_db()
        self.assertIsNone(failing_asset.last_price_update)
        # ETH should be updated
        self.asset_eth.refresh_from_db()
        self.assertIsNotNone(self.asset_eth.last_price_update)


class BackfillSubscriptionsTests(ObserverTestBase):
    """Test the backfill management command."""

    def test_backfill_creates_subscriptions_for_active_positions(self):
        """Backfill creates subscriptions for PENDING and ACTIVE positions."""
        from django.core.management import call_command
        from io import StringIO

        pos_pending = self._create_position(self.asset_btc, status="pending")
        pos_active = self._create_position(self.asset_btc, status="active")
        pos_confirmed = self._create_position(self.asset_eth, status="confirmed")

        self.assertEqual(AssetSubscription.objects.count(), 0)

        out = StringIO()
        call_command("backfill_subscriptions", stdout=out)

        # Only PENDING and ACTIVE should get subscriptions
        self.assertEqual(AssetSubscription.objects.count(), 2)
        self.assertTrue(AssetSubscription.objects.filter(position=pos_pending).exists())
        self.assertTrue(AssetSubscription.objects.filter(position=pos_active).exists())
        self.assertFalse(AssetSubscription.objects.filter(position=pos_confirmed).exists())

    def test_backfill_is_idempotent(self):
        """Running backfill twice doesn't create duplicate subscriptions."""
        from django.core.management import call_command
        from io import StringIO

        self._create_position(self.asset_btc, status="pending")

        call_command("backfill_subscriptions", stdout=StringIO())
        call_command("backfill_subscriptions", stdout=StringIO())

        self.assertEqual(AssetSubscription.objects.count(), 1)
