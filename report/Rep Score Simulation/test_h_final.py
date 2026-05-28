"""Final design candidates — H with listing fee variants + optional small cut."""
from __future__ import annotations
import random
import numpy as np
from simulator import CPMM, Stake
from simulator_g import (CREATOR_DEFAULT_STAKE, BURN_FEE,
                         MIN_LOSER_VOTERS, MIN_TOTAL_VOTERS, run_inflation)


class ModelI(CPMM):
    """H + optional loser-pool cut for creator."""
    name = "model_i"

    def __init__(self, claim_id: int = 0, virtual_seed: float = 25.0,
                 creator_uid: int | None = None,
                 creator_side: str = 'YES',
                 creator_stake: float = CREATOR_DEFAULT_STAKE,
                 listing_fee: float = 0.0,
                 creator_cut_pct: float = 0.0):
        super().__init__(claim_id)
        self.y_reserve = float(virtual_seed)
        self.n_reserve = float(virtual_seed)
        self.init_L    = float(virtual_seed)
        self.creator_uid = creator_uid
        self.listing_fee = listing_fee if creator_uid is not None else 0.0
        self.creator_cut_pct = creator_cut_pct
        if creator_uid is not None:
            self.buy(creator_uid, creator_side, creator_stake)

    def buy(self, user_id, side, rep_amount=10.0):
        net = rep_amount * (1.0 - BURN_FEE)
        return super().buy(user_id, side, net)

    def resolve(self, winning_side):
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}
        if (len(loser_voters) < MIN_LOSER_VOTERS
                or len(total_voters) < MIN_TOTAL_VOTERS):
            return {s.user_id: 0.0 for s in self.stakes}

        out = super().resolve(winning_side)

        if (self.creator_cut_pct > 0 and self.creator_uid is not None
                and any(s.user_id == self.creator_uid and s.side == winning_side
                        for s in self.stakes)):
            losers_pool = sum(s.rep_paid for s in self.stakes
                              if s.side == losing_side)
            cut = self.creator_cut_pct * losers_pool
            out[self.creator_uid] = out.get(self.creator_uid, 0.0) + cut
        return out


def scenario_creator(factory, n_trials=500, skill=0.65, n_traders=30, seed=11):
    rng = random.Random(seed)
    nets = []
    for trial in range(n_trials):
        truth = rng.choice(['YES', 'NO'])
        guess = truth if rng.random() < skill else (
            'NO' if truth == 'YES' else 'YES')
        m = factory(trial, 0, guess)
        for uid in range(1, n_traders + 1):
            t_skill = rng.uniform(0.4, 0.6)
            side = truth if rng.random() < t_skill else (
                'NO' if truth == 'YES' else 'YES')
            m.buy(uid, side, 10.0)
        profits = m.resolve(truth)
        nets.append(profits.get(0, 0.0) - m.listing_fee)
    arr = np.array(nets)
    return {
        'mean': float(arr.mean()), 'median': float(np.median(arr)),
        'p25': float(np.percentile(arr, 25)), 'p75': float(np.percentile(arr, 75)),
        'pct_losing': float((arr < 0).mean() * 100),
    }


def make_factory(V, fee, cut):
    def f(claim_id, uid):
        side = random.choice(['YES', 'NO'])
        return ModelI(claim_id=claim_id, virtual_seed=V, creator_uid=uid,
                      creator_side=side, creator_stake=CREATOR_DEFAULT_STAKE,
                      listing_fee=fee, creator_cut_pct=cut)
    return f


def make_scenario_factory(V, fee, cut):
    def f(claim_id, uid, side):
        return ModelI(claim_id=claim_id, virtual_seed=V, creator_uid=uid,
                      creator_side=side, creator_stake=CREATOR_DEFAULT_STAKE,
                      listing_fee=fee, creator_cut_pct=cut)
    return f


def main() -> None:
    print("=" * 100)
    print("MODEL I — H + tunable fee + tunable cut. 25% trivial mix, 180 days.")
    print("=" * 100)

    configs = [
        # (label, V, fee, cut)
        ("H V=25 fee=2 cut=0",        25,  2.0, 0.00),
        ("H V=25 fee=0 cut=0",        25,  0.0, 0.00),
        ("H V=25 fee=0 cut=5%",       25,  0.0, 0.05),
        ("H V=25 fee=0 cut=10%",      25,  0.0, 0.10),
        ("H V=25 fee=2 cut=5%",       25,  2.0, 0.05),
        ("H V=25 fee=2 cut=10%",      25,  2.0, 0.10),
        ("H V=50 fee=2 cut=5%",       50,  2.0, 0.05),
        ("H V=10 fee=0 cut=10%",      10,  0.0, 0.10),
        ("H V=10 fee=2 cut=10%",      10,  2.0, 0.10),
    ]

    print(f"\n{'config':<25} {'cr_mean':>8} {'cr_med':>7} {'%lose':>6} "
          f"{'180d_med':>9} {'180d_mean':>10}")
    print("-" * 75)
    for label, V, fee, cut in configs:
        cr = scenario_creator(make_scenario_factory(V, fee, cut))
        random.seed(123)
        infl = run_inflation(days=180, n_agents=100, claims_per_day=5,
                             trivial_fraction=0.25,
                             model_factory=make_factory(V, fee, cut), seed=42)
        print(f"{label:<25} {cr['mean']:>+8.2f} {cr['median']:>+7.2f} "
              f"{cr['pct_losing']:>5.1f}% {infl['median_drift_pct']:>+8.1f}% "
              f"{infl['mean_drift_pct']:>+9.1f}%")

    print()
    print("Reference: G baseline cr_mean=-5.49, 180d_median_drift=+102%")


if __name__ == '__main__':
    main()
