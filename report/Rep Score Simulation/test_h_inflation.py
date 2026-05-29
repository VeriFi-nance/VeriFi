"""Model H sweep with full 180-day inflation sim.

User accepts mild inflation. Find V where:
- Creator mean EV > 0 (or close)
- Median rep drift over 180d acceptable (target: <+100%, F was +425%)
"""
from __future__ import annotations
import random
import numpy as np
from simulator_g import (CREATOR_LISTING_FEE, CREATOR_DEFAULT_STAKE, BURN_FEE,
                         MIN_LOSER_VOTERS, MIN_TOTAL_VOTERS, run_inflation)
from test_creator_as_trader import ModelH, run_scenario


def make_factory(V: float):
    def factory(claim_id: int, creator_uid: int) -> ModelH:
        # Inflation sim picks creator side randomly; that's fine
        # Real creators would side w/ their guess but here we sim avg case
        side = random.choice(['YES', 'NO'])
        return ModelH(claim_id=claim_id, virtual_seed=V,
                      creator_uid=creator_uid, creator_side=side,
                      creator_stake=CREATOR_DEFAULT_STAKE)
    return factory


def main() -> None:
    print("=" * 100)
    print("MODEL H — 180-day inflation sim, V sweep")
    print("100 agents, 5 claims/day, 25% trivial mix (matches G report)")
    print("=" * 100)

    print(f"\n{'V':>5} {'creator_mean':>13} {'creator_med':>12} "
          f"{'180d_median_drift':>18} {'180d_mean_drift':>16} "
          f"{'top_q_median':>13} {'bottom_q_median':>16}")
    print("-" * 110)

    Vs = [10, 25, 50, 75, 100, 150, 200]
    for V in Vs:
        # 1) Creator-EV from earlier scenario test
        cr = run_scenario(virtual_seed=float(V), n_trials=500)

        # 2) Full inflation sim
        random.seed(123)  # for the side-pick in factory
        infl = run_inflation(days=180, n_agents=100, claims_per_day=5,
                             trivial_fraction=0.25,
                             model_factory=make_factory(float(V)),
                             seed=42)
        print(f"{V:>5} {cr['mean']:>+13.2f} {cr['median']:>+12.2f} "
              f"{infl['median_drift_pct']:>+17.1f}% {infl['mean_drift_pct']:>+15.1f}% "
              f"{infl['top_median']:>+13.1f} {infl['bottom_median']:>+16.1f}")

    print()
    print("Reference (from G report):")
    print("  G baseline           180d_median_drift = +102%  (25% trivial mix)")
    print("  F                    180d_median_drift = +425%  (25% trivial mix)")


if __name__ == '__main__':
    main()
