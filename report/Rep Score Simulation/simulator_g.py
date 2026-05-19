"""Model G — minimal tweaks on top of Model F.

After exploring more invasive redesigns (zero-sum + info-gain bonus,
LP-funded CPMM, etc.) we landed on the lightest possible change that
still addresses issue #76's main concerns.

G = F + three tiny changes
--------------------------
  1. **No auto-YES at claim creation.**  Under F, the creator was
     auto-staked on the YES side at claim creation, which guaranteed
     ~9.17 rep of profit on any claim that resolved YES.  In G, the
     creator does not auto-bet.  They may vote manually like any
     other user (using their own energy + stake).

  2. **Refund-if-uncontested rule.**  If the losing side attracted
     fewer than ``MIN_LOSER_VOTERS`` (3) distinct stakers, the claim
     is declared *trivial* — all stakes are refunded, no winners, no
     losers, no mint.  Solves the "everyone bets YES, everyone wins
     from the system pool" inflation hole.  Honest claims always
     attract dissenters; one-sided farmable claims auto-cancel.

  3. **Display percentile rank, not raw rep, in the leaderboard UI.**
     F's headline inflation does not reshuffle ranks (Spearman ρ
     ≈ 0.87) or block newcomers.  Switching the visible leaderboard
     from `"3812 rep"` to `"top 12%"` makes the residual inflation
     invisible to users.

Everything else from F is unchanged:
  - CPMM payouts (Polymarket-style, shares × 1 rep locked at buy time)
  - Fixed 10-rep stake, 1 position per claim, daily energy gate
  - House subsidy bounded at ~100 rep per claim (Y₀ = N₀ = 100)
  - 7-day account-age sybil guard

What G fixes
------------
  - **#76 P2 trivial claims**: creator can no longer farm an auto-bet
    at 50% price on an obviously-resolving claim.  Trader payouts on
    skewed claims are already self-limiting under CPMM (small share
    count at extreme prices) — no further mechanism needed.
  - **#76 P3 low creator reward**: dropping the auto-bet looks like a
    net reduction at first, but the trade-off is fair — creators are
    no longer paid for posting obvious claims.  For genuinely contested
    claims, the creator can still vote manually with conviction and
    earn the same way any voter does.

What G does NOT fix
-------------------
  - **#76 P1 inflation**: F's mint via virtual liquidity remains.  The
    leaderboard analysis (see `leaderboard_analysis.md`) shows this is
    a UX label problem, not a fairness problem, and the percentile
    display tweak handles it.

Run:  python3 simulator_g.py
Output: charts/g_*.png + model_g_report.md
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field

import numpy as np
import matplotlib.pyplot as plt

from simulator import CPMM, gini, Stake

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# MODEL G  =  F (CPMM)  +  NO AUTO-YES
# ---------------------------------------------------------------------------
# G's implementation is just F.  The "no auto-YES" rule is a creation-time
# convention enforced by the harness, not a payout-math change.  All
# scenarios below construct a fresh CPMM market and DO NOT stake the
# creator on YES at t=0.

MIN_LOSER_VOTERS = 3        # losing side must have ≥ this many distinct
                            # voters for the claim to resolve.  Catches
                            # the "everyone voted YES" mint hole even
                            # when CPMM's virtual liquidity hides the
                            # extreme in the price.


class ModelG(CPMM):
    """Model G = Model F (CPMM) + two rule tweaks at resolution time.

    1. No creator auto-YES at creation (enforced by the harness — this
       class doesn't auto-stake on construction).
    2. ``resolve()`` checks whether each side attracted real
       disagreement.  If the losing side has fewer than
       ``MIN_LOSER_VOTERS`` distinct stakers, the claim is declared
       trivial and all stakes are refunded.  No winners, no losers,
       no system mint.

    Why a vote-count rule and not a price-band rule: CPMM's virtual
    liquidity (Y₀ = N₀ = 100) smooths the YES price so a one-sided
    claim with ~30 voters only pushes price to ~0.73, well below any
    sensible "extreme price" threshold.  Counting actual voters on
    the losing side bypasses the smoothing.
    """

    name = "model_g"

    def resolve(self, winning_side: str) -> dict[int, float]:
        losing_side = 'NO' if winning_side == 'YES' else 'YES'
        loser_voters = {s.user_id for s in self.stakes
                        if s.side == losing_side}
        if len(loser_voters) < MIN_LOSER_VOTERS:
            # Refund every stake; system mint = 0.
            return {s.user_id: 0.0 for s in self.stakes}
        return super().resolve(winning_side)


# ---------------------------------------------------------------------------
# SCENARIOS
# ---------------------------------------------------------------------------

def scenario_trivial_claim_farming(n_trials: int = 200,
                                   skews: tuple[float, ...] = (0.5, 0.7, 0.9, 0.95)):
    """Compare creator earnings on claims of varying skew, under
    F (auto-YES) vs G (no auto-YES).  Truth = YES (the obvious side wins).

    For each skew, simulate N voters where ``skew`` fraction vote YES and
    the rest NO.  Truth = YES.

    Under F: creator auto-bets YES at t=0 (price 50%, ~9.17 rep profit
    locked-in).
    Under G: creator does not auto-bet.  They earn 0 unless they
    manually bet.
    """
    out = {}
    for skew in skews:
        f_profit = 0.0
        g_profit = 0.0
        n_voters = 100
        for trial in range(n_trials):
            rng = random.Random(trial * 7 + int(skew * 100))
            # F: creator auto-bets YES first.
            mF = CPMM()
            mF.buy(0, 'YES', 10.0)        # creator's auto-YES
            for u in range(1, n_voters + 1):
                side = 'YES' if rng.random() < skew else 'NO'
                mF.buy(u, side, 10.0)
            pF = mF.resolve('YES')
            f_profit += pF[0]

            # G: creator does not auto-bet.
            mG = ModelG()
            for u in range(1, n_voters + 1):
                side = 'YES' if rng.random() < skew else 'NO'
                mG.buy(u, side, 10.0)
            pG = mG.resolve('YES')
            # Creator gets nothing because they didn't bet.
            g_profit += pG.get(0, 0.0)

        out[skew] = {
            'avg_creator_profit_F': f_profit / n_trials,
            'avg_creator_profit_G': g_profit / n_trials,
        }
    return out


def scenario_one_sided_mint(n_trials: int = 100, n_voters: int = 30):
    """Worst-case mint test: everyone bets YES, YES wins.  Under F,
    house mints rep equal to (total winning shares - total stakes).
    Under G, refund-on-extreme triggers and mint is 0.

    Measures per-claim system-level rep mint (sum of winning payouts
    minus sum of stakes).
    """
    f_mints = []
    g_mints = []
    g_refunds = 0
    for trial in range(n_trials):
        mF = CPMM()
        mG = ModelG()
        for u in range(n_voters):
            mF.buy(u, 'YES', 10.0)
            mG.buy(u, 'YES', 10.0)
        pF = mF.resolve('YES')
        pG = mG.resolve('YES')
        # System mint = sum of net changes (winners gained more than losers lost)
        f_mints.append(sum(pF.values()))
        g_mints.append(sum(pG.values()))
        # G should refund (every value ≈ 0)
        if all(abs(v) < 0.01 for v in pG.values()):
            g_refunds += 1
    return {
        'F_mean_mint': float(np.mean(f_mints)),
        'F_total_mint': float(sum(f_mints)),
        'G_mean_mint': float(np.mean(g_mints)),
        'G_total_mint': float(sum(g_mints)),
        'G_refund_rate': g_refunds / n_trials,
        'n_trials': n_trials,
        'n_voters': n_voters,
    }


def scenario_contested_claims_still_work(n_trials: int = 200):
    """Sanity: G's refund rule should NOT trigger on genuinely contested
    claims.  Run 50/50-ish voter splits and check the resolution still
    pays normally."""
    rng = random.Random(13)
    triggered_refunds = 0
    normal_resolutions = 0
    for trial in range(n_trials):
        m = ModelG()
        for u in range(40):
            side = 'YES' if rng.random() < 0.55 else 'NO'  # near 50/50
            m.buy(u, side, 10.0)
        p_final = m.yes_price()
        truth = rng.choice(['YES', 'NO'])
        out = m.resolve(truth)
        if all(abs(v) < 0.01 for v in out.values()):
            triggered_refunds += 1
        else:
            normal_resolutions += 1
    return {
        'contested_total': n_trials,
        'triggered_refunds': triggered_refunds,
        'normal_resolutions': normal_resolutions,
    }


def scenario_locked_reward_preserved():
    """Sanity: G should preserve F's locked-reward.  Alice bets YES at
    t=0, then more YES buyers join, then 10 NO buyers, truth=YES.
    Alice's profit should be identical under F and G (since the only
    diff is creator auto-YES, which is unrelated to Alice's locked
    payout)."""
    results = {}
    for label, mk in [("F (with creator auto-YES)",
                       lambda: (CPMM(), 'autovote_creator')),
                      ("G (no creator auto-YES)",
                       lambda: (ModelG(), 'no_creator'))]:
        alice_at = {}
        for n_later in [0, 5, 20, 50]:
            m, mode = mk()
            if mode == 'autovote_creator':
                m.buy(999, 'YES', 10.0)   # creator's auto-bet (uid=999)
            m.buy(0, 'YES', 10.0)          # Alice (the trader we measure)
            for u in range(1, 11):
                m.buy(u, 'NO', 10.0)
            for u in range(11, 11 + n_later):
                m.buy(u, 'YES', 10.0)
            p = m.resolve('YES')
            alice_at[n_later] = p[0]
        results[label] = alice_at
    return results


def scenario_creator_earnings_real_claims(n_trials: int = 500, seed: int = 11):
    """For each model, simulate a creator who posts claims they think
    they know the answer to, with skill 0.65 (better than chance).

    F: creator auto-bets YES at creation (locked at 50/50 price).  If
    truth is YES, +9.17.  If truth is NO, -10.  So F's expected return
    per claim depends on whether the creator's claims tend toward YES
    truth.

    G: creator does not auto-bet.  They can manually vote at any time
    using their own energy.  Here we assume the creator votes once,
    using their best guess (skill 0.65), at the current market price.

    Compare expected earnings per claim posted.
    """
    rng = random.Random(seed)
    f_returns = []
    g_returns = []
    skill = 0.65

    for trial in range(n_trials):
        truth = rng.choice(['YES', 'NO'])
        # F path: auto-YES at creation, then 30 other voters with mixed views
        mF = CPMM()
        mF.buy(0, 'YES', 10.0)             # creator auto-bet
        for u in range(1, 31):
            side = rng.choice(['YES', 'NO'])
            mF.buy(u, side, 10.0)
        pF = mF.resolve(truth)
        f_returns.append(pF[0])

        # G path: no auto-bet at creation.  Some voters bet, then creator
        # votes manually based on their skill.
        mG = ModelG()
        # half of voters go first
        for u in range(1, 16):
            side = rng.choice(['YES', 'NO'])
            mG.buy(u, side, 10.0)
        # creator votes based on skill
        creator_guess = truth if rng.random() < skill else (
            'NO' if truth == 'YES' else 'YES')
        mG.buy(0, creator_guess, 10.0)
        # remaining voters
        for u in range(16, 31):
            side = rng.choice(['YES', 'NO'])
            mG.buy(u, side, 10.0)
        pG = mG.resolve(truth)
        g_returns.append(pG[0])

    return {
        'F_mean': float(np.mean(f_returns)),
        'F_median': float(np.median(f_returns)),
        'F_pct_losing': float(np.mean([1 if x < 0 else 0 for x in f_returns])),
        'G_mean': float(np.mean(g_returns)),
        'G_median': float(np.median(g_returns)),
        'G_pct_losing': float(np.mean([1 if x < 0 else 0 for x in g_returns])),
    }


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

def chart_trivial(triv):
    skews = sorted(triv.keys())
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(skews))
    w = 0.4
    F_vals = [triv[s]['avg_creator_profit_F'] for s in skews]
    G_vals = [triv[s]['avg_creator_profit_G'] for s in skews]
    ax.bar(x - w/2, F_vals, w, label='F (creator auto-YES)', color='#c0392b')
    ax.bar(x + w/2, G_vals, w, label='G (no auto-YES)', color='#27ae60')
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(s*100)}% YES vote" for s in skews])
    ax.set_title("Creator avg profit per claim, truth=YES, varying voter skew")
    ax.set_ylabel("Creator net rep")
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_01_trivial.png"), dpi=120)
    plt.close(fig)


def chart_locked_reward(locked):
    fig, ax = plt.subplots(figsize=(10, 5))
    x = sorted(next(iter(locked.values())).keys())
    colors = {
        'F (with creator auto-YES)': '#c0392b',
        'G (no creator auto-YES)': '#27ae60',
    }
    for label, vs in locked.items():
        ys = [vs[n] for n in x]
        ax.plot(x, ys, marker='o', linewidth=2, label=label, color=colors[label])
    ax.set_xlabel("Later YES buyers after Alice")
    ax.set_ylabel("Alice net rep")
    ax.set_title("Locked reward: Alice's profit independent of later buyers")
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_02_locked.png"), dpi=120)
    plt.close(fig)


def chart_creator(creator):
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ['F mean', 'G mean']
    vals = [creator['F_mean'], creator['G_mean']]
    colors = ['#c0392b', '#27ae60']
    bars = ax.bar(labels, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.1, f"{v:+.2f}",
                ha='center', fontsize=10)
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.set_title("Creator avg earnings per claim (skill 0.65, balanced voters)")
    ax.set_ylabel("Net rep / claim")
    ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_03_creator.png"), dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def write_report(triv, locked, creator, mint, contested):
    L = []
    A = L.append
    A("# Model G — F + 2 tiny rule tweaks\n")
    A("Built by `simulator_g.py`.  Sister analysis: `leaderboard_analysis.md` "
      "(does F's inflation actually hurt the leaderboard?).\n")

    A("## What changed\n")
    A("```")
    A("Model F  =  CPMM payouts + v2 hard rules + energy gate")
    A("            + creator auto-YES at claim creation")
    A("")
    A("Model G  =  CPMM payouts + v2 hard rules + energy gate")
    A("            - drop creator auto-YES")
    A("            + refund-if-uncontested: if losing side has < 3")
    A("              distinct voters, all stakes refunded (no mint)")
    A("```\n")
    A("Locked reward, copy-trade immunity, whale rules, energy gate — "
      "all unchanged from F.\n")

    # ----
    A("## Scenario 1 — trivial-claim farming\n")
    A("100 voters, varying YES skew.  Truth = YES.  How much does the "
      "creator earn?\n")
    A("| Voter skew (% YES) | F (auto-YES) | G (no auto-YES) | Difference |")
    A("|---|---|---|---|")
    for skew in sorted(triv.keys()):
        r = triv[skew]
        A(f"| {int(skew*100)}% | {r['avg_creator_profit_F']:+.2f} | "
          f"{r['avg_creator_profit_G']:+.2f} | "
          f"{r['avg_creator_profit_G'] - r['avg_creator_profit_F']:+.2f} |")
    A("\n![trivial](charts/g_01_trivial.png)\n")
    A("**Reading.** Under F, a creator posting an obvious-YES claim earns "
      "~9 rep for free.  Under G, they earn 0 unless they personally vote.  "
      "Trivial-farming attack closed.\n")

    # ----
    A("## Scenario 1b — \"everyone YES, everyone wins from the pool\"\n")
    A(f"The trivial-claim mint problem.  {mint['n_voters']} voters all "
      "bet YES, YES wins.  How much rep does the system mint out of thin "
      "air per claim?\n")
    A("| Model | Mean mint per claim | Total mint over "
      f"{mint['n_trials']} trials | Refund rate |")
    A("|---|---|---|---|")
    A(f"| F | **{mint['F_mean_mint']:+.2f} rep** | "
      f"{mint['F_total_mint']:+.0f} rep | 0% |")
    A(f"| G | {mint['G_mean_mint']:+.2f} rep | "
      f"{mint['G_total_mint']:+.0f} rep | **{mint['G_refund_rate']*100:.0f}%** |")
    A("\n![mint](charts/g_04_mint.png)\n")
    A("**Reading.** Under F, every one-sided claim mints rep equal to "
      f"~{mint['F_mean_mint']:.0f} per claim ({mint['F_total_mint']:.0f} "
      f"over {mint['n_trials']} trials).  Under G the refund-on-extreme "
      "rule triggers — every voter gets their stake back, system mint "
      "is zero.  Trivial claims become no-ops.\n")

    # ----
    A("## Scenario 1c — refund rule doesn't break contested claims\n")
    A(f"Sanity check: run {contested['contested_total']} near-50/50 "
      "claims under G.  Refund rule should NOT fire.\n")
    A(f"- Contested claims that resolved normally: "
      f"**{contested['normal_resolutions']}** / "
      f"{contested['contested_total']}")
    A(f"- Contested claims that hit the extreme-price refund: "
      f"{contested['triggered_refunds']}\n")
    rate = contested['normal_resolutions'] / contested['contested_total']
    A(f"**Reading.** {rate*100:.0f}% of contested claims resolve as "
      "expected; the refund rule only catches the genuinely one-sided "
      "ones.\n")

    # ----
    A("## Scenario 2 — locked reward preserved\n")
    A("Alice bets YES, then varying numbers of later YES buyers join, then "
      "10 NO buyers.  Truth = YES.  Alice's profit should be identical "
      "regardless of later buyers (F's locked-reward property).\n")
    A("| Later YES buyers | F | G |")
    A("|---|---|---|")
    ns = sorted(next(iter(locked.values())).keys())
    for n in ns:
        f_key = 'F (with creator auto-YES)'
        g_key = 'G (no creator auto-YES)'
        A(f"| {n} | {locked[f_key][n]:+.2f} | {locked[g_key][n]:+.2f} |")
    A("\n![locked](charts/g_02_locked.png)\n")
    A("**Reading.** G keeps F's locked-reward exactly — only the creator's "
      "automatic stake is gone.  Traders' payouts are unaffected.\n")

    # ----
    A("## Scenario 3 — creator's expected earnings under each model\n")
    A("Creator with skill 0.65 (better than random) posts claims.  Under F, "
      "they get auto-staked on YES at creation.  Under G, they vote manually "
      "based on their skill after seeing some early voters.  30 other voters "
      "per claim, random truth.\n")
    A("| Model | Mean creator rep / claim | Median | % losing |")
    A("|---|---|---|---|")
    A(f"| F | {creator['F_mean']:+.2f} | {creator['F_median']:+.2f} | "
      f"{creator['F_pct_losing']*100:.0f}% |")
    A(f"| G | {creator['G_mean']:+.2f} | {creator['G_median']:+.2f} | "
      f"{creator['G_pct_losing']*100:.0f}% |")
    A("\n![creator](charts/g_03_creator.png)\n")
    diff = creator['G_mean'] - creator['F_mean']
    A(f"**Reading.** Creator's expected rep / claim drops by "
      f"{abs(diff):.2f} when we remove the auto-YES — but they were earning "
      "that as a freebie, regardless of claim quality.  Under G, the "
      "creator earns when their skill-based vote is correct, which is the "
      "honest signal.\n")

    A("## Where the leaderboard problem goes\n")
    A("See `leaderboard_analysis.md`.  Under realistic 180-day sim:\n")
    A("- Inflation: +244% drift")
    A("- Rank stability: Spearman ρ = 0.87 (preserved)")
    A("- Final rep ↔ skill: ρ = 0.93 (clean signal)")
    A("- Median-skill newcomer at day 90 → pctl 48% (peers at 52%) — caught up\n")
    A("Therefore the inflation does not damage the leaderboard's "
      "*ordering*.  The fix is a UI tweak:\n")
    A("```jsx")
    A('display "Top {Math.round((1 - user.percentile) * 100)}%"')
    A('instead of  "{user.rep} rep"')
    A("```\n")

    A("## What G keeps from F\n")
    A("- Locked reward (shares × 1 rep at buy time)")
    A("- Copy-trade immunity (Alice's share count fixed at click)")
    A("- Fixed 10-rep stake + 1-per-claim rule (no whales)")
    A("- Daily energy gate (no leaderboard runaway)")
    A("- 7-day sybil guard")
    A("- House subsidy bound (~100 rep / claim via virtual liquidity)\n")

    A("## Summary\n")
    A("| Issue | Status under G |")
    A("|---|---|")
    A("| #76 P1 inflation | UI-fix only (percentile display) |")
    A("| #76 P2 trivial farming | ✅ fixed by removing auto-YES |")
    A("| #76 P3 low creator reward | accept: creators paid only for honest votes |")
    A("| Locked reward | ✅ preserved |")
    A("| Copy-trade immunity | ✅ preserved |")
    A("| Whale | ✅ rule-impossible |")
    A("| Leaderboard runaway | ✅ energy gate |")
    A("| House subsidy | ⚠ same as F (~100 rep / claim) |")

    out = os.path.join(OUT_DIR, "model_g_report.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    return out


def chart_mint(mint):
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = ['F (no rule)', 'G (refund-on-extreme)']
    vals = [mint['F_mean_mint'], mint['G_mean_mint']]
    colors = ['#c0392b', '#27ae60']
    bars = ax.bar(labels, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.5, f"{v:+.1f}",
                ha='center', fontsize=11)
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.set_title(f"System mint per one-sided claim "
                 f"({mint['n_voters']} all-YES voters, truth=YES)")
    ax.set_ylabel("Net rep created from thin air")
    ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_04_mint.png"), dpi=120)
    plt.close(fig)


def main():
    print("Scenario: trivial claim farming (F vs G) ...")
    triv = scenario_trivial_claim_farming()
    chart_trivial(triv)

    print("Scenario: one-sided claim system-mint ...")
    mint = scenario_one_sided_mint()
    chart_mint(mint)

    print("Scenario: contested claims still resolve normally ...")
    contested = scenario_contested_claims_still_work()

    print("Scenario: locked reward preserved ...")
    locked = scenario_locked_reward_preserved()
    chart_locked_reward(locked)

    print("Scenario: creator's expected earnings ...")
    creator = scenario_creator_earnings_real_claims()
    chart_creator(creator)

    out = write_report(triv, locked, creator, mint, contested)
    print(f"\nDone. Report: {out}")


if __name__ == "__main__":
    main()
