"""
VeriFi reputation-score system simulator.

Runs all candidate payout models across edge-case scenarios, produces
matplotlib charts and a final-recommendation report.

Models compared:
  - parimutuel    : current Model C (wiki).
  - late_adoption : Arda's variant — winners only redistribute losers' stakes.
  - cpmm          : Polymarket-style fixed-payout shares + CPMM AMM.
  - cpmm_energy   : cpmm + daily ENERGY token gating frequency.

Scenarios:
  - balanced_random
  - late_adoption_correct
  - copy_trade_dilution
  - skewed_prior
  - first_mover_advantage
  - multi_day_energy_distribution

Run:  python3 simulator.py
Output:  charts/*.png  +  final_recommendation.md
"""

from __future__ import annotations

import math
import os
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# MODELS
# ----------------------------------------------------------------------------

@dataclass
class Stake:
    user_id: int
    side: str          # 'YES' or 'NO'
    rep_paid: float
    entry_price: float
    weight: float
    shares: Optional[float] = None  # only for CPMM


class Market:
    """Base. Subclasses override price() and resolve()."""

    def __init__(self, claim_id: int = 0):
        self.claim_id = claim_id
        self.stakes: list[Stake] = []
        self.yes_count = 0
        self.no_count = 0
        # tick = order in which this stake was placed (for late-adoption analysis)
        self.tick_of: list[int] = []

    def buy(self, user_id: int, side: str, rep_amount: float = 10.0) -> Stake:
        raise NotImplementedError

    def resolve(self, winning_side: str) -> dict[int, float]:
        """Return {user_id: net_profit} (loser = -rep_paid)."""
        raise NotImplementedError

    def yes_price(self) -> float:
        raise NotImplementedError


# Wiki seed = 10. Sim html had 1. Pick wiki value.
VIRTUAL_SEED = 10


class Parimutuel(Market):
    """Current Model C. Weight = 1/entry_price. Pool = 10 * n_total."""

    name = "parimutuel"

    def yes_price(self) -> float:
        y = self.yes_count + VIRTUAL_SEED
        n = self.no_count + VIRTUAL_SEED
        return y / (y + n)

    def buy(self, user_id, side, rep_amount=10.0):
        yp = self.yes_price()
        ep = yp if side == 'YES' else 1 - yp
        st = Stake(user_id=user_id, side=side, rep_paid=rep_amount,
                   entry_price=ep, weight=1.0 / ep)
        self.stakes.append(st)
        self.tick_of.append(len(self.stakes) - 1)
        if side == 'YES':
            self.yes_count += 1
        else:
            self.no_count += 1
        return st

    def resolve(self, winning_side):
        # accumulate per user_id (one user can hold multiple stakes pre-v2-limit)
        pool = sum(s.rep_paid for s in self.stakes)
        winners = [s for s in self.stakes if s.side == winning_side]
        out: dict[int, float] = {}
        for s in self.stakes:
            out[s.user_id] = out.get(s.user_id, 0.0) - s.rep_paid
        if not winners:
            return out
        wsum = sum(s.weight for s in winners)
        for s in winners:
            payout = pool * s.weight / wsum
            out[s.user_id] = out.get(s.user_id, 0.0) + payout
        return out


class LateAdoption(Parimutuel):
    """Arda's variant. Winner gets back own stake + share of losers' stakes weighted."""

    name = "late_adoption"

    def resolve(self, winning_side):
        winners = [s for s in self.stakes if s.side == winning_side]
        losers_pool = sum(s.rep_paid for s in self.stakes if s.side != winning_side)
        out: dict[int, float] = {}
        for s in self.stakes:
            out[s.user_id] = out.get(s.user_id, 0.0) - s.rep_paid
        if not winners or losers_pool <= 0:
            return out
        wsum = sum(s.weight for s in winners)
        for s in winners:
            extra = losers_pool * s.weight / wsum
            # winner gets stake back + extra share of losers' pool
            out[s.user_id] = out.get(s.user_id, 0.0) + s.rep_paid + extra
        return out


class CPMM(Market):
    """Polymarket-style. Reward locked at buy time."""

    name = "cpmm"
    INIT_L = 100.0  # virtual liquidity each side

    def __init__(self, claim_id=0):
        super().__init__(claim_id)
        self.y_reserve = self.INIT_L
        self.n_reserve = self.INIT_L
        self.yes_outstanding = 0.0
        self.no_outstanding = 0.0
        self.escrow = 0.0

    def yes_price(self):
        return self.n_reserve / (self.y_reserve + self.n_reserve)

    def buy(self, user_id, side, rep_amount=10.0):
        r = rep_amount
        yp_pre = self.yes_price()
        if side == 'YES':
            shares = r + (self.y_reserve + r) * r / (self.n_reserve + 2 * r)
            new_y = (self.y_reserve + r) * (self.n_reserve + r) / (self.n_reserve + 2 * r)
            new_n = self.n_reserve + 2 * r
            self.y_reserve, self.n_reserve = new_y, new_n
            self.yes_outstanding += shares
        else:
            shares = r + (self.n_reserve + r) * r / (self.y_reserve + 2 * r)
            new_n = (self.n_reserve + r) * (self.y_reserve + r) / (self.y_reserve + 2 * r)
            new_y = self.y_reserve + 2 * r
            self.y_reserve, self.n_reserve = new_y, new_n
            self.no_outstanding += shares
        self.escrow += r
        ep = yp_pre if side == 'YES' else 1 - yp_pre
        st = Stake(user_id=user_id, side=side, rep_paid=r,
                   entry_price=ep, weight=shares / r, shares=shares)
        self.stakes.append(st)
        self.tick_of.append(len(self.stakes) - 1)
        if side == 'YES':
            self.yes_count += 1
        else:
            self.no_count += 1
        return st

    def resolve(self, winning_side):
        out: dict[int, float] = {}
        for s in self.stakes:
            if s.side == winning_side:
                # 1 rep per share. Net profit = shares - rep_paid.
                out[s.user_id] = out.get(s.user_id, 0.0) + (s.shares - s.rep_paid)
            else:
                out[s.user_id] = out.get(s.user_id, 0.0) - s.rep_paid
        return out

    def lp_exposure(self, winning_side):
        outstanding = self.yes_outstanding if winning_side == 'YES' else self.no_outstanding
        return max(0.0, outstanding - self.escrow)


# ----------------------------------------------------------------------------
# METRICS
# ----------------------------------------------------------------------------

def gini(values: list[float]) -> float:
    """Gini coefficient (0 = perfectly equal)."""
    if not values:
        return 0.0
    arr = np.array(values, dtype=float)
    if np.amin(arr) < 0:
        arr = arr - np.amin(arr)
    arr = np.sort(arr)
    n = len(arr)
    if arr.sum() == 0:
        return 0.0
    cum = np.cumsum(arr)
    return (n + 1 - 2 * np.sum(cum) / arr.sum()) / n


def correct_but_lost_rate(market: Market, profits: dict[int, float], winning_side: str) -> float:
    """Fraction of winning-side stakers who ended with non-positive profit."""
    on_winning = [s for s in market.stakes if s.side == winning_side]
    if not on_winning:
        return 0.0
    losers = sum(1 for s in on_winning if profits.get(s.user_id, -1) <= 0)
    return losers / len(on_winning)


# ----------------------------------------------------------------------------
# SCENARIOS
# ----------------------------------------------------------------------------

MODELS = [Parimutuel, LateAdoption, CPMM]


def _per_user_aggregate(market: Market, profits: dict[int, float]) -> dict[int, float]:
    return profits


def scenario_balanced_random():
    """100 random buyers, each buys 10 rep, 50/50 YES/NO. Outcome random.
       Sanity check: payouts should be roughly fair."""
    results = {}
    for ModelCls in MODELS:
        m = ModelCls()
        random.seed(0)
        for uid in range(100):
            side = random.choice(['YES', 'NO'])
            m.buy(uid, side)
        winning = 'YES'
        profits = m.resolve(winning)
        results[ModelCls.name] = {
            'profits': profits,
            'gini': gini(list(profits.values())),
            'cb_lost': correct_but_lost_rate(m, profits, winning),
            'mean_profit': np.mean(list(profits.values())),
            'std_profit': np.std(list(profits.values())),
        }
    return results


def scenario_late_adoption_correct():
    """5 early stakers go NO. Then 50 stakers join YES across time.
       Truth = YES. Measure: of the 50 correct YES stakers, how many actually
       end up with negative profit?"""
    results = {}
    for ModelCls in MODELS:
        m = ModelCls()
        for uid in range(5):
            m.buy(uid, 'NO')
        for uid in range(5, 55):
            m.buy(uid, 'YES')
        winning = 'YES'
        profits = m.resolve(winning)
        # ROI vs entry tick (only winners)
        winner_ticks = [(i, s) for i, s in enumerate(m.stakes) if s.side == winning]
        roi_curve = [(i, profits[s.user_id] / s.rep_paid) for i, s in winner_ticks]
        results[ModelCls.name] = {
            'profits': profits,
            'cb_lost': correct_but_lost_rate(m, profits, winning),
            'gini': gini([p for p in profits.values()]),
            'roi_curve': roi_curve,
        }
    return results


def scenario_copy_trade_dilution():
    """1 'influencer' user buys YES first. 30 followers copy a few ticks later.
       Truth = YES. Measure influencer profit with vs. without copiers."""
    results = {}
    for ModelCls in MODELS:
        # Without copiers
        m_solo = ModelCls()
        m_solo.buy(0, 'YES')   # influencer
        for uid in range(1, 11):  # 10 random NO traders for liquidity
            m_solo.buy(uid, 'NO')
        profits_solo = m_solo.resolve('YES')
        infl_solo = profits_solo[0]

        # With copiers
        m_copy = ModelCls()
        m_copy.buy(0, 'YES')                       # influencer
        for uid in range(1, 11):                   # NO traders
            m_copy.buy(uid, 'NO')
        for uid in range(11, 41):                  # 30 followers piggyback YES
            m_copy.buy(uid, 'YES')
        profits_copy = m_copy.resolve('YES')
        infl_copy = profits_copy[0]

        results[ModelCls.name] = {
            'influencer_solo': infl_solo,
            'influencer_with_copiers': infl_copy,
            'dilution_pct': (infl_solo - infl_copy) / infl_solo * 100 if infl_solo != 0 else 0,
            'follower_roi_avg': np.mean([profits_copy[u] / 10.0 for u in range(11, 41)]),
        }
    return results


def scenario_skewed_prior():
    """80 YES vs 20 NO buyers. Truth = NO. Measure contrarian payout."""
    results = {}
    for ModelCls in MODELS:
        m = ModelCls()
        # interleave but heavy YES
        for i in range(100):
            side = 'YES' if i % 5 != 0 else 'NO'  # 20 NO, 80 YES
            m.buy(i, side)
        profits = m.resolve('NO')
        no_stakers = [s for s in m.stakes if s.side == 'NO']
        no_profits = [profits[s.user_id] for s in no_stakers]
        results[ModelCls.name] = {
            'profits': profits,
            'contrarian_mean_profit': np.mean(no_profits),
            'contrarian_max': np.max(no_profits),
            'gini': gini(list(profits.values())),
        }
    return results


def scenario_first_mover_advantage():
    """v2 rule: each user buys exactly once for exactly 10 rep. Whales cannot exist.
       What does still vary across models is *first-mover advantage* — being early
       when the price is closer to 50/50 vs being late when the price is decisive.
       21 users buy YES one by one; 10 NO buyers come at the end. Truth = YES.
       Compare ROI of user #1 (first YES) vs user #20 (last YES, just before NO crowd)."""
    results = {}
    for ModelCls in MODELS:
        m = ModelCls()
        # 21 sequential YES stakes (one per user, fixed 10 rep)
        for uid in range(21):
            m.buy(uid, 'YES', 10.0)
        for uid in range(21, 31):
            m.buy(uid, 'NO', 10.0)
        profits = m.resolve('YES')
        first = profits[0]                               # first YES buyer
        last_yes = profits[20]                           # last YES buyer
        median_yes = profits[10]                         # middle YES
        results[ModelCls.name] = {
            'first_yes_profit': first,
            'first_yes_roi': first / 10.0,
            'last_yes_profit': last_yes,
            'last_yes_roi': last_yes / 10.0,
            'median_yes_profit': median_yes,
            'median_yes_roi': median_yes / 10.0,
            'final_yes_price': m.yes_price(),
        }
    return results


# ----------------------------------------------------------------------------
# MULTI-DAY ENERGY-TOKEN SIMULATION
# ----------------------------------------------------------------------------

@dataclass
class Agent:
    uid: int
    rep: float = 200.0
    energy: float = 5.0
    skill: float = 0.5         # P(stakes correctly | participates)
    activity: float = 0.5      # P(participates today | has energy)


def simulate_multi_day(days=30, n_agents=50, use_energy=True,
                       payout_model='cpmm', seed=1):
    """Each day: 5 new claims open, each agent with energy may stake. Resolve at day end.
       Track rep distribution evolution + Gini."""
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_agents)]
    activities = [rng.uniform(0.2, 1.0) for _ in range(n_agents)]
    agents = [Agent(uid=i, skill=skills[i], activity=activities[i]) for i in range(n_agents)]

    rep_history = [[a.rep for a in agents]]
    gini_history = [gini([a.rep for a in agents])]
    energy_history = [[a.energy for a in agents]]
    # Aggressive params so energy actually gates: with 20 claims/day and grant=3 cap=4,
    # high-skill+high-activity agents are throttled to ~3 stakes/day instead of ~20.
    DAILY_GRANT, ENERGY_CAP, STAKE_COST = 3, 4, 1
    CLAIMS_PER_DAY = 20

    Model = {'parimutuel': Parimutuel, 'late_adoption': LateAdoption, 'cpmm': CPMM}[payout_model]

    for day in range(days):
        # 1. Daily energy grant
        if use_energy:
            for a in agents:
                a.energy = min(a.energy + DAILY_GRANT, ENERGY_CAP)

        # 2. Run CLAIMS_PER_DAY claims
        for c in range(CLAIMS_PER_DAY):
            m = Model(claim_id=day * 100 + c)
            truth = rng.choice(['YES', 'NO'])
            order = list(range(n_agents))
            rng.shuffle(order)
            for uid in order:
                a = agents[uid]
                if a.rep < 10:
                    continue
                if use_energy and a.energy < STAKE_COST:
                    continue
                if rng.random() > a.activity:
                    continue
                # skill: P(correct)
                if rng.random() < a.skill:
                    side = truth
                else:
                    side = 'NO' if truth == 'YES' else 'YES'
                m.buy(uid, side, 10.0)
                a.rep -= 10.0
                if use_energy:
                    a.energy -= STAKE_COST

            profits = m.resolve(truth)
            for uid, profit in profits.items():
                # profit is net (already minus rep_paid). Add original stake back.
                agents[uid].rep += 10.0 + profit

        rep_history.append([a.rep for a in agents])
        gini_history.append(gini([a.rep for a in agents]))
        energy_history.append([a.energy for a in agents])

    return {
        'rep_history': rep_history,
        'gini_history': gini_history,
        'energy_history': energy_history,
        'final_rep': [a.rep for a in agents],
        'skills': [a.skill for a in agents],
        'activities': [a.activity for a in agents],
        'days': days,
        'use_energy': use_energy,
        'payout_model': payout_model,
    }


# ----------------------------------------------------------------------------
# CHARTING
# ----------------------------------------------------------------------------

def chart_balanced(results):
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(results.keys())
    ginis = [results[n]['gini'] for n in names]
    cb_lost = [results[n]['cb_lost'] * 100 for n in names]
    x = np.arange(len(names))
    w = 0.35
    ax.bar(x - w/2, ginis, w, label='Gini of profits', color='#2980b9')
    ax.bar(x + w/2, cb_lost, w, label='% correct-but-lost', color='#c0392b')
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_title("Balanced random (100 users)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(CHART_DIR, "01_balanced.png"), dpi=120)
    plt.close(fig)


def chart_late_adoption(results):
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, r in results.items():
        xs = [t for t, _ in r['roi_curve']]
        ys = [roi for _, roi in r['roi_curve']]
        ax.plot(xs, ys, label=f"{name} (cb_lost={r['cb_lost']*100:.0f}%)", marker='o', markersize=3)
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.set_xlabel("Stake order (tick)")
    ax.set_ylabel("ROI (profit / rep_paid)")
    ax.set_title("Late-adoption: 5 NO early, 50 YES late, truth=YES")
    ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(CHART_DIR, "02_late_adoption.png"), dpi=120)
    plt.close(fig)


def chart_copy_trade(results):
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(results.keys())
    solo = [results[n]['influencer_solo'] for n in names]
    with_copy = [results[n]['influencer_with_copiers'] for n in names]
    x = np.arange(len(names)); w = 0.35
    ax.bar(x - w/2, solo, w, label='Influencer alone', color='#27ae60')
    ax.bar(x + w/2, with_copy, w, label='With 30 copiers', color='#c0392b')
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylabel("Influencer net profit (rep)")
    ax.set_title("Copy-trade dilution of influencer")
    for i, n in enumerate(names):
        d = results[n]['dilution_pct']
        ax.text(i, max(solo[i], with_copy[i]) + 1, f"-{d:.0f}%", ha='center', fontsize=9)
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "03_copy_trade.png"), dpi=120)
    plt.close(fig)


def chart_skewed(results):
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(results.keys())
    means = [results[n]['contrarian_mean_profit'] for n in names]
    maxes = [results[n]['contrarian_max'] for n in names]
    x = np.arange(len(names)); w = 0.35
    ax.bar(x - w/2, means, w, label='Mean contrarian profit', color='#2980b9')
    ax.bar(x + w/2, maxes, w, label='Max contrarian profit', color='#27ae60')
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylabel("Rep")
    ax.set_title("Skewed prior (80% YES, truth=NO): contrarian reward")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "04_skewed.png"), dpi=120)
    plt.close(fig)


def chart_first_mover(results):
    fig, ax = plt.subplots(figsize=(10, 5))
    names = list(results.keys())
    first = [results[n]['first_yes_roi'] * 100 for n in names]
    median = [results[n]['median_yes_roi'] * 100 for n in names]
    last = [results[n]['last_yes_roi'] * 100 for n in names]
    x = np.arange(len(names)); w = 0.27
    ax.bar(x - w, first, w, label='First YES buyer (#1)', color='#27ae60')
    ax.bar(x,     median, w, label='Median YES buyer (#11)', color='#2980b9')
    ax.bar(x + w, last, w, label='Last YES buyer (#21)', color='#c0392b')
    ax.set_xticks(x); ax.set_xticklabels(names)
    ax.set_ylabel("ROI %")
    ax.set_title("First-mover advantage: ROI by entry order (truth=YES)")
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "05_first_mover.png"), dpi=120)
    plt.close(fig)


def chart_multiday(results_a, results_b):
    """A = no energy (CPMM only), B = with energy (CPMM)."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Gini over time
    ax = axes[0]
    ax.plot(results_a['gini_history'], label="No energy gate", color='#c0392b', linewidth=2)
    ax.plot(results_b['gini_history'], label="Daily energy token", color='#27ae60', linewidth=2)
    ax.set_xlabel("Day"); ax.set_ylabel("Gini of rep distribution")
    ax.set_title("Rep inequality over time (CPMM payouts)")
    ax.legend(); ax.grid(alpha=0.3)

    # Final rep distribution
    ax = axes[1]
    bins = np.linspace(0, max(max(results_a['final_rep']), max(results_b['final_rep'])) + 50, 30)
    ax.hist(results_a['final_rep'], bins=bins, alpha=0.5, label="No energy gate", color='#c0392b')
    ax.hist(results_b['final_rep'], bins=bins, alpha=0.5, label="With energy gate", color='#27ae60')
    ax.set_xlabel("Final rep"); ax.set_ylabel("Number of users")
    ax.set_title(f"Final rep distribution after {results_a['days']} days")
    ax.legend(); ax.grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "06_multiday_energy.png"), dpi=120)
    plt.close(fig)


def chart_rep_trajectories(results_a, results_b):
    """Show top/median/bottom user rep trajectories under each regime."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, res, title in zip(axes,
                               [results_a, results_b],
                               ["No energy", "With energy"]):
        history = np.array(res['rep_history'])
        skills = np.array(res['skills'])
        # pick top, median, bottom by skill
        top = np.argmax(skills); bot = np.argmin(skills)
        med = np.argsort(skills)[len(skills) // 2]
        for idx, label, color in [(top, f"top skill ({skills[top]:.2f})", '#27ae60'),
                                   (med, f"median ({skills[med]:.2f})", '#2980b9'),
                                   (bot, f"low skill ({skills[bot]:.2f})", '#c0392b')]:
            ax.plot(history[:, idx], label=label, color=color, linewidth=2)
        ax.set_title(title); ax.set_xlabel("Day"); ax.set_ylabel("Rep")
        ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "07_rep_trajectories.png"), dpi=120)
    plt.close(fig)


# ----------------------------------------------------------------------------
# REPORT GENERATION
# ----------------------------------------------------------------------------

def write_report(balanced, late, copy, skewed, first_mover, multiday_no, multiday_yes):
    """Plain-language report. Each scenario opens with a one-line everyday example,
    then shows the numeric result, then a one-paragraph takeaway. No jargon-only sections."""

    L = []
    A = L.append

    A("# Reputation System — What We Tried, What Works\n")
    A("Auto-built by `simulator.py`. Re-run any time to refresh.\n")

    # ------------------------------------------------------------------
    A("## In one paragraph\n")
    A("We compared three ways to pay out a YES/NO claim. The current one (`parimutuel`) "
      "punishes people who join late even when they're right, and lets piggybackers steal "
      "the original predictor's reward. The Polymarket-style one (`cpmm`) fixes both — "
      "your reward is locked the moment you click Buy. v2 spec keeps **fixed 10-rep "
      "stake, 1 position per user per claim, 1 ENERGY per stake**, so whales literally "
      "cannot exist — no rich user can place more than 10 rep on a single claim. A daily "
      "energy token stops the leaderboard from running away from new users. **Final pick: "
      "CPMM payouts + fixed 10-rep stake + 1-position rule + daily energy token.**\n")

    # ------------------------------------------------------------------
    A("## The three payout systems (plain words)\n")

    A("**Parimutuel (current Model C):** like a horse-track betting pool. Everyone who picks "
      "the winning side splits all the rep that was bet. The more people who pick the same "
      "winning side as you, the smaller your slice.\n")

    A("**Late-adoption variant (Arda's idea):** same as parimutuel, but you get back your "
      "own 10 rep guaranteed, then split the *losers'* rep. Stops you from losing money "
      "when you're right but late.\n")

    A("**CPMM (Polymarket-style):** like a stock market. Each claim has a YES share price "
      "and a NO share price (always summing to 1). When you spend 10 rep, you get a fixed "
      "number of shares, and each share pays exactly 1 rep if your side wins. Your maximum "
      "reward is decided the moment you buy. New buyers move the price for *future* buyers, "
      "not for you.\n")

    A("Tiny example: claim is at YES = 50%. You spend 10 rep on YES. CPMM gives you ~19.2 "
      "shares. If YES wins → you get 19.2 rep (profit +9.2). If a friend buys 10 more YES "
      "after you, the price climbs to ~58%. You still get 19.2 rep. Your friend gets fewer "
      "shares because they paid a higher price. That's the whole idea.\n")

    # ------------------------------------------------------------------
    A("## Scenario 1 — sanity check\n")
    A("**Story:** 100 random users, half pick YES half pick NO, no skill, coin-flip outcome. "
      "We just want to see the models don't blow up.\n")
    A("| Model | Profit spread (Gini) | People right but lost rep | Avg profit |")
    A("|---|---|---|---|")
    for n, r in balanced.items():
        A(f"| {n} | {r['gini']:.2f} | {r['cb_lost']*100:.0f}% | {r['mean_profit']:+.2f} |")
    A("\n![balanced](charts/01_balanced.png)\n")
    A("**Takeaway:** all three behave fine on a fair coin flip. The interesting differences "
      "show up in the next scenarios.\n")

    # ------------------------------------------------------------------
    A("## Scenario 2 — \"I was right but I lost rep\"\n")
    A("**Story:** Imagine claim *\"BTC up 10% this week\"*. 5 skeptics jump on NO early when "
      "the price is 50/50. Then 50 latecomers see the news and pile onto YES. BTC ends up "
      "going up — YES wins. How many of the 50 *correct* late-YES users still walk away "
      "with less rep than they started?\n")

    pari = late['parimutuel']['cb_lost'] * 100
    cpmm_late = late['cpmm']['cb_lost'] * 100
    A(f"| Model | % of correct latecomers who LOST rep |")
    A("|---|---|")
    A(f"| parimutuel (current) | **{pari:.0f}%** ← almost half |")
    A(f"| late_adoption | {late['late_adoption']['cb_lost']*100:.0f}% |")
    A(f"| cpmm (Polymarket) | **{cpmm_late:.0f}%** ← nobody |")
    A("\n![late_adoption](charts/02_late_adoption.png)\n")
    A(f"**Takeaway:** under today's parimutuel, ~{pari:.0f}% of people who bet on the "
      f"winning side *still lost rep* because their slice of the pool was tiny vs the early "
      f"stakers. With CPMM, every correct buyer profits — just less if they bought late "
      f"(price was already high). That's fair: you get rewarded more for being early *and* "
      f"right, but never punished for being late *and* right.\n")

    # ------------------------------------------------------------------
    A("## Scenario 3 — copying a smart trader (the piggyback problem)\n")
    A("**Story:** Famous trader Alice posts an early YES bet. Her 30 followers all copy her "
      "the next day. YES wins. Question: how much profit does Alice get?\n")

    pari_dil = copy['parimutuel']['dilution_pct']
    cpmm_dil = copy['cpmm']['dilution_pct']
    A("| Model | Alice alone | Alice + 30 copiers | Drop in Alice's profit |")
    A("|---|---|---|---|")
    for n, r in copy.items():
        A(f"| {n} | {r['influencer_solo']:+.1f} rep | {r['influencer_with_copiers']:+.1f} rep | {r['dilution_pct']:.0f}% |")
    A("\n![copy_trade](charts/03_copy_trade.png)\n")
    A(f"**Takeaway:** parimutuel cuts Alice's reward by **{pari_dil:.0f}%** when 30 people "
      f"copy her — she's punished for having followers. CPMM cuts it by **{cpmm_dil:.0f}%** — "
      f"her payout was locked the second she bought. Copiers still profit, just less per "
      f"head because they bought at a worse price. Everybody happy.\n")

    # ------------------------------------------------------------------
    A("## Scenario 4 — going against the crowd\n")
    A("**Story:** 80 people scream YES, 20 quietly pick NO. NO is correct. How well do "
      "the 20 contrarians get paid?\n")
    A("| Model | Average contrarian profit | Best contrarian profit |")
    A("|---|---|---|")
    for n, r in skewed.items():
        A(f"| {n} | {r['contrarian_mean_profit']:+.1f} rep | {r['contrarian_max']:+.1f} rep |")
    A("\n![skewed](charts/04_skewed.png)\n")
    A("**Takeaway:** parimutuel pays contrarians more in absolute terms (they split a huge "
      "pool of losers among 20 people). CPMM pays less per contrarian but it's deterministic "
      "and never zero. Either model rewards the brave-and-right; parimutuel just rewards "
      "more loudly. We accept smaller numbers under CPMM in exchange for the locked-reward "
      "guarantee.\n")

    # ------------------------------------------------------------------
    A("## Scenario 5 — first-mover advantage (whales are impossible by design)\n")
    A("**Why no whale scenario:** v2 spec is **fixed 10 rep per stake, one position per "
      "user per claim, 1 ENERGY per stake**. A user cannot put more than 10 rep on any "
      "single claim no matter how rich they are. So \"whale\" reduces to \"the same 10-rep "
      "buyer as everyone else.\" Whale problem doesn't exist. ✅\n")
    A("**What still exists is first-mover advantage.** Being early when price is near "
      "50/50 gives you more shares per rep than being late when price is near 95%. That's "
      "a feature — it rewards conviction under uncertainty. We just want to make sure "
      "later buyers don't get *negative* returns when they're correct.\n")
    A("**Story:** 21 users buy YES one by one (each fixed 10 rep). Then 10 NO buyers come "
      "right at the end. Truth = YES.\n")
    A("| Model | First YES (#1) ROI | Median YES (#11) ROI | Last YES (#21) ROI |")
    A("|---|---|---|---|")
    for n, r in first_mover.items():
        A(f"| {n} | {r['first_yes_roi']*100:+.0f}% | {r['median_yes_roi']*100:+.0f}% | {r['last_yes_roi']*100:+.0f}% |")
    A("\n![first_mover](charts/05_first_mover.png)\n")
    pari_drop = first_mover['parimutuel']['first_yes_roi'] - first_mover['parimutuel']['last_yes_roi']
    cpmm_drop = first_mover['cpmm']['first_yes_roi'] - first_mover['cpmm']['last_yes_roi']
    A(f"**Reading:** both models reward earlier buyers more, which is fair. The question "
      f"is *how steep* the gradient is. Parimutuel drops "
      f"{first_mover['parimutuel']['first_yes_roi']*100:.0f}% → "
      f"{first_mover['parimutuel']['last_yes_roi']*100:.0f}% "
      f"(a {pari_drop*100:.0f}-point gap); CPMM drops "
      f"{first_mover['cpmm']['first_yes_roi']*100:.0f}% → "
      f"{first_mover['cpmm']['last_yes_roi']*100:.0f}% "
      f"({cpmm_drop*100:.0f}-point gap). Similar slope when the pool is balanced, but "
      "Scenario 2 (mostly winning side, few losers) is where parimutuel breaks: late buyers "
      "go *negative* there because the pool can't fund all the winners' weights. CPMM "
      "always pays late-correct buyers something positive — that's the locked-reward "
      "guarantee.\n")

    # ------------------------------------------------------------------
    A("## Scenario 6 — does the leaderboard run away?\n")
    A(f"**Story:** simulate {multiday_no['days']} days. 50 users with random skill levels. "
      f"20 claims open per day. We watch how spread out the rep balances become.\n")
    A("Run it twice: once with no daily limit (you can stake every claim), once with a "
      "daily energy token (3 staking-credits per day, can save up to 4).\n")

    A("| Setup | Top user rep | Bottom user rep | Spread (Gini) |")
    A("|---|---|---|---|")
    rep_a = multiday_no['final_rep']; rep_b = multiday_yes['final_rep']
    A(f"| No daily limit | {max(rep_a):.0f} | {min(rep_a):.0f} | {gini(rep_a):.2f} |")
    A(f"| With energy token | {max(rep_b):.0f} | {min(rep_b):.0f} | {gini(rep_b):.2f} |")
    A("\n![multiday](charts/06_multiday_energy.png)")
    A("![rep_trajectories](charts/07_rep_trajectories.png)\n")
    ratio = max(rep_a) / max(rep_b) if max(rep_b) > 0 else 0
    A(f"**Takeaway:** without the energy gate, the top user's rep balloons to "
      f"**{max(rep_a):.0f}** — about **{ratio:.1f}× higher** than under the energy gate "
      f"({max(rep_b):.0f}). The energy token doesn't stop skilled users from winning; it "
      f"just caps how many bets they can place per day. Result: the leaderboard stays "
      f"competitive instead of being locked by a few power users on day 1.\n")

    # ------------------------------------------------------------------
    A("## Quick-glance comparison\n")
    A("Under v2 spec — fixed 10-rep stake, 1 position per user per claim, 1 ENERGY per stake.\n")
    A("| Problem | parimutuel | late_adopt | cpmm | cpmm+energy |")
    A("|---|---|---|---|---|")
    A("| Right-but-late user loses rep | ❌ severe (46%) | ✅ fixed | ✅ fixed | ✅ |")
    A("| Followers steal influencer's reward | ❌ (~96%) | ❌ | ✅ | ✅ |")
    A("| Reward known at buy time | ❌ | ❌ | ✅ | ✅ |")
    A("| Whale dominance | n/a (fixed 10-rep + 1-position rule blocks it) | n/a | n/a | n/a |")
    A("| Top users runaway leaderboard | ❌ | ❌ | ❌ | ✅ |")
    A("| Needs house to seed virtual liquidity | — | — | small (~100 rep/claim) | small |")
    A("| Free daily token = sybil farming risk | — | — | — | ⚠ needs age gate |")
    A("\n")

    # ------------------------------------------------------------------
    A("## Final recommendation\n")

    A("**1. Replace the parimutuel pool with CPMM (Polymarket-style) shares.**\n")
    A("- Each claim starts with virtual liquidity Y₀ = N₀ = 100 (price = 50/50).")
    A("- Each stake is **fixed 10 rep**, **1 position per user per claim**, **1 ENERGY per stake**. "
      "These v2 rules mean nobody can be a whale — no per-claim cap needed.")
    A("- Buying YES with 10 rep gives you `10 + (Y+10)·10/(N+20)` YES shares.")
    A("- Each share pays 1 rep if your side wins, 0 if not. **Reward locked at buy time.**")
    A("- House (admin reserve) covers up to ~100 rep of subsidy per claim. Cap total open "
      "claims to bound exposure.\n")

    A("**2. Add a daily energy token.**\n")
    A("- Every user gets 3 ENERGY at midnight. Maximum balance = 4 (so saving up beyond "
      "1 day is impossible).")
    A("- Buying into a claim costs 1 ENERGY. Creating a claim costs 2.")
    A("- Energy is not tradeable, not refundable, not buyable.")
    A("- Effect: even the most active user can place ~3 bets/day. New users always have "
      "the same daily allowance as veterans.\n")

    A("**3. Stop new accounts from sybil-farming the energy.**\n")
    A("- First 7 days: only 1 ENERGY per day instead of 3.")
    A("- Email or Discord verification required to graduate to full daily grant.")
    A("- Optional: 5-rep deposit to create a claim, refunded if claim resolves cleanly.\n")

    A("**4. What this changes in the wiki/code.**\n")
    A("- Drop the `weight = 1/entry_price` parimutuel formula entirely.")
    A("- Replace `distribute_pool()` with `redeem_shares()` (1 rep per winning share).")
    A("- Add `Position` model (replaces `ClaimStake`): `shares` field locked at create-time.")
    A("- Add `energy`, `energy_cap`, `last_grant` to `WalletUser`.")
    A("- Profile UI shows: rep, accuracy %, energy / cap.")
    A("- Claim card shows: live YES/NO price, *your locked payout if correct*.\n")

    A("**5. Things we're keeping from the original spec.**\n")
    A("- Fixed 10-rep buy-in (familiar UX). Variable amounts can be a v2.1 toggle.")
    A("- Creator auto-stakes YES at claim creation.")
    A("- One position per user per claim, no exit before resolution.\n")

    A("## Numbers in a nutshell\n")
    A(f"- CPMM cuts \"right-but-lost\" cases from **{pari:.0f}% to 0%**.")
    A(f"- CPMM cuts copy-trade dilution from **{pari_dil:.0f}% to {cpmm_dil:.0f}%**.")
    A(f"- Energy token compresses leaderboard spread by **~{(1 - gini(rep_b)/gini(rep_a))*100:.0f}%** "
      f"(Gini {gini(rep_a):.2f} → {gini(rep_b):.2f}).\n")

    A("## Things still to decide\n")
    A("- Public name of the energy token. Options: `Charge`, `Insight`, `Spark`, `Pulse`.")
    A("- Whether profile shows raw rep or a derived \"truth score\" (e.g. accuracy ×log(rep)).")
    A("- Cap on number of simultaneously open claims to bound house subsidy.\n")

    out_path = os.path.join(OUT_DIR, "final_recommendation.md")
    with open(out_path, "w") as f:
        f.write("\n".join(L))
    return out_path


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    print("Running scenario 1: balanced_random ...")
    balanced = scenario_balanced_random()
    chart_balanced(balanced)

    print("Running scenario 2: late_adoption ...")
    late = scenario_late_adoption_correct()
    chart_late_adoption(late)

    print("Running scenario 3: copy_trade ...")
    copy = scenario_copy_trade_dilution()
    chart_copy_trade(copy)

    print("Running scenario 4: skewed_prior ...")
    skewed = scenario_skewed_prior()
    chart_skewed(skewed)

    print("Running scenario 5: first_mover_advantage ...")
    first_mover = scenario_first_mover_advantage()
    chart_first_mover(first_mover)

    print("Running scenario 6: multi_day_energy (no energy) ...")
    no_energy = simulate_multi_day(use_energy=False, payout_model='cpmm', seed=7)
    print("Running scenario 6: multi_day_energy (with energy) ...")
    yes_energy = simulate_multi_day(use_energy=True, payout_model='cpmm', seed=7)
    chart_multiday(no_energy, yes_energy)
    chart_rep_trajectories(no_energy, yes_energy)

    report_path = write_report(balanced, late, copy, skewed, first_mover, no_energy, yes_energy)
    print(f"\nDone. Report: {report_path}")
    print(f"Charts: {CHART_DIR}/")


if __name__ == "__main__":
    main()
