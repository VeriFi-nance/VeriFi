"""Model G rep market tests — parity with simulator_i.py."""
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.energy import grant_energy, spend, ENERGY_CAP
from accounts.models import WalletUser

from . import rep_market
from .models import Asset, ClaimMarket, ClaimStake, HardClaim


def _mk_user(idx, rep=1000.0):
    u = WalletUser.objects.create(
        address=f"0x{idx:040x}", rep=rep, energy=4.0,
        last_energy_grant=timezone.now(),
    )
    return u


def _mk_asset():
    return Asset.objects.create(
        name="BTC", symbol="BTC", description="",
        market_type=Asset.MarketType.CRYPTO,
        provider=Asset.Provider.COINGECKO,
        provider_symbol="bitcoin",
    )


def _mk_claim(author):
    asset = _mk_asset()
    return HardClaim.objects.create(
        author=author, asset=asset, direction="bullish",
        percentage=10.0, until=date.today() + timedelta(days=30),
    )


class CPMMMathTests(TestCase):
    def test_locked_payout_invariant(self):
        """Locked reward: later buyers do not move first buyer's payout."""
        creator = _mk_user(1)
        yes_traders = [_mk_user(i) for i in range(2, 6)]
        no_voters = [_mk_user(i) for i in range(20, 24)]
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 10.0)

        first = rep_market.buy(market, yes_traders[0], "YES")
        first_shares = first.shares

        for t in yes_traders[1:]:
            rep_market.buy(market, t, "YES")
        for u in no_voters:
            rep_market.buy(market, u, "NO")

        deltas = rep_market.resolve(market, "YES")
        # Delta credited at resolution = shares (locked payout, invariant).
        self.assertAlmostEqual(deltas[yes_traders[0].pk], first_shares, places=6)

    def test_refund_if_trivial_no_dissenters(self):
        """All YES voters, NO < 3 → all refunded."""
        creator = _mk_user(1)
        others = [_mk_user(i) for i in range(2, 7)]
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 10.0)
        for u in others:
            rep_market.buy(market, u, "YES")

        rep_pre = {u.pk: WalletUser.objects.get(pk=u.pk).rep for u in [creator, *others]}
        rep_market.resolve(market, "YES")
        market.refresh_from_db()
        self.assertTrue(market.refunded_trivial)
        # Each user gets rep_paid_gross back. Net change vs pre-buy = -burn-listing only for creator,
        # -burn only for traders. After refund, rep returns to (pre_create - listing - burn) for creator
        # and (pre_buy - burn) for traders, where their rep_paid_gross was credited back.
        # Just check: creator final rep == 1000 - LISTING_FEE - burn_creator = 1000 - 2 - 0.5
        creator_final = WalletUser.objects.get(pk=creator.pk).rep
        # Creator: -listing(2) - burn(0.5 on 10 stake) = -2.5
        self.assertAlmostEqual(creator_final, 1000 - 2 - 0.5, places=6)
        # Trader: -burn(0.5 on 10) = -0.5
        trader_final = WalletUser.objects.get(pk=others[0].pk).rep
        self.assertAlmostEqual(trader_final, 1000 - 0.5, places=6)

    def test_refund_if_trivial_too_few_total(self):
        creator = _mk_user(1)
        no_voter1 = _mk_user(2)
        no_voter2 = _mk_user(3)
        no_voter3 = _mk_user(4)
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 10.0)
        # 4 total stakers (creator + 3 NO) — below MIN_TOTAL_VOTERS=5
        rep_market.buy(market, no_voter1, "NO")
        rep_market.buy(market, no_voter2, "NO")
        rep_market.buy(market, no_voter3, "NO")
        rep_market.resolve(market, "NO")
        market.refresh_from_db()
        self.assertTrue(market.refunded_trivial)

    def test_creator_cut_on_win(self):
        creator = _mk_user(1)
        yes_voters = [_mk_user(i) for i in range(2, 5)]   # 3 YES voters + creator
        no_voters = [_mk_user(i) for i in range(20, 25)]  # 5 NO voters
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 10.0)
        for u in yes_voters:
            rep_market.buy(market, u, "YES")
        for u in no_voters:
            rep_market.buy(market, u, "NO")

        # Pre-resolve creator rep
        creator_pre = WalletUser.objects.get(pk=creator.pk).rep

        # Creator's stake on YES
        creator_stake = ClaimStake.objects.get(market=market, user=creator)
        creator_shares = creator_stake.shares

        # Losers' net pool
        losers_net = sum(
            s.rep_paid_net for s in ClaimStake.objects.filter(market=market, side="NO")
        )
        expected_cut = rep_market.CREATOR_CUT_PCT * losers_net
        rep_market.resolve(market, "YES")
        creator_post = WalletUser.objects.get(pk=creator.pk).rep
        # creator received shares + cut
        self.assertAlmostEqual(creator_post - creator_pre,
                               creator_shares + expected_cut, places=6)

    def test_creator_keeps_pool_at_50_50(self):
        """Mirror trick: after creator joins, yes_price should equal 0.5."""
        creator = _mk_user(1)
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 25.0)
        self.assertAlmostEqual(rep_market.yes_price(market), 0.5, places=9)
        self.assertAlmostEqual(market.y_reserve, market.n_reserve, places=9)

    def test_locked_invariance_against_later_buyers(self):
        """First trader's shares should match a CPMM compute on the post-creator state."""
        creator = _mk_user(1)
        first = _mk_user(2)
        late = [_mk_user(i) for i in range(3, 8)]
        claim = _mk_claim(creator)
        market = rep_market.init_market(claim, creator, "YES", 10.0)

        # Compute expected shares for first BEFORE any other buy
        y_pre, n_pre = market.y_reserve, market.n_reserve
        net = rep_market.TRADER_STAKE * (1 - rep_market.BURN_FEE)
        expected_shares = net + (y_pre + net) * net / (n_pre + 2 * net)

        first_stake = rep_market.buy(market, first, "YES")
        self.assertAlmostEqual(first_stake.shares, expected_shares, places=6)

        for u in late:
            rep_market.buy(market, u, "YES")

        # First's shares unchanged on disk
        first_stake.refresh_from_db()
        self.assertAlmostEqual(first_stake.shares, expected_shares, places=6)


class EnergyTests(TestCase):
    def test_spend_decrements(self):
        u = _mk_user(99)
        self.assertEqual(u.energy, 4.0)
        self.assertTrue(spend(u, 1))
        WalletUser.objects.get(pk=u.pk).refresh_from_db()
        u.refresh_from_db()
        self.assertEqual(u.energy, 3.0)

    def test_spend_insufficient(self):
        u = _mk_user(100)
        u.energy = 0.0
        u.last_energy_grant = timezone.now()
        u.save()
        self.assertFalse(spend(u, 1))

    def test_grant_adds_energy(self):
        u = _mk_user(101)
        u.energy = 0.0
        u.last_energy_grant = timezone.now() - timedelta(days=10)
        u.save()
        grant_energy(u)
        u.refresh_from_db()
        self.assertEqual(u.energy, 30.0)
