"""Test concrete fixes to reduce Model G's inflation drift.

Worst case before any extra knobs: G at homogeneous high-skill = +756%
over 180 days. Test four candidate tweaks and combinations:

  Fix A — Lower CPMM virtual seed: INIT_L = 30 (vs 100). Less subsidy
          per claim, more price impact per trade.
  Fix B — Vote-share refund: refund if losing side < 15% of total
          voters (instead of fixed minimum of 3).
  Fix C — Burn fee: 1% of every stake routed to /dev/null. Constant
          deflation pressure.
  Fix D — Per-claim mint cap: if a claim would mint more than CAP rep,
          scale all winning shares down to fit the cap.

Run:  python3 simulator_inflation_fixes.py
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt

from simulator import CPMM, Stake
from simulator_g import ModelG

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# MODEL VARIANTS
# ---------------------------------------------------------------------------

class GTunable(ModelG):
    """ModelG with knobs exposed for sweep testing."""

    def __init__(self, claim_id: int = 0,
                 init_L: float = 100.0,
                 vote_share_refund: float | None = None,
                 min_loser_voters: int = 3,
                 burn_bps: int = 0,
                 mint_cap: float | None = None):
        super().__init__(claim_id)
        # Override CPMM's INIT_L by resetting reserves
        self.y_reserve = init_L
        self.n_reserve = init_L
        self.init_L = init_L
        self.vote_share_refund = vote_share_refund
        self.min_loser_voters_local = min_loser_voters
        self.burn_bps = burn_bps
        self.mint_cap = mint_cap
        self.burned_total = 0.0

    def buy(self, user_id, side, rep_amount=10.0):
        # Optionally burn a fraction before the rep hits the AMM curve
        burn = rep_amount * self.burn_bps / 10000.0
        self.burned_total += burn
        return super().buy(user_id, side, rep_amount - burn)

    def resolve(self, winning_side):
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes
                        if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}

        # Refund rule check
        refund = False
        if len(loser_voters) < self.min_loser_voters_local:
            refund = True
        if self.vote_share_refund is not None and total_voters:
            share = len(loser_voters) / len(total_voters)
            if share < self.vote_share_refund:
                refund = True

        if refund:
            # Stakes were already reduced by burn at buy time, so refund
            # the post-burn stake (which equals what they paid into the
            # AMM).  Burn rep is gone permanently.
            return {s.user_id: -s.rep_paid * 0.0 for s in self.stakes}
            # ^ net change 0 for each user (stake refunded);
            #   burn is the only net loss to the system.

        # Otherwise run CPMM resolution
        out = {}
        for s in self.stakes:
            base = -s.rep_paid
            if s.side == winning_side:
                base += s.shares
            out[s.user_id] = out.get(s.user_id, 0.0) + base

        # Optional mint-cap: if net mint > cap, scale winning shares down
        if self.mint_cap is not None:
            mint = sum(out.values())
            if mint > self.mint_cap and mint > 0:
                scale = self.mint_cap / mint
                # rescale each winner's gain (loser changes unchanged)
                for s in self.stakes:
                    if s.side == winning_side:
                        # winner's contribution was (shares - rep_paid)
                        # rescale that to (shares - rep_paid) * scale + (1-scale)*0
                        winner_gain = s.shares - s.rep_paid
                        out[s.user_id] -= winner_gain * (1 - scale)
        return out


@dataclass
class Agent:
    uid: int
    rep: float = 200.0
    energy: float = 5.0
    skill: float = 0.5
    activity: float = 0.5


def run(days, n_agents, claims_per_day, trivial_fraction, model_factory,
        seed=0, skill_range=(0.4, 0.75)):
    rng = random.Random(seed)
    skills = [rng.uniform(*skill_range) for _ in range(n_agents)]
    activities = [rng.uniform(0.2, 1.0) for _ in range(n_agents)]
    agents = [Agent(uid=i, skill=skills[i], activity=activities[i])
              for i in range(n_agents)]
    DAILY_GRANT, ENERGY_CAP, STAKE_COST = 3, 4, 1
    supply = [sum(a.rep for a in agents)]

    for day in range(days):
        for a in agents:
            a.energy = min(a.energy + DAILY_GRANT, ENERGY_CAP)
        for c in range(claims_per_day):
            m = model_factory(day * 1000 + c)
            truth = rng.choice(['YES', 'NO'])
            trivial = rng.random() < trivial_fraction
            order = list(range(n_agents))
            rng.shuffle(order)
            for uid in order:
                a = agents[uid]
                if a.rep < 10 or a.energy < STAKE_COST:
                    continue
                if rng.random() > a.activity:
                    continue
                skill = 0.99 if trivial else a.skill
                side = truth if rng.random() < skill else (
                    'NO' if truth == 'YES' else 'YES')
                m.buy(uid, side, 10.0)
                a.rep -= 10.0
                a.energy -= STAKE_COST
            profits = m.resolve(truth)
            for uid, p in profits.items():
                agents[uid].rep += 10.0 + p
        supply.append(sum(a.rep for a in agents))

    initial, final = supply[0], supply[-1]
    return {
        'drift_pct': (final - initial) / initial * 100,
        'final_supply': final,
    }


# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------

def main():
    print("Running fixes sweep (this takes ~1 min) ...")
    # Two stress scenarios per fix: 25% trivial mix (typical platform)
    # and 100% trivial mix (worst case).  Also one homogeneous high-skill
    # case to stress non-trivial-but-skewed claims.
    scenarios = [
        ('typical (25% trivial, skill 0.4-0.75)',
         {'trivial_fraction': 0.25, 'skill_range': (0.4, 0.75)}),
        ('worst-case trivial (100% trivial)',
         {'trivial_fraction': 1.0, 'skill_range': (0.4, 0.75)}),
        ('homogeneous high skill (no synthetic trivial)',
         {'trivial_fraction': 0.0, 'skill_range': (0.85, 0.95)}),
    ]

    fixes = [
        ('F (baseline)', lambda cid: CPMM(claim_id=cid)),
        ('G (current)', lambda cid: ModelG(claim_id=cid)),
        ('G + A: INIT_L=30', lambda cid: GTunable(cid, init_L=30)),
        ('G + B: vote-share refund 15%',
         lambda cid: GTunable(cid, vote_share_refund=0.15)),
        ('G + C: burn 1%',
         lambda cid: GTunable(cid, burn_bps=100)),
        ('G + D: mint cap 20/claim',
         lambda cid: GTunable(cid, mint_cap=20.0)),
        ('G + A+B+C (all)',
         lambda cid: GTunable(cid, init_L=30, vote_share_refund=0.15,
                              burn_bps=100)),
    ]

    results = {}
    for sname, sargs in scenarios:
        for fname, factory in fixes:
            r = run(days=180, n_agents=200, claims_per_day=10,
                    model_factory=factory, seed=0, **sargs)
            results[(sname, fname)] = r['drift_pct']
            print(f"  {sname:55s} | {fname:35s} | drift {r['drift_pct']:+7.0f}%")

    # Report
    L = []
    L.append("# Inflation reduction fixes — sweep\n")
    L.append("Each fix tested against three scenarios. 180 days, 200 "
             "users, 10 claims/day.\n")
    L.append("## Fixes tested\n")
    L.append("- **A** — `INIT_L=30`: lower CPMM virtual seed.")
    L.append("- **B** — `vote_share_refund=0.15`: refund if losing side "
             "< 15% of total voters (in addition to the absolute count rule).")
    L.append("- **C** — `burn_bps=100`: 1% of every stake burned.")
    L.append("- **D** — `mint_cap=20`: if a claim would mint > 20 rep, "
             "scale winning payouts down to fit the cap.\n")

    for sname, _ in scenarios:
        L.append(f"## Scenario: {sname}\n")
        L.append("| Fix | 180-day drift |")
        L.append("|---|---|")
        for fname, _ in fixes:
            L.append(f"| {fname} | {results[(sname, fname)]:+.0f}% |")
        L.append("")

    L.append("## Recommendation\n")
    typical = {fname: results[(scenarios[0][0], fname)] for fname, _ in fixes}
    worst = {fname: results[(scenarios[1][0], fname)] for fname, _ in fixes}
    homog = {fname: results[(scenarios[2][0], fname)] for fname, _ in fixes}
    best_combined = min(fixes, key=lambda f: max(
        typical[f[0]], worst[f[0]], homog[f[0]]))
    L.append(f"**Best across all 3 scenarios:** `{best_combined[0]}` — "
             "minimises the worst-case drift across knobs tested.\n")

    out = os.path.join(OUT_DIR, "inflation_fixes.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
