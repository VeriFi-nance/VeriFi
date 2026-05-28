"""Model I — creator-as-trader CPMM with virtual seed + loser-pool cut.

Difference vs Model G:
  - Pool seeded with virtual liquidity V=10 (protocol-minted, no real backing).
  - Creator joins via normal CPMM buy() like any trader → gets fair share price.
  - Creator earns CREATOR_CUT_PCT (default 10%) of losers' pool on win
    (transfer, not mint).

Same as Model G:
  - 2-rep listing fee burned at claim creation (anti-spam).
  - 5% burn fee on every trader buy.
  - Refund-if-trivial: losing side < 3 voters OR total < 5 voters.
  - Locked reward for non-creator traders: shares × 1 rep.
"""
from __future__ import annotations
from simulator import CPMM, Stake
from simulator_g import (CREATOR_LISTING_FEE, CREATOR_DEFAULT_STAKE,
                         CREATOR_MIN_STAKE, CREATOR_MAX_STAKE,
                         MIN_LOSER_VOTERS, MIN_TOTAL_VOTERS, BURN_FEE)


VIRTUAL_SEED = 10.0
CREATOR_CUT_PCT = 0.10


class ModelI(CPMM):
    """Creator-as-trader CPMM with virtual seed + creator loser-pool cut."""
    name = "model_i"

    def __init__(self, claim_id: int = 0,
                 virtual_seed: float = VIRTUAL_SEED,
                 creator_uid: int | None = None,
                 creator_side: str = 'YES',
                 creator_stake: float = CREATOR_DEFAULT_STAKE,
                 listing_fee: float = CREATOR_LISTING_FEE,
                 creator_cut_pct: float = CREATOR_CUT_PCT):
        super().__init__(claim_id)
        self.y_reserve = float(virtual_seed)
        self.n_reserve = float(virtual_seed)
        self.init_L = float(virtual_seed)

        self.creator_uid = creator_uid
        self.listing_fee = listing_fee if creator_uid is not None else 0.0
        self.creator_cut_pct = creator_cut_pct

        if creator_uid is not None:
            X = max(CREATOR_MIN_STAKE, min(CREATOR_MAX_STAKE, creator_stake))
            # Creator buys via normal CPMM buy() — no special pricing.
            self.buy(creator_uid, creator_side, X)

    def buy(self, user_id, side, rep_amount=10.0):
        """5% burn on every buy (creator and traders alike)."""
        net = rep_amount * (1.0 - BURN_FEE)
        return super().buy(user_id, side, net)

    def resolve(self, winning_side: str) -> dict[int, float]:
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}

        if (len(loser_voters) < MIN_LOSER_VOTERS
                or len(total_voters) < MIN_TOTAL_VOTERS):
            # Trivial refund — full stake back for everyone, listing fee already burned.
            return {s.user_id: 0.0 for s in self.stakes}

        out = super().resolve(winning_side)

        # Creator cut: % of losers' pool if creator's side won.
        if (self.creator_cut_pct > 0 and self.creator_uid is not None
                and any(s.user_id == self.creator_uid and s.side == winning_side
                        for s in self.stakes)):
            losers_pool = sum(s.rep_paid for s in self.stakes
                              if s.side == losing_side)
            cut = self.creator_cut_pct * losers_pool
            out[self.creator_uid] = out.get(self.creator_uid, 0.0) + cut
        return out
