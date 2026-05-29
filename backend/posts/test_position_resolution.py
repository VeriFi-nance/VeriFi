from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from unittest.mock import patch, MagicMock

from posts.models import Position, PositionEvent, Asset, Community, CommunityMembership
from accounts.models import WalletUser
from posts.position_resolution import _resolve_pending, _resolve_active, calculate_pnl

class PositionResolutionTestCase(TestCase):
    def setUp(self):
        self.creator_user = WalletUser.objects.create(address="0xcreator00000000000000000000000000000000")
        self.community = Community.objects.create(
            name="Test Community",
            creator=self.creator_user,
            privacy_type=Community.PrivacyType.PUBLIC
        )
        self.asset = Asset.objects.create(
            symbol="BTC",
            name="Bitcoin",
            market_type=Asset.MarketType.CRYPTO,
            provider="binance",
            binance_symbol="BTCUSDT"
        )
        self.now = timezone.now()

    def create_position(self, direction, entry_price, sl, tp, status=Position.Status.PENDING):
        return Position.objects.create(
            author=self.creator_user,
            community=self.community,
            asset=self.asset,
            direction=direction,
            entry_price=entry_price,
            entry_interval=self.now + timedelta(days=2),
            stop_loss=sl,
            take_profit=tp,
            lifetime=self.now + timedelta(days=7),
            status=status
        )

    class MockCandle:
        def __init__(self, timestamp, low, high, close=0):
            self.timestamp = timestamp
            self.low = low
            self.high = high
            self.close = close

    @patch('posts.position_resolution.get_ohlc_data')
    def test_pending_to_active_long(self, mock_get_ohlc):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000)
        
        # entry_price is 50000, so a low <= 50000 should trigger
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=51000, high=52000),
            self.MockCandle((self.now + timedelta(days=1)), low=49000, high=51000)
        ]
        
        _resolve_pending(pos, self.now)
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.ACTIVE)
        self.assertTrue(PositionEvent.objects.filter(position=pos, event_type=PositionEvent.EventType.ENTRY_TRIGGERED).exists())

    @patch('posts.position_resolution.get_ohlc_data')
    def test_pending_to_missed_long(self, mock_get_ohlc):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000)
        
        # entry_price is 50000, low never reaches it
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=51000, high=52000)
        ]
        
        _resolve_pending(pos, self.now + timedelta(days=3)) # Past entry interval
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.MISSED)

    @patch('posts.position_resolution.get_ohlc_data')
    def test_active_to_confirmed_long(self, mock_get_ohlc):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000, status=Position.Status.ACTIVE)
        PositionEvent.objects.create(position=pos, event_type=PositionEvent.EventType.ENTRY_TRIGGERED, details={"trigger_date": self.now.date().isoformat()})
        
        # TP is 60000
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=45000, high=61000)
        ]
        
        _resolve_active(pos, self.now)
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.CONFIRMED)
        self.assertEqual(pos.exit_price, 60000)
        self.assertEqual(pos.pnl_percentage, 20.0)

    @patch('posts.position_resolution.get_ohlc_data')
    def test_active_to_rejected_long(self, mock_get_ohlc):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000, status=Position.Status.ACTIVE)
        PositionEvent.objects.create(position=pos, event_type=PositionEvent.EventType.ENTRY_TRIGGERED, details={"trigger_date": self.now.date().isoformat()})
        
        # SL is 40000
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=39000, high=55000)
        ]
        
        _resolve_active(pos, self.now)
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.REJECTED)
        self.assertEqual(pos.exit_price, 40000)
        self.assertEqual(pos.pnl_percentage, -20.0)

    @patch('posts.position_resolution.get_ohlc_data')
    def test_active_conflict_resolves_to_sl(self, mock_get_ohlc):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000, status=Position.Status.ACTIVE)
        PositionEvent.objects.create(position=pos, event_type=PositionEvent.EventType.ENTRY_TRIGGERED, details={"trigger_date": self.now.date().isoformat()})
        
        # Both SL and TP hit
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=39000, high=61000)
        ]
        
        _resolve_active(pos, self.now)
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.REJECTED)
        self.assertEqual(pos.exit_price, 40000)

    @patch('posts.position_resolution.fetch_current_price')
    @patch('posts.position_resolution.get_ohlc_data')
    def test_active_to_expired(self, mock_get_ohlc, mock_fetch):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000, status=Position.Status.ACTIVE)
        PositionEvent.objects.create(position=pos, event_type=PositionEvent.EventType.ENTRY_TRIGGERED, details={"trigger_date": self.now.date().isoformat()})
        
        mock_get_ohlc.return_value = [
            self.MockCandle(self.now, low=45000, high=55000, close=48000)
        ]
        
        _resolve_active(pos, self.now + timedelta(days=8)) # Past lifetime
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.EXPIRED)
        self.assertEqual(pos.exit_price, 48000)
        self.assertEqual(pos.pnl_percentage, -4.0)

    def test_active_without_trigger_event_raises_assertion_error(self):
        pos = self.create_position(Position.Direction.LONG, 50000, 40000, 60000, status=Position.Status.ACTIVE)
        # No ENTRY_TRIGGERED event is created
        with self.assertRaises(AssertionError) as ctx:
            _resolve_active(pos, self.now)
        self.assertIn(
            f"The position #{pos.id} you tried to resolve active is still not triggered. You cant resolve_active an untriggered event.",
            str(ctx.exception)
        )

    def test_calculate_pnl(self):
        self.assertEqual(calculate_pnl(Position.Direction.LONG, 100, 120), 20.0)
        self.assertEqual(calculate_pnl(Position.Direction.LONG, 100, 80), -20.0)
        self.assertEqual(calculate_pnl(Position.Direction.SHORT, 100, 80), 20.0)
        self.assertEqual(calculate_pnl(Position.Direction.SHORT, 100, 120), -20.0)
