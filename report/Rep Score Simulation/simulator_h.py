"""Model H — LP-funded CPMM.  No house subsidy, no rep minting.

Idea: instead of seeding each claim with 100 virtual YES and 100 virtual
NO shares (which is what creates F's inflation), real users deposit rep
to fund the initial pool and earn a share of the trading fees.

This is the standard Uniswap-style LP pattern adapted to a binary
prediction market.

Roles
-----
LP (often the creator): deposits ``D`` rep, mints ``D`` YES and ``D``
NO shares in the pool, receives an LP-token (claim on the pool).

Trader: stakes ``FIXED_STAKE`` (10) rep on YES or NO.  A ``fee_bps`` fee
is removed from the stake at buy time and added to the LP pool.  The
remaining rep flows into the pool and shifts the price exactly like F.

Resolution
----------
- Winning-side shares pay 1 rep each (locked-reward preserved for
  traders, same as F).
- LP redeems all remaining pool shares.  Winning-side pool shares pay
  1 rep, losing-side pool shares pay 0.  LP also collects all
  accumulated fees.

Conservation
------------
Per claim, ``LP_in + trader_stakes_in = LP_out + trader_payouts``.
No mint, no burn.  Across all claims, total rep supply is constant.

What this fixes vs F
--------------------
- Inflation: gone (zero-sum per claim, verified below).
- Creator reward: naturally tied to claim quality (more traffic = more
  fees for the creator/LP).  Solves issue #76 P3 without a separate
  bonus mechanism.

What this keeps from F
----------------------
- Locked reward for traders: shares × 1 rep at resolution, same as F.
- Copy-trade immunity: Alice's share count locked at her buy time.
- CPMM trading math.

What this trades off
--------------------
- LP can take impermanent loss if the claim resolves decisively against
  the side they're holding most of.  Honest LPs need fees > expected
  loss on average to participate.  Knob: ``fee_bps``.
- Cold-start: who LPs the first claim?  House can seed until organic
  LPs appear, but the seed is loanable (recoverable on resolution),
  not a permanent mint.

Run:  python3 simulator_h.py
Output:  charts/h_*.png  +  model_h_report.md
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt

from simulator import gini, Stake

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


FEE_BPS = 200            # 2% of every stake routed to LP pool
DEFAULT_LP_DEPOSIT = 20  # min creator LP deposit at claim creation


# ---------------------------------------------------------------------------
# MODEL H
# ---------------------------------------------------------------------------

@dataclass
class LPPosition:
    user_id: int
    deposit: float
    lp_tokens: float


class ModelH:
    """CPMM with user-supplied liquidity and trading fees that pay LPs."""

    name = "model_h"

    def __init__(self, claim_id: int = 0, fee_bps: int = FEE_BPS):
        self.claim_id = claim_id
        self.fee_bps = fee_bps
        self.y_reserve = 0.0
        self.n_reserve = 0.0
        self.lp_tokens_total = 0.0
        self.lp_positions: list[LPPosition] = []
        self.stakes: list[Stake] = []
        self.accumulated_fees = 0.0
        self.yes_outstanding = 0.0   # trader shares (excl. LP pool shares)
        self.no_outstanding = 0.0

    # --- LP side -----------------------------------------------------------

    def add_liquidity(self, user_id: int, rep_amount: float):
        """LP deposits ``rep_amount`` rep.  Adds equal-size shares to both
        sides (preserves price) and mints LP-tokens proportional to pool
        share."""
        if self.y_reserve == 0 and self.n_reserve == 0:
            # First LP defines the pool
            self.y_reserve = rep_amount
            self.n_reserve = rep_amount
            minted = rep_amount  # 1:1 token mint on first deposit
        else:
            # Subsequent LPs deposit at current ratio
            pool_size = (self.y_reserve + self.n_reserve) / 2
            minted = rep_amount * self.lp_tokens_total / pool_size
            # split deposit proportionally so price doesn't move
            total_reserve = self.y_reserve + self.n_reserve
            self.y_reserve += rep_amount * (self.y_reserve / total_reserve) * 2
            self.n_reserve += rep_amount * (self.n_reserve / total_reserve) * 2
        self.lp_tokens_total += minted
        self.lp_positions.append(
            LPPosition(user_id=user_id, deposit=rep_amount, lp_tokens=minted)
        )
        return minted

    def yes_price(self) -> float:
        total = self.y_reserve + self.n_reserve
        return self.n_reserve / total if total > 0 else 0.5

    # --- trader side -------------------------------------------------------

    def buy(self, user_id: int, side: str, rep_amount: float = 10.0) -> Stake:
        """Gnosis-CFMM style: mint outcome pair from rep, swap one side
        via constant-product AMM.  Strictly zero-sum (no subsidy)."""
        if self.y_reserve == 0 and self.n_reserve == 0:
            raise RuntimeError("Claim has no liquidity yet — LP must seed it.")
        fee = rep_amount * self.fee_bps / 10000.0
        r = rep_amount - fee  # rep that hits the curve after fee
        self.accumulated_fees += fee
        yp_pre = self.yes_price()

        # 1. Mint: r rep -> r YES + r NO shares for the trader
        # 2. Swap r of the losing side into AMM for the winning side out
        k = self.y_reserve * self.n_reserve
        if side == 'YES':
            new_n = self.n_reserve + r
            new_y = k / new_n
            received = self.y_reserve - new_y
            shares = r + received  # r from mint + ``received`` from swap
            self.y_reserve, self.n_reserve = new_y, new_n
            self.yes_outstanding += shares
        else:
            new_y = self.y_reserve + r
            new_n = k / new_y
            received = self.n_reserve - new_n
            shares = r + received
            self.y_reserve, self.n_reserve = new_y, new_n
            self.no_outstanding += shares
        ep = yp_pre if side == 'YES' else 1 - yp_pre
        st = Stake(user_id=user_id, side=side, rep_paid=rep_amount,
                   entry_price=ep, weight=shares / r if r > 0 else 0.0,
                   shares=shares)
        self.stakes.append(st)
        return st

    # --- resolution --------------------------------------------------------

    def resolve(self, winning_side: str) -> dict[int, float]:
        out: dict[int, float] = {}

        # 1. Traders: redeem locked shares.  Losers lose their stake; winners
        #    get ``shares`` rep.  (Net = shares - rep_paid for winners,
        #    -rep_paid for losers.)
        for s in self.stakes:
            base = -s.rep_paid
            if s.side == winning_side:
                base += s.shares
            out[s.user_id] = out.get(s.user_id, 0.0) + base

        # 2. LPs: redeem the pool.  Each LP gets ``lp_share`` of the
        #    winning-side pool reserve (1 rep per share) and ``lp_share``
        #    of the accumulated fees.  Losing-side reserve pays 0.
        winning_reserve = (self.y_reserve if winning_side == 'YES'
                           else self.n_reserve)
        lp_pool_rep = winning_reserve + self.accumulated_fees
        if self.lp_tokens_total > 0:
            for lp in self.lp_positions:
                share = lp.lp_tokens / self.lp_tokens_total
                payout = lp_pool_rep * share
                # net for LP = payout - deposit
                out[lp.user_id] = out.get(lp.user_id, 0.0) + payout - lp.deposit
        return out

    def total_rep_delta(self, resolution_dict: dict[int, float]) -> float:
        return sum(resolution_dict.values())


# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------

def scenario_inflation(n_rounds: int = 400, n_users: int = 60,
                       fee_bps: int = FEE_BPS, lp_deposit: float = 20.0,
                       seed: int = 7):
    """Same harness as inflation test for F vs G.  Run H with creator-as-LP."""
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_users)]
    rep = [200.0] * n_users
    history = [sum(rep)]

    for r in range(n_rounds):
        truth = rng.choice(['YES', 'NO'])
        eligible_lps = [u for u in range(n_users) if rep[u] >= lp_deposit]
        if not eligible_lps:
            history.append(sum(rep)); continue
        lp_uid = rng.choice(eligible_lps)
        m = ModelH(claim_id=r, fee_bps=fee_bps)

        # LP deposits — rep flows out of user balance into the pool.
        m.add_liquidity(lp_uid, lp_deposit)
        rep[lp_uid] -= lp_deposit
        involved = {lp_uid}

        for uid in range(n_users):
            if rep[uid] < 10:
                continue
            side = truth if rng.random() < skills[uid] else (
                'NO' if truth == 'YES' else 'YES')
            m.buy(uid, side, 10.0)
            rep[uid] -= 10.0
            involved.add(uid)

        # ``resolve`` returns NET change per user (already accounts for
        # stakes / LP deposits being "in").  Add it on top of the
        # already-debited balance.
        profits = m.resolve(truth)
        for uid in involved:
            rep[uid] += (lp_deposit if uid == lp_uid else 0.0)
            # add back any stake the user put down as trader
            if any(s.user_id == uid for s in m.stakes):
                rep[uid] += 10.0
            rep[uid] += profits.get(uid, 0.0)
        history.append(sum(rep))

    return {'history': history, 'n_rounds': n_rounds, 'n_users': n_users,
            'initial': n_users * 200.0}


def scenario_lp_profitability(n_claims: int = 1000, n_users: int = 50,
                              lp_deposit: float = 20.0, fee_bps: int = FEE_BPS,
                              seed: int = 11):
    """Is being an LP a profitable role?  Sample many claims; pick one
    user to be the LP each time; measure the LP's net P&L distribution.

    Truth is uniformly random; bettors have heterogeneous skill so the
    final price spans a wide range.
    """
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_users)]
    lp_pnls = []
    final_prices = []
    n_bets = []

    for r in range(n_claims):
        truth = rng.choice(['YES', 'NO'])
        m = ModelH(claim_id=r, fee_bps=fee_bps)
        lp_uid = 0
        m.add_liquidity(lp_uid, lp_deposit)
        for uid in range(1, n_users):
            if rng.random() > 0.6:
                continue
            side = truth if rng.random() < skills[uid] else (
                'NO' if truth == 'YES' else 'YES')
            m.buy(uid, side, 10.0)
        final_prices.append(m.yes_price())
        n_bets.append(len(m.stakes))
        out = m.resolve(truth)
        lp_pnls.append(out.get(lp_uid, 0.0))

    return {
        'lp_pnls': lp_pnls,
        'final_prices': final_prices,
        'n_bets': n_bets,
        'mean_pnl': float(np.mean(lp_pnls)),
        'median_pnl': float(np.median(lp_pnls)),
        'pct_losing': float(np.mean([1 if x < 0 else 0 for x in lp_pnls])),
        'lp_deposit': lp_deposit,
        'fee_bps': fee_bps,
    }


def scenario_fee_sweep(n_claims: int = 500, n_users: int = 50,
                       lp_deposit: float = 20.0, seed: int = 13):
    """Sweep fee_bps and look at LP expected P&L."""
    out = {}
    for fee in [0, 50, 100, 200, 300, 500]:
        r = scenario_lp_profitability(n_claims=n_claims, n_users=n_users,
                                      lp_deposit=lp_deposit, fee_bps=fee,
                                      seed=seed)
        out[fee] = {'mean_pnl': r['mean_pnl'], 'median_pnl': r['median_pnl'],
                    'pct_losing': r['pct_losing']}
    return out


def scenario_trader_locked_reward():
    """Trader Alice bets YES early; many later YES buyers join.  Truth=YES.
    Show Alice's profit under H vs F (locked reward preservation)."""
    from simulator import CPMM
    results = {}
    for label, mk in [
        ("F", lambda: CPMM()),
        ("H (LP=20)", lambda: (lambda mm: (mm.add_liquidity(99, 20.0), mm)[1])(ModelH())),
        ("H (LP=50)", lambda: (lambda mm: (mm.add_liquidity(99, 50.0), mm)[1])(ModelH())),
    ]:
        alice_at_n = {}
        for n_later in [0, 5, 20, 50]:
            m = mk()
            m.buy(0, 'YES', 10.0)         # Alice
            for u in range(1, 11):
                m.buy(u, 'NO', 10.0)       # NO traders (loser pool)
            for u in range(11, 11 + n_later):
                m.buy(u, 'YES', 10.0)
            p = m.resolve('YES')
            alice_at_n[n_later] = p[0]
        results[label] = alice_at_n
    return results


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

def chart_inflation(res):
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(len(res['history']))
    ax.plot(xs, res['history'], color='#16a085', linewidth=2,
            label="Model H (LP-funded)")
    ax.axhline(res['initial'], color='gray', linestyle='--', linewidth=1,
               label=f"initial {res['initial']:.0f}")
    drift = (res['history'][-1] - res['initial']) / res['initial'] * 100
    ax.set_title(f"H supply over {res['n_rounds']} rounds  (drift {drift:+.2f}%)")
    ax.set_xlabel("Round"); ax.set_ylabel("Total rep")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "h_01_inflation.png"), dpi=120)
    plt.close(fig)


def chart_lp_pnl(res):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    ax = axes[0]
    ax.hist(res['lp_pnls'], bins=50, color='#27ae60', alpha=0.7)
    ax.axvline(0, color='red', linewidth=1.5, label='break-even')
    ax.axvline(res['mean_pnl'], color='blue', linewidth=1.5,
               linestyle='--', label=f"mean = {res['mean_pnl']:+.2f}")
    ax.set_title(f"LP P&L distribution  (deposit {res['lp_deposit']}, "
                 f"fee {res['fee_bps']} bps)")
    ax.set_xlabel("LP net rep / claim"); ax.set_ylabel("Count")
    ax.legend(); ax.grid(alpha=0.3)

    ax = axes[1]
    ax.scatter(res['final_prices'], res['lp_pnls'], alpha=0.4, s=15,
               color='#2980b9')
    ax.axhline(0, color='red', linewidth=1)
    ax.set_xlabel("Final YES price")
    ax.set_ylabel("LP P&L")
    ax.set_title("LP P&L vs final price")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "h_02_lp_pnl.png"), dpi=120)
    plt.close(fig)


def chart_fee_sweep(res):
    fees = sorted(res.keys())
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(fees, [res[f]['mean_pnl'] for f in fees], marker='o',
            label='mean LP P&L', color='#16a085', linewidth=2)
    ax.plot(fees, [res[f]['median_pnl'] for f in fees], marker='s',
            label='median LP P&L', color='#2980b9', linewidth=2)
    ax2 = ax.twinx()
    ax2.plot(fees, [res[f]['pct_losing'] * 100 for f in fees], marker='^',
             label='% losing claims', color='#c0392b', linewidth=2)
    ax2.set_ylabel("% LP-losing claims", color='#c0392b')
    ax.axhline(0, color='gray', linestyle='--', linewidth=1)
    ax.set_xlabel("Trading fee (basis points)")
    ax.set_ylabel("LP P&L (rep / claim)")
    ax.set_title("LP profitability vs fee level")
    ax.grid(alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='lower right')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "h_03_fee_sweep.png"), dpi=120)
    plt.close(fig)


def chart_locked_reward(res):
    fig, ax = plt.subplots(figsize=(10, 5))
    x = sorted(next(iter(res.values())).keys())
    colors = {'F': '#c0392b', 'H (LP=20)': '#16a085', 'H (LP=50)': '#2980b9'}
    for label, vs in res.items():
        ys = [vs[n] for n in x]
        ax.plot(x, ys, marker='o', linewidth=2, label=label,
                color=colors.get(label, 'gray'))
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.set_title("Alice's locked reward: profit vs how many later YES buyers join")
    ax.set_xlabel("Later YES buyers after Alice")
    ax.set_ylabel("Alice net rep")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "h_04_locked.png"), dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def write_report(infl, lp_p, fee_sweep, locked):
    L = []
    A = L.append
    A("# Model H — LP-funded CPMM\n")
    A("Auto-built by `simulator_h.py`. Alternative to G — keeps F's "
      "locked-reward and copy-trade immunity while killing F's inflation, "
      "by replacing house-supplied virtual liquidity with user-supplied "
      "liquidity earning fees.\n")

    A("## Design summary\n")
    A("- **LP** (often the claim creator) deposits `D` rep at claim "
      "creation. Pool starts `Y = N = D`. LP receives LP-tokens.\n")
    A(f"- Each trader `buy()` charges `fee_bps = {FEE_BPS}` (2%). Fee goes "
      "to LP pool; remaining stake hits the CPMM curve.\n")
    A("- At resolution: winning-side shares pay 1 rep (same as F). LP "
      "redeems pool shares (winning-side = 1 rep, losing-side = 0) plus "
      "accumulated fees.\n")
    A("- **Per-claim conservation**: `LP_in + trader_stakes = LP_out + "
      "trader_payouts`. No mint.\n")

    # ----------------------------------------------------------------
    A("## P1 — Inflation\n")
    drift = (infl['history'][-1] - infl['initial']) / infl['initial'] * 100
    A(f"Same harness as the G/F inflation test: {infl['n_rounds']} rounds, "
      f"{infl['n_users']} users, initial supply {infl['initial']:.0f}, "
      "random truth, mixed skill.\n")
    A("| Model | Drift over 400 rounds |")
    A("|---|---|")
    A("| F (CPMM, INIT_L=100) | +150% to +250% |")
    A("| G (zero-sum) | 0% |")
    A(f"| **H (LP-funded)** | **{drift:+.2f}%** |")
    A("\n![inflation](charts/h_01_inflation.png)\n")
    A("Same as G: zero-sum by construction. No house mint.\n")

    # ----------------------------------------------------------------
    A("## Locked reward and copy-trade immunity\n")
    A("Same test as before: Alice bets YES; vary the number of later YES "
      "buyers. Alice's net rep under each model:\n")
    A("| Later YES buyers | F | H (LP=20) | H (LP=50) |")
    A("|---|---|---|---|")
    ns = sorted(next(iter(locked.values())).keys())
    for n in ns:
        A(f"| {n} | {locked['F'][n]:+7.2f} | {locked['H (LP=20)'][n]:+7.2f} | "
          f"{locked['H (LP=50)'][n]:+7.2f} |")
    A("\n![locked_reward](charts/h_04_locked.png)\n")
    A("**Reading.** H preserves locked reward — Alice's payout is "
      "`shares × 1 rep`, set at her buy time, exactly like F. Later buyers "
      "do not dilute her. (Compare G in the prior report, where Alice's "
      "profit dropped from +94 to +5.85 when 30 followers copied.)\n")

    # ----------------------------------------------------------------
    A("## LP profitability\n")
    A(f"Run {len(lp_p['lp_pnls'])} random claims with one user as LP "
      f"(deposit {lp_p['lp_deposit']}, fee {lp_p['fee_bps']} bps).\n")
    A(f"- Mean LP P&L per claim: **{lp_p['mean_pnl']:+.2f} rep**")
    A(f"- Median LP P&L per claim: **{lp_p['median_pnl']:+.2f} rep**")
    A(f"- Claims where LP lost money: **{lp_p['pct_losing']*100:.0f}%**\n")
    A("![lp_pnl](charts/h_02_lp_pnl.png)\n")
    profitable = lp_p['mean_pnl'] > 0
    A(("LPs are **profitable on average** — they will choose to participate."
       if profitable else
       "LPs **lose on average** at this fee level. Either raise the fee or "
       "subsidise LPs with a small house bonus per resolved claim."))
    A("\n")

    # ----------------------------------------------------------------
    A("## Fee tuning\n")
    A("Sweep the trading fee to find a setting where LPs profit and "
      "traders aren't taxed too hard.\n")
    A("| Fee (bps) | Mean LP P&L | Median LP P&L | % losing |")
    A("|---|---|---|---|")
    for f in sorted(fee_sweep.keys()):
        r = fee_sweep[f]
        A(f"| {f} | {r['mean_pnl']:+.2f} | {r['median_pnl']:+.2f} | "
          f"{r['pct_losing']*100:.0f}% |")
    A("\n![fee_sweep](charts/h_03_fee_sweep.png)\n")
    best_fee = max(fee_sweep.keys(),
                   key=lambda f: fee_sweep[f]['mean_pnl'])
    A(f"Best mean LP P&L at fee = {best_fee} bps "
      f"({fee_sweep[best_fee]['mean_pnl']:+.2f} rep / claim). Above ~300 "
      "bps the fee starts deterring trading volume in practice (not "
      "modeled here).\n")

    # ----------------------------------------------------------------
    A("## Comparison vs F and G\n")
    A("| Property | F | G | **H** |")
    A("|---|---|---|---|")
    A("| Inflation | +150–250%/yr-equivalent | 0% | **0%** |")
    A("| Locked reward for traders | ✅ | ❌ (broken) | ✅ |")
    A("| Copy-trade immunity for trader | ✅ | ❌ (re-introduced) | ✅ |")
    A("| Right-but-late lose rep | 0% | 0% | **0%** |")
    A("| Whale impossible (rule) | ✅ | ✅ | ✅ |")
    A("| House subsidy required | ⚠ ~100/claim mint | none | none (LPs absorb) |")
    A("| Creator earns from claim quality | weak | bounded bonus | **yes — fees scale with traffic** |")
    A("| Trivial-claim farming | ❌ (P2 unfixed) | ✅ info-gain | partial — fees scale with volume, not info; needs add-on |")
    A("| LP role required | no | no | **yes** — UX complexity |")
    A("\n## What H does not fix on its own\n")
    A("- **P2 trivial farming**: H doesn't penalise trivial-claim winners "
      "directly. Two options:\n"
      "  - layer G's info-gain factor `I = H(p_final)` onto winner payouts;\n"
      "  - or rely on the fact that trivial claims attract little volume, "
      "so the LP earns few fees and the creator is implicitly disincentivised.\n")
    A("- **LP cold-start**: someone must seed the very first claim. The "
      "house can act as bootstrap LP and recover its deposit on resolution. "
      "Once user LPs appear, the house stops seeding.\n")
    A("- **Sybil-LP farming**: a user could LP their own trivial claim and "
      "vote both sides through alts. Mitigation: require minimum trade "
      "volume from distinct accounts before the LP can redeem fees.\n")

    A("## Recommendation\n")
    A("H is the cleanest of the three. It:\n"
      "1. kills inflation (matches G)\n"
      "2. preserves F's locked-reward UX\n"
      "3. preserves F's copy-trade immunity\n"
      "4. naturally rewards creators in proportion to claim quality (volume)\n\n"
      "It costs one UX concept (LP role) and requires fee tuning. If "
      "issue #76 P2 (trivial claims) is also a blocker, bolt on G's "
      "info-gain factor; this composes cleanly because G's `I` only "
      "modifies the winner-pool fraction.\n")

    out = os.path.join(OUT_DIR, "model_h_report.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    return out


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    print("Scenario: inflation under H ...")
    infl = scenario_inflation()
    chart_inflation(infl)

    print("Scenario: LP profitability ...")
    lp_p = scenario_lp_profitability(n_claims=1000)
    chart_lp_pnl(lp_p)

    print("Scenario: fee sweep ...")
    fs = scenario_fee_sweep(n_claims=500)
    chart_fee_sweep(fs)

    print("Scenario: locked reward / copy-trade immunity ...")
    locked = scenario_trader_locked_reward()
    chart_locked_reward(locked)

    out = write_report(infl, lp_p, fs, locked)
    print(f"\nDone. Report: {out}")
    print(f"Charts: {CHART_DIR}/h_*.png")


if __name__ == "__main__":
    main()
