"""Test variants that give creator non-zero upside in Model G.

Variant A — CREATOR_CUT: creator earns `cut_pct` of losers' pool (transfer,
            not mint). Trader payouts unchanged at `shares × 1 rep`.
Variant B — REFUND_FEE: creator's 2-rep listing fee refunded if non-trivial
            AND total stakers >= REFUND_MIN (transfer of already-burned).
Variant C — A+B combined.

Metric goals:
- Creator mean net/claim > 0 at honest skill (0.65)
- Locked-reward invariant preserved for non-creator traders
- Inflation drift not materially worse than G baseline
"""
from __future__ import annotations
import random
import numpy as np
from simulator_g import (ModelG, CREATOR_LISTING_FEE, CREATOR_DEFAULT_STAKE,
                         MIN_LOSER_VOTERS, MIN_TOTAL_VOTERS, BURN_FEE,
                         Agent, run_inflation)
from simulator import Stake


class ModelG_CreatorCut(ModelG):
    """Variant A: creator takes `cut_pct` of losers' pool on win."""
    name = "model_g_creator_cut"

    def __init__(self, *args, cut_pct: float = 0.10, refund_fee_threshold: int = 0,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.cut_pct = cut_pct
        self.refund_fee_threshold = refund_fee_threshold  # 0 = disabled

    def resolve(self, winning_side: str) -> dict[int, float]:
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}
        n_total = len(total_voters)

        if (len(loser_voters) < MIN_LOSER_VOTERS
                or n_total < MIN_TOTAL_VOTERS):
            return {s.user_id: 0.0 for s in self.stakes}

        # Base CPMM payout (1 rep × shares for winners, -rep_paid for losers)
        out: dict[int, float] = {}
        losers_pool = 0.0
        for s in self.stakes:
            if s.side == winning_side:
                out[s.user_id] = out.get(s.user_id, 0.0) + (s.shares - s.rep_paid)
            else:
                out[s.user_id] = out.get(s.user_id, 0.0) - s.rep_paid
                losers_pool += s.rep_paid

        # Creator cut (only if their side won)
        if (self.creator_uid is not None
                and any(s.user_id == self.creator_uid and s.side == winning_side
                        for s in self.stakes)):
            cut = self.cut_pct * losers_pool
            out[self.creator_uid] = out.get(self.creator_uid, 0.0) + cut

        # Refund listing fee if attendance threshold met
        if self.refund_fee_threshold > 0 and n_total >= self.refund_fee_threshold:
            out[self.creator_uid] = out.get(self.creator_uid, 0.0) + self.listing_fee
            # Mark fee as refunded so inflation loop knows
            self._fee_refunded = True
        else:
            self._fee_refunded = False
        return out


def scenario_creator(model_factory, n_trials: int = 1000, seed: int = 11,
                     skill: float = 0.65, n_traders: int = 30) -> dict:
    """Replicates scenario_creator_earnings shape but uses given model_factory."""
    rng = random.Random(seed)
    creator_nets = []
    losing = 0
    minting_net = []  # rep created (mint) or destroyed per claim across all players

    for trial in range(n_trials):
        truth = rng.choice(['YES', 'NO'])
        guess = truth if rng.random() < skill else (
            'NO' if truth == 'YES' else 'YES')

        m = model_factory(trial, 0, guess)

        # Track rep flows: creator stake + listing fee already accounted
        creator_paid_initial = CREATOR_DEFAULT_STAKE + (m.listing_fee)

        # 30 traders, skill 0.5 (random)
        trader_stake_in = 0.0
        for uid in range(1, n_traders + 1):
            t_skill = rng.uniform(0.4, 0.6)
            side = truth if rng.random() < t_skill else (
                'NO' if truth == 'YES' else 'YES')
            m.buy(uid, side, 10.0)
            trader_stake_in += 10.0 * (1.0 - BURN_FEE)  # net after burn

        burn_total = (n_traders * 10.0 * BURN_FEE) + m.listing_fee
        # If listing fee refunded, subtract from burn
        profits = m.resolve(truth)
        fee_refunded = getattr(m, '_fee_refunded', False)
        if fee_refunded:
            burn_total -= m.listing_fee

        creator_net = profits.get(0, 0.0) - m.listing_fee
        if fee_refunded:
            creator_net += m.listing_fee  # already counted in profits via refund path

        # Actually let's recompute cleanly:
        # Creator's total wallet delta = profits[0] - listing_fee_paid + refund(if any)
        # Since we add refund inside profits[0] above, just: creator_net = profits[0] - listing_fee
        # If refunded, profits[0] already includes +listing_fee, so net = 0 contribution from fee
        creator_net = profits.get(0, 0.0) - m.listing_fee

        creator_nets.append(creator_net)
        if creator_net < 0:
            losing += 1

        # Sum of all profits = net mint (since profits already minus rep_paid)
        # But profits is net change from pool perspective. To get mint:
        # mint = sum(profits.values()) - 0  (profits is already net of stakes)
        # Wait — profits is per-user delta. Sum across users = mint - burn.
        mint = sum(profits.values()) - (0 if not fee_refunded else m.listing_fee)
        minting_net.append(mint)

    arr = np.array(creator_nets)
    return {
        'mean':   float(arr.mean()),
        'median': float(np.median(arr)),
        'p25':    float(np.percentile(arr, 25)),
        'p75':    float(np.percentile(arr, 75)),
        'pct_losing': losing / n_trials * 100,
        'mean_mint_per_claim': float(np.mean(minting_net)),
    }


def main() -> None:
    print("=" * 78)
    print("CREATOR-PROFIT VARIANTS — 1000 trials, skill 0.65, 30 traders")
    print("=" * 78)

    variants = {
        'G baseline (no cut, no refund)':
            lambda cid, uid, side: ModelG(claim_id=cid, creator_uid=uid,
                                          creator_side=side),
        'A1: cut=5%, no fee refund':
            lambda cid, uid, side: ModelG_CreatorCut(claim_id=cid, creator_uid=uid,
                                                    creator_side=side,
                                                    cut_pct=0.05,
                                                    refund_fee_threshold=0),
        'A2: cut=10%, no fee refund':
            lambda cid, uid, side: ModelG_CreatorCut(claim_id=cid, creator_uid=uid,
                                                    creator_side=side,
                                                    cut_pct=0.10,
                                                    refund_fee_threshold=0),
        'A3: cut=15%, no fee refund':
            lambda cid, uid, side: ModelG_CreatorCut(claim_id=cid, creator_uid=uid,
                                                    creator_side=side,
                                                    cut_pct=0.15,
                                                    refund_fee_threshold=0),
        'B: cut=0%, fee refund @ ≥10':
            lambda cid, uid, side: ModelG_CreatorCut(claim_id=cid, creator_uid=uid,
                                                    creator_side=side,
                                                    cut_pct=0.0,
                                                    refund_fee_threshold=10),
        'C: cut=10% + fee refund @ ≥10':
            lambda cid, uid, side: ModelG_CreatorCut(claim_id=cid, creator_uid=uid,
                                                    creator_side=side,
                                                    cut_pct=0.10,
                                                    refund_fee_threshold=10),
    }

    print(f"\n{'Variant':<40} {'mean':>8} {'median':>8} {'p25':>8} {'p75':>8} "
          f"{'%lose':>7} {'mint/clm':>9}")
    print("-" * 95)
    for name, factory in variants.items():
        r = scenario_creator(factory, n_trials=1000)
        print(f"{name:<40} {r['mean']:>+8.2f} {r['median']:>+8.2f} "
              f"{r['p25']:>+8.2f} {r['p75']:>+8.2f} "
              f"{r['pct_losing']:>6.1f}% {r['mean_mint_per_claim']:>+9.3f}")

    print()
    print("Notes:")
    print(" - mean<0 = creators lose on average → claim supply will dry")
    print(" - mint/clm > 0 = inflationary (rep created per claim)")
    print(" - locked reward (shares × 1 rep) untouched for traders in ALL variants")


if __name__ == '__main__':
    main()
