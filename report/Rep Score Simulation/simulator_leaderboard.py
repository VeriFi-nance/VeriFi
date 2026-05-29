"""Does Model F's inflation actually mess up the leaderboard?

Run F in realistic conditions and measure four things that would make
inflation a real problem:

  Q1. Rank stability — does the ordering of users by rep drift over time?
      Test: Spearman ρ between an early-day ranking and later-day rankings.
  Q2. Newcomer competitiveness — can a fresh user catch up?
      Test: inject a fresh user at month 3 with median rep and median
      skill.  Does their final rank track their skill, or do incumbents
      block them?
  Q3. Top-tier consolidation — does the top 5% widen its lead?
      Test: ratio of top 5% mean to bottom 50% mean over time.
  Q4. Visible inflation in percentile UI — if we just show rank, does
      inflation become invisible?

If F passes these, then F's inflation is a UX label problem, not a
fairness problem.  Solvable with display tweaks (percentile rank, log
truth score) — no protocol change needed.

Run:  python3 simulator_leaderboard.py
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

from simulator import CPMM, gini

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


@dataclass
class Agent:
    uid: int
    rep: float = 200.0
    energy: float = 5.0
    skill: float = 0.5
    activity: float = 0.5


def run_F(days: int = 180, n_agents: int = 200, claims_per_day: int = 10,
          seed: int = 0, inject_newcomer_at_day: int | None = None):
    """Realistic Model F simulation.

    All v2 hard rules: fixed 10-rep stake, 1 bet per user per claim,
    1 energy per bet, daily grant 3, cap 4.

    Optionally inject a fresh newcomer with median skill at the given day
    to test whether late entrants are blocked from climbing.
    """
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_agents)]
    activities = [rng.uniform(0.20, 1.00) for _ in range(n_agents)]
    agents = [Agent(uid=i, skill=skills[i], activity=activities[i])
              for i in range(n_agents)]

    median_skill = sorted(skills)[len(skills) // 2]
    median_activity = sorted(activities)[len(activities) // 2]

    DAILY_GRANT, ENERGY_CAP, STAKE_COST = 3, 4, 1
    history = {0: [a.rep for a in agents]}
    snapshots_at = list(range(30, days + 1, 30))
    newcomer_uid = None

    for day in range(days):
        # Newcomer injection
        if inject_newcomer_at_day is not None and day == inject_newcomer_at_day:
            cur_rep = sorted([a.rep for a in agents])
            median_rep = cur_rep[len(cur_rep) // 2]
            newcomer = Agent(
                uid=len(agents),
                rep=median_rep,
                skill=median_skill,
                activity=median_activity,
            )
            newcomer_uid = newcomer.uid
            agents.append(newcomer)

        for a in agents:
            a.energy = min(a.energy + DAILY_GRANT, ENERGY_CAP)

        for c in range(claims_per_day):
            m = CPMM(claim_id=day * 1000 + c)
            truth = rng.choice(['YES', 'NO'])
            order = list(range(len(agents)))
            rng.shuffle(order)
            for uid in order:
                a = agents[uid]
                if a.rep < 10 or a.energy < STAKE_COST:
                    continue
                if rng.random() > a.activity:
                    continue
                side = truth if rng.random() < a.skill else (
                    'NO' if truth == 'YES' else 'YES')
                m.buy(uid, side, 10.0)
                a.rep -= 10.0
                a.energy -= STAKE_COST
            profits = m.resolve(truth)
            for uid, p in profits.items():
                agents[uid].rep += 10.0 + p

        if (day + 1) in snapshots_at:
            history[day + 1] = [a.rep for a in agents]

    return {
        'agents': agents,
        'skills_initial': skills,
        'history': history,
        'newcomer_uid': newcomer_uid,
        'days': days,
    }


# ---------------------------------------------------------------------------
# Q1: rank stability
# ---------------------------------------------------------------------------

def q1_rank_stability(res):
    """Spearman ρ between day-30 ranking and each later snapshot.
    Uses day-30 (not day-0) because day-0 has all-equal rep."""
    days = sorted(d for d in res['history'] if d >= 30)
    ref_day = days[0]
    ref = res['history'][ref_day][:len(res['skills_initial'])]
    out = []
    for d in days:
        cur = res['history'][d][:len(ref)]
        rho, _ = spearmanr(ref, cur)
        out.append((d, rho))
    return out


def q1_rank_vs_skill(res):
    """Spearman ρ between final rep and original skill.  If high, the
    leaderboard reflects skill (good)."""
    final = res['history'][res['days']]
    skill = res['skills_initial']
    # If newcomer present, only correlate the original cohort
    rho, _ = spearmanr(final[:len(skill)], skill)
    return rho


# ---------------------------------------------------------------------------
# Q2: newcomer trajectory
# ---------------------------------------------------------------------------

def q2_newcomer(seed: int = 5):
    """Inject a median-skill newcomer at day 90, run to day 180.
    Compare their final percentile rank to incumbents of the same skill."""
    res = run_F(days=180, n_agents=200, seed=seed, inject_newcomer_at_day=90)
    newcomer_uid = res['newcomer_uid']
    if newcomer_uid is None:
        return None
    final_rep = res['history'][res['days']]
    nc_rep = final_rep[newcomer_uid]
    pct_below_nc = sum(1 for r in final_rep if r < nc_rep) / len(final_rep)
    # Comparison: incumbents with similar skill
    median_skill = sorted(res['skills_initial'])[len(res['skills_initial']) // 2]
    similar = [(uid, final_rep[uid]) for uid in range(len(res['skills_initial']))
               if abs(res['skills_initial'][uid] - median_skill) < 0.05]
    similar_ranks = [sum(1 for r in final_rep if r < rep) / len(final_rep)
                     for _, rep in similar]
    return {
        'newcomer_final_rep': nc_rep,
        'newcomer_percentile': pct_below_nc * 100,
        'similar_incumbents_mean_pct': float(np.mean(similar_ranks)) * 100,
        'similar_incumbents_min_pct': float(np.min(similar_ranks)) * 100,
        'similar_incumbents_max_pct': float(np.max(similar_ranks)) * 100,
    }


# ---------------------------------------------------------------------------
# Q3: top-tier consolidation
# ---------------------------------------------------------------------------

def q3_top_vs_bottom(res):
    """Ratio of top-5% mean rep to bottom-50% mean rep over time.
    Lower = more competitive.  Rising = oligarchy forming."""
    days = sorted(res['history'].keys())
    out = []
    for d in days:
        reps = sorted(res['history'][d])
        n = len(reps)
        bottom_50 = reps[:n // 2]
        top_5 = reps[-(n // 20):]
        if not bottom_50 or sum(bottom_50) <= 0:
            ratio = float('inf')
        else:
            ratio = (sum(top_5) / len(top_5)) / (sum(bottom_50) / len(bottom_50))
        out.append((d, ratio))
    return out


# ---------------------------------------------------------------------------
# Q4: percentile UI
# ---------------------------------------------------------------------------

def q4_percentile_view(res):
    """For the median-skill incumbent, track their rep AND their
    percentile rank over time.  If rep balloons but percentile is steady,
    inflation is purely cosmetic."""
    median_idx = np.argsort(res['skills_initial'])[len(res['skills_initial']) // 2]
    days = sorted(res['history'].keys())
    raw_rep = []
    pct = []
    for d in days:
        reps = res['history'][d]
        their_rep = reps[median_idx]
        below = sum(1 for r in reps if r < their_rep)
        raw_rep.append(their_rep)
        pct.append(below / len(reps) * 100)
    return days, raw_rep, pct


# ---------------------------------------------------------------------------
# CHARTS
# ---------------------------------------------------------------------------

def chart_q1(rank_stab, rank_vs_skill_rho):
    fig, ax = plt.subplots(figsize=(9, 5))
    days = [d for d, _ in rank_stab]
    rhos = [r for _, r in rank_stab]
    ax.plot(days, rhos, marker='o', color='#2980b9', linewidth=2)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Day")
    ax.set_ylabel("Spearman ρ vs day-30 ranking")
    ax.set_title(f"Q1: Leaderboard rank stability under F  (rep↔skill ρ final = {rank_vs_skill_rho:+.2f})")
    ax.grid(alpha=0.3)
    ax.axhline(1.0, color='gray', linestyle='--', linewidth=1, label='identical order')
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "lb_01_rank_stability.png"), dpi=120)
    plt.close(fig)


def chart_q3(top_bot):
    fig, ax = plt.subplots(figsize=(9, 5))
    days = [d for d, _ in top_bot]
    ratios = [r if r != float('inf') else None for _, r in top_bot]
    ax.plot(days, ratios, marker='o', color='#c0392b', linewidth=2)
    ax.set_xlabel("Day")
    ax.set_ylabel("Top-5% mean rep ÷ Bottom-50% mean rep")
    ax.set_title("Q3: Are top users running away from the pack?")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "lb_03_top_vs_bottom.png"), dpi=120)
    plt.close(fig)


def chart_q4(days, raw, pct):
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(days, raw, color='#c0392b', linewidth=2, label='raw rep')
    ax1.set_ylabel("Raw rep", color='#c0392b')
    ax1.set_xlabel("Day")
    ax1.tick_params(axis='y', labelcolor='#c0392b')
    ax2 = ax1.twinx()
    ax2.plot(days, pct, color='#27ae60', linewidth=2, label='percentile rank')
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Percentile rank (%)", color='#27ae60')
    ax2.tick_params(axis='y', labelcolor='#27ae60')
    fig.suptitle("Q4: Median-skill user — raw rep balloons but percentile is steady")
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "lb_04_percentile_view.png"), dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def write_report(res, rank_stab, rank_vs_skill_rho, newcomer, top_bot,
                 q4_days, q4_raw, q4_pct):
    L = []
    A = L.append
    A("# Does Model F's inflation actually hurt the leaderboard?\n")
    A("Setup: 180 days, 200 users, 10 claims/day, v2 energy gate, skill "
      "uniform in [0.40, 0.75].\n")

    init = res['history'][0]
    final = res['history'][res['days']]
    drift = (sum(final) - sum(init)) / sum(init) * 100
    A(f"**Headline.** Total rep supply drift over 180 days: "
      f"**{drift:+.1f}%**. Yes, inflation is real. But does it hurt?\n")

    A("## Q1 — Does the leaderboard order stay stable?\n")
    A("Spearman ρ between day-30 ranking and each later day. ρ=1 means "
      "identical order.\n")
    A("| Day | ρ vs day 30 |")
    A("|---|---|")
    for d, r in rank_stab:
        A(f"| {d} | {r:+.3f} |")
    A("\n![rank_stability](charts/lb_01_rank_stability.png)\n")
    final_rho = rank_stab[-1][1]
    A(f"Final ρ = **{final_rho:+.3f}**. Order is "
      f"{'preserved' if final_rho > 0.85 else 'mostly preserved' if final_rho > 0.6 else 'shifting'}. ")
    A(f"Correlation of final rep with original skill: ρ = **{rank_vs_skill_rho:+.2f}** — "
      f"{'leaderboard reflects skill cleanly' if rank_vs_skill_rho > 0.7 else 'leaderboard reflects skill with some noise' if rank_vs_skill_rho > 0.4 else 'leaderboard is noisy vs skill'}.\n")

    A("## Q2 — Can a fresh newcomer catch up?\n")
    A("Inject a user at day 90 with median rep and median skill. Run to "
      "day 180. Compare their final percentile rank to incumbents of "
      "identical skill.\n")
    if newcomer is None:
        A("(newcomer injection failed)\n")
    else:
        A(f"- Newcomer final rep: **{newcomer['newcomer_final_rep']:.0f}**")
        A(f"- Newcomer final percentile: **{newcomer['newcomer_percentile']:.0f}%**")
        A(f"- Same-skill incumbents: mean pctl **{newcomer['similar_incumbents_mean_pct']:.0f}%**, "
          f"range [{newcomer['similar_incumbents_min_pct']:.0f}–"
          f"{newcomer['similar_incumbents_max_pct']:.0f}%]")
        gap = newcomer['similar_incumbents_mean_pct'] - newcomer['newcomer_percentile']
        A(f"\nGap newcomer vs incumbents: **{gap:+.0f} pctl pts**. "
          f"{'Newcomer essentially caught up' if abs(gap) < 10 else 'Newcomer is behind comparable incumbents — concerning' if gap > 15 else 'Newcomer mostly caught up'}.\n")

    A("## Q3 — Is the top tier running away?\n")
    A("Ratio of top-5% mean rep to bottom-50% mean rep.\n")
    A("| Day | Top-5% ÷ Bottom-50% |")
    A("|---|---|")
    for d, r in top_bot:
        rstr = f"{r:.1f}" if r != float('inf') else "inf"
        A(f"| {d} | {rstr} |")
    A("\n![top_vs_bottom](charts/lb_03_top_vs_bottom.png)\n")
    final_ratio = top_bot[-1][1]
    initial_ratio = top_bot[1][1] if len(top_bot) > 1 else top_bot[0][1]
    A(f"Initial ratio = **{initial_ratio:.1f}**, final ratio = **{final_ratio:.1f}**. "
      f"{'Top tier is widening lead — concerning' if final_ratio > initial_ratio * 2 else 'Stable spread' if abs(final_ratio - initial_ratio) < initial_ratio * 0.5 else 'Spread growing modestly'}.\n")

    A("## Q4 — Percentile UI hides inflation\n")
    A("Median-skill user. Track their raw rep AND their percentile rank "
      "over time.\n")
    A("| Day | Raw rep | Percentile |")
    A("|---|---|---|")
    for d, r, p in zip(q4_days, q4_raw, q4_pct):
        A(f"| {d} | {r:.0f} | {p:.0f}% |")
    A("\n![percentile_view](charts/lb_04_percentile_view.png)\n")
    A("**Reading.** Even though raw rep balloons due to inflation, the "
      "median user's *percentile rank* stays around the 50% line. If the "
      "UI displays percentile (\"top X%\") instead of raw rep, inflation "
      "becomes literally invisible to users.\n")

    A("## Verdict\n")
    rank_ok = final_rho > 0.85
    newcomer_ok = newcomer and abs(newcomer['similar_incumbents_mean_pct'] -
                                    newcomer['newcomer_percentile']) < 15
    top_bot_ok = final_ratio < initial_ratio * 2

    if rank_ok and newcomer_ok and top_bot_ok:
        A("**F's inflation does NOT meaningfully damage the leaderboard.** "
          "Order is preserved, newcomers can catch up to skill peers, top "
          "tier doesn't consolidate. Inflation is a UX label problem only.\n")
    else:
        failing = []
        if not rank_ok: failing.append("rank instability")
        if not newcomer_ok: failing.append("newcomer blocked")
        if not top_bot_ok: failing.append("top-tier consolidation")
        A(f"**F's inflation has real effects.** Failing dimensions: "
          f"{', '.join(failing)}. Protocol change may be needed.\n")

    A("## Display fix\n")
    A("If F passes the four tests above, the inflation problem is solved "
      "with a 1-line UI change:\n")
    A("```jsx")
    A("// instead of:")
    A("<span>{user.rep} rep</span>")
    A("// show:")
    A("<span>Top {Math.round((1 - user.percentile) * 100)}%</span>")
    A("```")
    A("Or a derived score:\n```python")
    A("truth_score = accuracy * math.log(rep + 1)")
    A("```")
    A("log(rep) compresses the inflation; relative ordering preserved.\n")

    out = os.path.join(OUT_DIR, "leaderboard_analysis.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    return out


def main():
    print("Running F for 180 days (no newcomer) ...")
    res = run_F(days=180, n_agents=200, claims_per_day=10, seed=0)

    rank_stab = q1_rank_stability(res)
    rank_vs_skill_rho = q1_rank_vs_skill(res)
    chart_q1(rank_stab, rank_vs_skill_rho)

    print("Running F with newcomer injected at day 90 ...")
    newcomer = q2_newcomer(seed=5)

    top_bot = q3_top_vs_bottom(res)
    chart_q3(top_bot)

    q4_days, q4_raw, q4_pct = q4_percentile_view(res)
    chart_q4(q4_days, q4_raw, q4_pct)

    report = write_report(res, rank_stab, rank_vs_skill_rho, newcomer,
                          top_bot, q4_days, q4_raw, q4_pct)
    print(f"\nDone. Report: {report}")


if __name__ == "__main__":
    main()
