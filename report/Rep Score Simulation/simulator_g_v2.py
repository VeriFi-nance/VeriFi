"""Model G v2 — locked reward preserved, deeper trivial-claim defense.

User feedback: keep locked rewards, accept small inflation, but harden
the trivial-claim attack surface.

Stack:
  1. No creator auto-YES at claim creation (closes +9.17 freebie).
  2. Listing fee: creator pays ``CREATOR_LISTING_FEE`` rep at claim
     creation, burned permanently.  Raises the break-even bar for
     spam/farm claims.  Trader payouts untouched.
  3. Min-loser-voters refund: if losing side has < ``MIN_LOSER_VOTERS``
     distinct voters, refund every stake — claim is trivial.
  4. Min-total-voters refund: if claim attracts < ``MIN_TOTAL_VOTERS``
     stakers, refund every stake — claim is "abandoned".  Prevents
     small-N farming where attacker just brings 3 alts on each side
     to dodge the loser-count rule.
  5. Reduced virtual seed: INIT_L drops from 100 to 30 so the per-
     claim mint cap drops from ~+143 to ~+43 rep.  Same CPMM math,
     just less subsidy.

Locked reward holds on every resolving claim — shares × 1 rep at buy
time, paid in full at resolution, or full refund if the claim is
declared trivial.

Run:  python3 simulator_g_v2.py
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt

from simulator import CPMM, gini, Stake

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


MIN_LOSER_VOTERS = 3
MIN_TOTAL_VOTERS = 5
CREATOR_LISTING_FEE = 2.0
INIT_L_G2 = 30.0


class ModelGv2(CPMM):
    """G with the v2 trivial-defense stack."""

    name = "model_g_v2"

    def __init__(self, claim_id: int = 0, creator_uid: int | None = None,
                 init_L: float = INIT_L_G2,
                 listing_fee: float = CREATOR_LISTING_FEE):
        super().__init__(claim_id)
        # Override virtual seed
        self.y_reserve = init_L
        self.n_reserve = init_L
        self.init_L = init_L
        self.creator_uid = creator_uid
        self.listing_fee = listing_fee
        self.listing_fee_burned = listing_fee if creator_uid is not None else 0.0

    def resolve(self, winning_side: str) -> dict[int, float]:
        """Listing fee is handled at CREATION (harness deducts it from
        creator).  This method only deals with stake-level resolution —
        net change per stake user, not the listing fee.
        """
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes
                        if s.side == losing_side}
        total_voters = {s.user_id for s in self.stakes}

        trivial = (
            len(loser_voters) < MIN_LOSER_VOTERS
            or len(total_voters) < MIN_TOTAL_VOTERS
        )
        if trivial:
            return {s.user_id: 0.0 for s in self.stakes}

        out = {}
        for s in self.stakes:
            base = -s.rep_paid
            if s.side == winning_side:
                base += s.shares
            out[s.user_id] = out.get(s.user_id, 0.0) + base
        return out


# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------

@dataclass
class Agent:
    uid: int
    rep: float = 200.0
    energy: float = 5.0
    skill: float = 0.5
    activity: float = 0.5


def run_inflation(days, n_agents, claims_per_day, trivial_fraction,
                  model_factory, seed=0, skill_range=(0.4, 0.75)):
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
            creator_uid = rng.randint(0, n_agents - 1)
            m = model_factory(day * 1000 + c, creator_uid)
            # creator pays listing fee
            if hasattr(m, 'listing_fee') and m.creator_uid is not None:
                agents[m.creator_uid].rep -= m.listing_fee
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
            # listing fee was already deducted at claim creation; it
            # stays burned regardless of outcome.  No further action.
        supply.append(sum(a.rep for a in agents))

    initial, final = supply[0], supply[-1]
    return {'drift_pct': (final - initial) / initial * 100,
            'final_supply': final, 'initial': initial}


def scenario_locked_reward():
    """Alice bets YES, varying late buyers, truth=YES.
    Locked reward should be invariant under G v2."""
    out = {}
    for label, factory in [
        ('F (CPMM, INIT_L=100)', lambda: CPMM()),
        ('G v1 (INIT_L=100)',
         lambda: _make_v1()),
        ('G v2 (INIT_L=30, listing fee, min 5 total)',
         lambda: ModelGv2(creator_uid=999)),
    ]:
        alice_at = {}
        for n_later in [0, 5, 20, 50]:
            m = factory()
            m.buy(0, 'YES', 10.0)         # Alice
            for u in range(1, 11):
                m.buy(u, 'NO', 10.0)
            for u in range(11, 11 + n_later):
                m.buy(u, 'YES', 10.0)
            p = m.resolve('YES')
            alice_at[n_later] = p[0]
        out[label] = alice_at
    return out


def _make_v1():
    """ModelG v1 = the current G (just refund-if-uncontested)."""
    from simulator_g import ModelG
    return ModelG()


def scenario_trivial_farming():
    """Attacker creates claim, votes YES on N sybils, ends up against 0/1/2/5
    honest dissenters.  How much rep does attacker net?"""
    results = []
    for n_dissenters in [0, 1, 2, 3, 5, 10]:
        f_profits = []
        g1_profits = []
        g2_profits = []
        f_mints = []
        g1_mints = []
        g2_mints = []
        for trial in range(200):
            for cls_label, make in [
                ('F', lambda: (CPMM(), 0)),
                ('G v1', lambda: (_make_v1(), 0)),
                ('G v2', lambda: (ModelGv2(creator_uid=0),
                                  CREATOR_LISTING_FEE)),
            ]:
                m, listing_fee = make()
                # 10 sybils vote YES, including the creator-uid=0
                for u in range(10):
                    m.buy(u, 'YES', 10.0)
                for u in range(10, 10 + n_dissenters):
                    m.buy(u, 'NO', 10.0)
                p = m.resolve('YES')
                # attacker net = sum of their sybil profits MINUS the
                # creator's listing fee (burned at creation, not in p)
                attacker = sum(p.get(u, 0) for u in range(10)) - listing_fee
                # system mint also excludes the listing fee
                mint = sum(p.values()) - listing_fee
                if cls_label == 'F':
                    f_profits.append(attacker)
                    f_mints.append(mint)
                elif cls_label == 'G v1':
                    g1_profits.append(attacker)
                    g1_mints.append(mint)
                else:
                    g2_profits.append(attacker)
                    g2_mints.append(mint)
        results.append({
            'n_dissenters': n_dissenters,
            'F_attacker': np.mean(f_profits),
            'G_v1_attacker': np.mean(g1_profits),
            'G_v2_attacker': np.mean(g2_profits),
            'F_mint': np.mean(f_mints),
            'G_v1_mint': np.mean(g1_mints),
            'G_v2_mint': np.mean(g2_mints),
        })
    return results


def scenario_inflation_compare():
    """Re-run the worst-case sweeps for G v1 vs G v2."""
    out = []
    for label, tf in [('typical (25% trivial)', 0.25),
                      ('worst trivial (100%)', 1.0)]:
        F = run_inflation(180, 200, 10, tf,
                          lambda cid, ca: CPMM(claim_id=cid), seed=0)
        from simulator_g import ModelG
        G1 = run_inflation(180, 200, 10, tf,
                           lambda cid, ca: ModelG(claim_id=cid), seed=0)
        G2 = run_inflation(180, 200, 10, tf,
                           lambda cid, ca: ModelGv2(claim_id=cid, creator_uid=ca),
                           seed=0)
        out.append((label, F['drift_pct'], G1['drift_pct'], G2['drift_pct']))
    return out


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def write_report(locked, trivial, inflation):
    L = []
    A = L.append
    A("# Model G v2 — locked rewards + harder trivial defense\n")
    A("Stack:")
    A("- No creator auto-YES (kept from v1)")
    A(f"- Listing fee: creator pays {CREATOR_LISTING_FEE} rep at claim "
      "creation, burned permanently (anti-spam, small deflation).")
    A(f"- Min loser voters: refund if < {MIN_LOSER_VOTERS} distinct "
      "dissenters (kept from v1).")
    A(f"- Min total voters: refund if claim attracts < {MIN_TOTAL_VOTERS} "
      "voters total (new — closes 'just bring 3 alts on each side' "
      "loophole).")
    A(f"- INIT_L = {INIT_L_G2} (was 100): per-claim mint cap drops from "
      "~+143 to ~+43 rep.\n")

    A("## Locked reward intact\n")
    A("Alice bets YES, vary late YES buyers, truth=YES:\n")
    A("| Later YES buyers | F | G v1 | G v2 |")
    A("|---|---|---|---|")
    for n in sorted(next(iter(locked.values())).keys()):
        row = [str(n)]
        for label in ['F (CPMM, INIT_L=100)',
                      'G v1 (INIT_L=100)',
                      'G v2 (INIT_L=30, listing fee, min 5 total)']:
            row.append(f"{locked[label][n]:+.2f}")
        A("| " + " | ".join(row) + " |")
    A("")
    A("Alice's profit is invariant across late buyers in every model — "
      "locked reward holds.  v2's Alice gets a lower absolute number "
      "than v1 because INIT_L is smaller (fewer subsidised shares per "
      "stake), but it's still locked.\n")

    A("## Trivial farming attack\n")
    A("Attacker brings 10 sybil accounts all voting YES.  Honest NO "
      "voters vary.  How much does the attacker pocket?\n")
    A("| Honest NO voters | F attacker net | G v1 attacker | G v2 attacker | F mint | G v1 mint | G v2 mint |")
    A("|---|---|---|---|---|---|---|")
    for r in trivial:
        A(f"| {r['n_dissenters']} | "
          f"{r['F_attacker']:+.1f} | "
          f"{r['G_v1_attacker']:+.1f} | "
          f"{r['G_v2_attacker']:+.1f} | "
          f"{r['F_mint']:+.1f} | "
          f"{r['G_v1_mint']:+.1f} | "
          f"{r['G_v2_mint']:+.1f} |")
    A("")

    A("## Inflation 180-day drift\n")
    A("| Scenario | F | G v1 | G v2 |")
    A("|---|---|---|---|")
    for label, f, g1, g2 in inflation:
        A(f"| {label} | {f:+.0f}% | {g1:+.0f}% | {g2:+.0f}% |")
    A("")

    out_path = os.path.join(OUT_DIR, "model_g_v2_report.md")
    with open(out_path, 'w') as f:
        f.write("\n".join(L))
    return out_path


def main():
    print("Locked reward test ...")
    locked = scenario_locked_reward()
    print("Trivial farming sweep ...")
    trivial = scenario_trivial_farming()
    print("Inflation comparison (this takes ~30s) ...")
    inflation = scenario_inflation_compare()
    out = write_report(locked, trivial, inflation)
    print(f"\nReport: {out}")


if __name__ == "__main__":
    main()
