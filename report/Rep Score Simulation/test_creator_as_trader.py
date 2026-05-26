"""Variant H — creator is just a regular trader.

Pool seeded with small virtual liquidity V (no real rep backing).
Creator joins via normal CPMM buy() like any trader. No special shares,
no special pricing. Pays listing fee (burned).

Trade-off vs G:
+ Creator gets fair CPMM share price → can profit on wins
- Virtual seed reintroduces some inflation (winners extract from
  unbacked reserves up to ~2V rep per claim)

Sweep V to find smallest seed that keeps creator EV > 0 AND inflation
acceptable.
"""
from __future__ import annotations
import random
import numpy as np
from simulator import CPMM, Stake
from simulator_g import (CREATOR_LISTING_FEE, CREATOR_DEFAULT_STAKE,
                         MIN_LOSER_VOTERS, MIN_TOTAL_VOTERS, BURN_FEE)


class ModelH(CPMM):
    """Creator-as-trader. Virtual seed V. No special creator stake."""
    name = "model_h"

    def __init__(self, claim_id: int = 0, virtual_seed: float = 5.0,
                 creator_uid: int | None = None,
                 creator_side: str = 'YES',
                 creator_stake: float = CREATOR_DEFAULT_STAKE,
                 listing_fee: float = CREATOR_LISTING_FEE):
        super().__init__(claim_id)
        self.y_reserve = float(virtual_seed)
        self.n_reserve = float(virtual_seed)
        self.init_L    = float(virtual_seed)
        self.creator_uid = creator_uid
        self.listing_fee = listing_fee if creator_uid is not None else 0.0

        if creator_uid is not None:
            # Creator does normal CPMM buy
            self.buy(creator_uid, creator_side, creator_stake)

    def buy(self, user_id, side, rep_amount=10.0):
        # 5% burn on trader buys (same as G)
        net = rep_amount * (1.0 - BURN_FEE)
        return super().buy(user_id, side, net)

    def resolve(self, winning_side):
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}
        if (len(loser_voters) < MIN_LOSER_VOTERS
                or len(total_voters) < MIN_TOTAL_VOTERS):
            return {s.user_id: 0.0 for s in self.stakes}
        return super().resolve(winning_side)


def run_scenario(virtual_seed: float, n_trials: int = 1000, seed: int = 11,
                 skill: float = 0.65, n_traders: int = 30) -> dict:
    rng = random.Random(seed)
    creator_nets = []
    minting_net = []

    for trial in range(n_trials):
        truth = rng.choice(['YES', 'NO'])
        guess = truth if rng.random() < skill else (
            'NO' if truth == 'YES' else 'YES')

        m = ModelH(claim_id=trial, virtual_seed=virtual_seed,
                   creator_uid=0, creator_side=guess,
                   creator_stake=CREATOR_DEFAULT_STAKE)

        for uid in range(1, n_traders + 1):
            t_skill = rng.uniform(0.4, 0.6)
            side = truth if rng.random() < t_skill else (
                'NO' if truth == 'YES' else 'YES')
            m.buy(uid, side, 10.0)

        profits = m.resolve(truth)
        # Creator net = profits[0] - listing_fee
        creator_net = profits.get(0, 0.0) - m.listing_fee
        creator_nets.append(creator_net)

        # Mint estimate: sum of net profits + total burned
        # (profits is delta after rep_paid; mint = sum(profits) is rep created)
        mint = sum(profits.values())
        minting_net.append(mint)

    arr = np.array(creator_nets)
    return {
        'mean':   float(arr.mean()),
        'median': float(np.median(arr)),
        'p25':    float(np.percentile(arr, 25)),
        'p75':    float(np.percentile(arr, 75)),
        'pct_losing': float((arr < 0).mean() * 100),
        'mean_mint_per_claim': float(np.mean(minting_net)),
    }


def main() -> None:
    print("=" * 90)
    print("MODEL H — creator as regular trader, sweep virtual seed V")
    print("Skill 0.65, 30 traders, 1000 trials")
    print("=" * 90)
    print(f"\n{'V':>5}  {'mean':>8} {'median':>8} {'p25':>8} {'p75':>8} "
          f"{'%lose':>7} {'mint/clm':>9}")
    print("-" * 70)
    for V in [1, 2, 5, 10, 20, 50, 100]:
        r = run_scenario(virtual_seed=float(V))
        print(f"{V:>5}  {r['mean']:>+8.2f} {r['median']:>+8.2f} "
              f"{r['p25']:>+8.2f} {r['p75']:>+8.2f} "
              f"{r['pct_losing']:>6.1f}% {r['mean_mint_per_claim']:>+9.3f}")

    print()
    print("Reference (from prior tests):")
    print("  G baseline           mean=-5.49  mint/claim=-9.82")
    print("  G + A2 (10% cut)     mean=+4.26  mint/claim=-0.08")
    print()
    print("Target: mean > 0 AND mint/claim < +0.1 (matches G+A2)")


if __name__ == '__main__':
    main()
