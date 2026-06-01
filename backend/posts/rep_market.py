"""Model G — creator-as-trader CPMM reputation market.

Direct port of `report/Rep Score Simulation/simulator_i.py` (Model I, the
final form on origin/sim/model-g) backed by the ORM.

Canonical constants from simulation.html (Source: commit 2b79401):
    VIRTUAL_SEED      = 10        virtual CPMM seed, protocol-minted
    BURN_FEE          = 0.05      5% of every trade burned
    LISTING_FEE       = 2         creator pays at claim creation, burned
    CREATOR_CUT_PCT   = 0.05      creator gets 5% of losers' net pool on win
    MIN_LOSER_VOTERS  = 3         refund all if loser side <3 distinct
    MIN_TOTAL_VOTERS  = 5         refund all if <5 total
    CREATOR_STAKE     in [10, 100]
    TRADER_STAKE      = 10
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from accounts.models import WalletUser

from .models import ClaimMarket, ClaimStake, HardClaim

VIRTUAL_SEED = 10.0
BURN_FEE = 0.05
LISTING_FEE = 2.0
CREATOR_CUT_PCT = 0.05
MIN_LOSER_VOTERS = 3
MIN_TOTAL_VOTERS = 5
CREATOR_MIN_STAKE = 10.0
CREATOR_MAX_STAKE = 100.0
TRADER_STAKE = 10.0


class MarketError(Exception):
    pass


@dataclass
class BuyPreview:
    shares: float
    entry_price: float
    locked_payout_if_win: float
    new_yes_price: float


def yes_price(market: ClaimMarket) -> float:
    return market.n_reserve / (market.y_reserve + market.n_reserve)


def _cpmm_buy(y: float, n: float, side: str, r: float) -> tuple[float, float, float]:
    """Mirror simulator.py:CPMM.buy. Returns (shares, new_y, new_n)."""
    if side == "YES":
        shares = r + (y + r) * r / (n + 2 * r)
        new_y = (y + r) * (n + r) / (n + 2 * r)
        new_n = n + 2 * r
    else:
        shares = r + (n + r) * r / (y + 2 * r)
        new_n = (n + r) * (y + r) / (y + 2 * r)
        new_y = y + 2 * r
    return shares, new_y, new_n


def preview_buy(market: ClaimMarket, side: str, rep_amount: float = TRADER_STAKE) -> BuyPreview:
    if side not in ("YES", "NO"):
        raise MarketError("side must be YES or NO")
    net = rep_amount * (1.0 - BURN_FEE)
    shares, new_y, new_n = _cpmm_buy(market.y_reserve, market.n_reserve, side, net)
    entry = (
        market.n_reserve / (market.y_reserve + market.n_reserve)
        if side == "YES"
        else market.y_reserve / (market.y_reserve + market.n_reserve)
    )
    return BuyPreview(
        shares=shares,
        entry_price=entry,
        locked_payout_if_win=shares,
        new_yes_price=new_n / (new_y + new_n),
    )


@transaction.atomic
def init_market(
    hard_claim: HardClaim,
    creator: WalletUser,
    side: str,
    stake_rep: float,
) -> ClaimMarket:
    if hasattr(hard_claim, "market"):
        raise MarketError("market_exists")
    if side not in ("YES", "NO"):
        raise MarketError("invalid_side")
    if not (CREATOR_MIN_STAKE <= stake_rep <= CREATOR_MAX_STAKE):
        raise MarketError("stake_out_of_range")

    locked_creator = WalletUser.objects.select_for_update().get(pk=creator.pk)
    total_cost = LISTING_FEE + stake_rep
    if locked_creator.rep < total_cost:
        raise MarketError("insufficient_rep")

    locked_creator.rep -= total_cost
    locked_creator.save(update_fields=["rep"])

    net = stake_rep * (1.0 - BURN_FEE)
    # Mirror trick (simulation.html:264-275): creator gets fair CPMM share
    # count from pre-buy Y=N=V pool, then BOTH reserves bumped by `net` so
    # the post-creator price stays at 50/50.
    v = VIRTUAL_SEED
    shares = net + (v + net) * net / (v + 2 * net)
    new_y = v + net
    new_n = v + net
    entry_price = 0.5

    market = ClaimMarket.objects.create(
        hard_claim=hard_claim,
        y_reserve=new_y,
        n_reserve=new_n,
        yes_outstanding=shares if side == "YES" else 0.0,
        no_outstanding=shares if side == "NO" else 0.0,
        escrow=net,
        total_burned=LISTING_FEE + (stake_rep - net),
        creator_side=side,
        creator_stake_rep=stake_rep,
        listing_fee_burned=LISTING_FEE,
    )
    ClaimStake.objects.create(
        market=market,
        user=locked_creator,
        side=side,
        rep_paid_gross=stake_rep,
        rep_paid_net=net,
        shares=shares,
        entry_price=entry_price,
        is_creator=True,
    )
    creator.rep = locked_creator.rep
    return market


@transaction.atomic
def buy(market: ClaimMarket, user: WalletUser, side: str) -> ClaimStake:
    if market.resolved:
        raise MarketError("resolved")
    if side not in ("YES", "NO"):
        raise MarketError("invalid_side")

    locked_market = ClaimMarket.objects.select_for_update().get(pk=market.pk)
    if ClaimStake.objects.filter(market=locked_market, user=user).exists():
        raise MarketError("already_staked")

    locked_user = WalletUser.objects.select_for_update().get(pk=user.pk)
    if locked_user.rep < TRADER_STAKE:
        raise MarketError("insufficient_rep")
    locked_user.rep -= TRADER_STAKE
    locked_user.save(update_fields=["rep"])

    net = TRADER_STAKE * (1.0 - BURN_FEE)
    entry_price = (
        locked_market.n_reserve / (locked_market.y_reserve + locked_market.n_reserve)
        if side == "YES"
        else locked_market.y_reserve / (locked_market.y_reserve + locked_market.n_reserve)
    )
    shares, new_y, new_n = _cpmm_buy(
        locked_market.y_reserve, locked_market.n_reserve, side, net
    )
    locked_market.y_reserve = new_y
    locked_market.n_reserve = new_n
    if side == "YES":
        locked_market.yes_outstanding += shares
    else:
        locked_market.no_outstanding += shares
    locked_market.escrow += net
    locked_market.total_burned += TRADER_STAKE - net
    locked_market.save(
        update_fields=[
            "y_reserve", "n_reserve", "yes_outstanding", "no_outstanding",
            "escrow", "total_burned",
        ]
    )

    stake = ClaimStake.objects.create(
        market=locked_market,
        user=locked_user,
        side=side,
        rep_paid_gross=TRADER_STAKE,
        rep_paid_net=net,
        shares=shares,
        entry_price=entry_price,
        is_creator=False,
    )
    user.rep = locked_user.rep
    market.y_reserve = locked_market.y_reserve
    market.n_reserve = locked_market.n_reserve
    market.yes_outstanding = locked_market.yes_outstanding
    market.no_outstanding = locked_market.no_outstanding
    market.escrow = locked_market.escrow
    market.total_burned = locked_market.total_burned
    return stake


@transaction.atomic
def resolve(market: ClaimMarket, winning_side: str) -> dict[int, float]:
    """Apply Model G payouts. Returns {user_id: rep_delta_at_resolution}.

    Per simulator_i.py:
      - If trivial (loser voters < MIN_LOSER_VOTERS or total voters <
        MIN_TOTAL_VOTERS): refund every stake at rep_paid_gross. Listing
        fee + burn are already gone.
      - Else: credit `shares` to winning-side stakers. Losers receive 0.
        If creator side won, credit creator an extra 5% of losers'
        rep_paid_net sum.
    """
    if winning_side not in ("YES", "NO"):
        raise MarketError("invalid_winning_side")
    locked_market = ClaimMarket.objects.select_for_update().get(pk=market.pk)
    if locked_market.resolved:
        raise MarketError("already_resolved")

    losing_side = "NO" if winning_side == "YES" else "YES"
    stakes = list(
        ClaimStake.objects.select_related("user").filter(market=locked_market)
    )
    loser_uids = {s.user_id for s in stakes if s.side == losing_side}
    total_uids = {s.user_id for s in stakes}

    deltas: dict[int, float] = {}
    if len(loser_uids) < MIN_LOSER_VOTERS or len(total_uids) < MIN_TOTAL_VOTERS:
        # Trivial refund — credit rep_paid_net only. Burn (and creator listing fee)
        # remain destroyed, matching simulation.html:349 `trivialNet = -burnLoss - creatorFee`.
        for s in stakes:
            deltas[s.user_id] = deltas.get(s.user_id, 0.0) + s.rep_paid_net
        locked_market.refunded_trivial = True
    else:
        for s in stakes:
            if s.side == winning_side:
                deltas[s.user_id] = deltas.get(s.user_id, 0.0) + s.shares
        creator_won_stake = next(
            (s for s in stakes if s.is_creator and s.side == winning_side), None
        )
        if creator_won_stake is not None:
            losers_pool = sum(s.rep_paid_net for s in stakes if s.side == losing_side)
            deltas[creator_won_stake.user_id] = (
                deltas.get(creator_won_stake.user_id, 0.0)
                + CREATOR_CUT_PCT * losers_pool
            )

    for uid, delta in deltas.items():
        if delta == 0:
            continue
        wu = WalletUser.objects.select_for_update().get(pk=uid)
        wu.rep += delta
        wu.save(update_fields=["rep"])

    locked_market.resolved = True
    locked_market.save(update_fields=["resolved", "refunded_trivial"])
    market.resolved = True
    market.refunded_trivial = locked_market.refunded_trivial
    return deltas
