from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from posts.models import Asset
from posts.ohlc_fetcher import OHLCFetchError, _try_crypto_chain


class CryptoOHLCFallbackTests(TestCase):
    def setUp(self):
        self.start = datetime(2026, 5, 30, tzinfo=timezone.utc)
        self.end = datetime(2026, 5, 31, tzinfo=timezone.utc)
        self.asset = Asset(
            symbol="ETH",
            name="Ethereum",
            market_type=Asset.MarketType.CRYPTO,
            provider=Asset.Provider.COINGECKO,
            provider_symbol="ethereum",
            quote_currency="USD",
            binance_symbol="ETHUSDT",
            kucoin_symbol="ETH-USDT",
            kraken_pair="ETHUSD",
            twelvedata_symbol="ETH/USD",
        )

    @patch("posts.ohlc_fetcher._fetch_kraken_ohlc")
    def test_kraken_is_tried_first(self, mock_kraken):
        mock_kraken.return_value = [{"timestamp": self.start, "open": 1, "high": 2, "low": 1, "close": 2}]

        rows = _try_crypto_chain(self.asset, self.start, self.end)

        mock_kraken.assert_called_once()
        self.assertEqual(len(rows), 1)

    @patch("posts.ohlc_fetcher._fetch_coingecko_ohlc")
    @patch("posts.ohlc_fetcher._fetch_kraken_ohlc")
    def test_coingecko_used_when_kraken_fails(self, mock_kraken, mock_coingecko):
        mock_kraken.side_effect = OHLCFetchError("Kraken unavailable")
        mock_coingecko.return_value = [{"timestamp": self.start, "open": 1, "high": 2, "low": 1, "close": 2}]

        rows = _try_crypto_chain(self.asset, self.start, self.end)

        mock_kraken.assert_called_once()
        mock_coingecko.assert_called_once()
        self.assertEqual(len(rows), 1)

    @patch("posts.ohlc_fetcher._fetch_binance_ohlc")
    @patch("posts.ohlc_fetcher._fetch_kucoin_ohlc")
    @patch("posts.ohlc_fetcher._fetch_twelvedata_ohlc")
    @patch("posts.ohlc_fetcher._fetch_coingecko_ohlc")
    @patch("posts.ohlc_fetcher._fetch_kraken_ohlc")
    def test_binance_is_last_resort(self, mock_kraken, mock_coingecko, mock_twelve, mock_kucoin, mock_binance):
        mock_kraken.side_effect = OHLCFetchError("451")
        mock_coingecko.side_effect = OHLCFetchError("rate limited")
        mock_twelve.side_effect = OHLCFetchError("no key")
        mock_kucoin.side_effect = OHLCFetchError("451")
        mock_binance.return_value = [{"timestamp": self.start, "open": 1, "high": 2, "low": 1, "close": 2}]

        rows = _try_crypto_chain(self.asset, self.start, self.end)

        mock_binance.assert_called_once()
        self.assertEqual(len(rows), 1)

    @patch("posts.ohlc_fetcher._fetch_binance_ohlc")
    @patch("posts.ohlc_fetcher._fetch_coingecko_ohlc")
    @patch("posts.ohlc_fetcher._fetch_kraken_ohlc")
    def test_provider_symbol_enables_coingecko_without_kraken(self, mock_kraken, mock_coingecko, mock_binance):
        self.asset.kraken_pair = ""
        mock_coingecko.return_value = [{"timestamp": self.start, "open": 1, "high": 2, "low": 1, "close": 2}]

        rows = _try_crypto_chain(self.asset, self.start, self.end)

        mock_kraken.assert_not_called()
        mock_coingecko.assert_called_once()
        mock_binance.assert_not_called()
        self.assertEqual(len(rows), 1)
