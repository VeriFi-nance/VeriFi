"""Is Model F's inflation actually a problem?

Test in realistic conditions, not the synthetic 400-round stress test. Look
at four things that would make inflation "bad":

  Q1. Rate — is it fast enough to notice month-over-month?
  Q2. Uniformity — does inflation flow disproportionately to top users
      (concentrating power) or roughly equally (just rescaling)?
  Q3. Rank stability — does the leaderboard order stay the same under
      inflation (i.e. is it just a units change)?
  Q4. Threshold drift — does the meaning of "good rep score" move so fast
      that newcomers can never catch up?

If inflation is slow, uniform, rank-preserving, and bounded relative to
honest activity, it's a UX label problem, not a fairness problem.

Run:  python3 simulator_inflation.py
Output:  charts/infl_*.png  +  inflation_analysis.md
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

from simulator import CPMM, gini
from simulator_g import ModelG

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


def run(days: int = 180, n_agents: int = 200, claims_per_day: int = 10,
        seed: int = 0, model: str = "F", init_L: float = 100.0):
    """Realistic Model F simulation.

    Hard rules (v2 spec): fixed 10-rep stake, 1 bet per user per claim,
    1 energy per bet, 3 daily energy grant, cap 4.
    """
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_agents)]
    activities = [rng.uniform(0.20, 1.00) for _ in range(n_agents)]
    agents = [Agent(uid=i, skill=skills[i], activity=activities[i])
              for i in range(n_agents)]

    DAILY_GRANT, ENERGY_CAP, STAKE_COST = 3, 4, 1
    history_supply = [sum(a.rep for a in agents)]
    history_top = []
    history_median = []
    history_bottom = []
    history_gini = []
    rep_at_day = {0: [a.rep for a in agents]}

    for day in range(days):
        for a in agents:
            a.energy = min(a.energy + DAILY_GRANT, ENERGY_CAP)

        for c in range(claims_per_day):
            if model == "F":
                m = CPMM(claim_id=day * 1000 + c)
            else:
                m = ModelG(claim_id=day * 1000 + c, creator_uid=0)
            # Tunable virtual liquidity. Smaller = less house subsidy/mint.
            m.y_reserve = init_L
            m.n_reserve = init_L
            truth = rng.choice(['YES', 'NO'])
            order = list(range(n_agents))
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

        sorted_rep = sorted([a.rep for a in agents])
        history_supply.append(sum(sorted_rep))
        history_top.append(np.percentile(sorted_rep, 95))
        history_median.append(np.percentile(sorted_rep, 50))
        history_bottom.append(np.percentile(sorted_rep, 5))
        history_gini.append(gini([a.rep for a in agents]))
        if (day + 1) % 30 == 0:
            rep_at_day[day + 1] = [a.rep for a in agents]

    return {
        'agents': agents, 'skills': skills,
        'supply': history_supply, 'top': history_top,
        'median': history_median, 'bottom': history_bottom,
        'gini': history_gini, 'snapshots': rep_at_day, 'days': days,
    }


def rank_correlation_over_time(snapshots: dict, ref_day: int = 30):
    """Spearman rho between ranking at ``ref_day`` (first day with variance)
    and each later day.  Day-0 is skipped because all users start at the
    same rep and the correlation is undefined."""
    days = sorted(d for d in snapshots.keys() if d >= ref_day)
    if not days:
        return []
    ref = snapshots[days[0]]
    return [(d, spearmanr(ref, snapshots[d]).correlation) for d in days]


def skill_vs_inflation(agents, days):
    """Per-skill-tier final rep / initial rep ratio."""
    buckets = {}
    for a in agents:
        bucket = round(a.skill * 10) / 10
        buckets.setdefault(bucket, []).append(a.rep / 200.0)
    return sorted(buckets.items())


def chart_supply(res, out_name):
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(len(res['supply']))
    ax.plot(xs, res['supply'], color='#c0392b', linewidth=2, label='total supply')
    init = res['supply'][0]
    ax.axhline(init, color='gray', linestyle='--', linewidth=1, label=f'initial ({init:.0f})')
    growth = (res['supply'][-1] - init) / init * 100
    ax.set_title(f"F supply over {res['days']} days  (final drift {growth:+.1f}%)")
    ax.set_xlabel("Day"); ax.set_ylabel("Total rep")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def chart_percentiles(res, out_name):
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(1, len(res['top']) + 1)
    ax.plot(xs, res['top'], label='95th pct', color='#27ae60', linewidth=2)
    ax.plot(xs, res['median'], label='median', color='#2980b9', linewidth=2)
    ax.plot(xs, res['bottom'], label='5th pct', color='#c0392b', linewidth=2)
    ax.set_title("Rep percentile trajectories under F")
    ax.set_xlabel("Day"); ax.set_ylabel("Rep")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def chart_distribution(res, out_name):
    fig, ax = plt.subplots(figsize=(10, 5))
    snap = res['snapshots']
    days = sorted(snap.keys())
    bins = np.linspace(0, max(max(snap[d]) for d in days) + 50, 40)
    colors = plt.cm.viridis(np.linspace(0, 1, len(days)))
    for d, c in zip(days, colors):
        ax.hist(snap[d], bins=bins, alpha=0.45, label=f"day {d}", color=c)
    ax.set_title("Rep distribution snapshots over time (F)")
    ax.set_xlabel("Rep"); ax.set_ylabel("Users")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def chart_rank_stability(rc, out_name):
    fig, ax = plt.subplots(figsize=(8, 5))
    days = [d for d, _ in rc]; cors = [c for _, c in rc]
    ax.plot(days, cors, marker='o', color='#2980b9', linewidth=2)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Leaderboard rank stability vs day 0  (Spearman ρ)")
    ax.set_xlabel("Day"); ax.set_ylabel("ρ (1 = identical order)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def chart_skill_buckets(buckets, out_name):
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = [k for k, _ in buckets]
    means = [np.mean(v) for _, v in buckets]
    ax.bar([f"{k:.1f}" for k in xs], means, color='#16a085')
    ax.axhline(1.0, color='gray', linestyle='--', linewidth=1, label='break-even')
    ax.set_title("Final rep / initial rep, bucketed by skill")
    ax.set_xlabel("Skill bucket (P(correct))"); ax.set_ylabel("rep_final / rep_init")
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def write_report(res, rc, buckets, drift_F_small: float = 0.0,
                 drift_G: float = 0.0):
    L = []
    A = L.append
    days = res['days']
    init = res['supply'][0]
    final = res['supply'][-1]
    drift = (final - init) / init * 100
    daily_rate = (final / init) ** (1.0 / days) - 1
    monthly_rate = (1 + daily_rate) ** 30 - 1

    A("# Is Model F's inflation a problem in practice?\n")
    A("Built by `simulator_inflation.py`. Realistic conditions: "
      f"{res['days']} days, {len(res['agents'])} users, 10 claims/day, "
      "energy gate active (3 grant, cap 4), random skill in [0.40, 0.75], "
      "random activity in [0.20, 1.00].\n")

    A("## Headline numbers\n")
    A(f"- Total supply (F, INIT_L=100): **{init:.0f} → {final:.0f}**  "
      f"(drift **{drift:+.1f}%** over {days} days)")
    A(f"- Same conditions, F with INIT_L=10 (smaller subsidy): "
      f"drift **{drift_F_small:+.1f}%**")
    A(f"- Same conditions, G (zero-sum): drift **{drift_G:+.1f}%**")
    A(f"- Implied daily inflation rate: **{daily_rate*100:.3f}%/day**")
    A(f"- Equivalent monthly: **{monthly_rate*100:.2f}%/mo**")
    A(f"- Equivalent annualised: **{((1+daily_rate)**365 - 1)*100:.1f}%/yr**\n")
    A("![supply](charts/infl_01_supply.png)\n")

    A("## Q1 — Is the rate fast enough to notice?\n")
    A(f"At {monthly_rate*100:.2f}%/mo … by analogy, USD inflation runs "
      f"~0.2–0.4%/mo (2024). VeriFi is {'within that range' if monthly_rate < 0.005 else 'much higher' if monthly_rate > 0.02 else 'noticeable but not extreme'}. "
      "Users who log in monthly will see their balance grow even on "
      "break-even play. Whether that's bad depends on Q2-Q4.\n")

    A("## Q2 — Is inflation uniform or concentrated?\n")
    A("Per-skill-tier final/initial rep ratio. If inflation is uniform, all "
      "tiers ride the same multiplier. If it's concentrated, only the top "
      "tier gets the gain.\n")
    A("| Skill bucket | Avg final / initial |")
    A("|---|---|")
    for k, vs in buckets:
        A(f"| {k:.1f} | {np.mean(vs):.2f}× |")
    A("\n![skill_buckets](charts/infl_05_skill_buckets.png)\n")
    spread = max(np.mean(v) for _, v in buckets) - min(np.mean(v) for _, v in buckets)
    A(f"Spread across buckets: **{spread:.2f}×**. "
      f"{'Concentrated — top tier benefits much more' if spread > 1.0 else 'Roughly uniform — inflation flows similarly across skill tiers'}.\n")

    A("## Q3 — Does the leaderboard order stay stable?\n")
    A("Spearman ρ between day-0 ranking and ranking at day d:\n")
    A("| Day | ρ vs day 0 |")
    A("|---|---|")
    for d, c in rc:
        A(f"| {d} | {c:+.3f} |")
    A("\n![rank_stability](charts/infl_04_rank.png)\n")
    final_rho = rc[-1][1]
    A(f"Final ρ = **{final_rho:+.3f}**. "
      f"{'Order is preserved — inflation is just a units change' if final_rho > 0.5 else 'Order changes significantly — inflation is NOT just rescaling, skill-based reshuffling happens'}.\n")

    A("## Q4 — Threshold drift\n")
    init_p50 = res['median'][0] if res['median'] else 200.0
    final_p50 = res['median'][-1]
    final_p95 = res['top'][-1]
    final_p5 = res['bottom'][-1]
    A(f"- Median user: 200 → **{final_p50:.0f}** rep")
    A(f"- 95th percentile: **{final_p95:.0f}**")
    A(f"- 5th percentile: **{final_p5:.0f}**\n")
    A("![percentiles](charts/infl_02_percentiles.png)")
    A("![distribution](charts/infl_03_dist.png)\n")
    A(f"A newcomer joining at day {days} with 200 starting rep sits at the "
      f"{'top quartile' if 200 > final_p50 else 'bottom half' if 200 < final_p50 else 'median'} "
      f"by absolute number. If the UI displays raw rep, this is misleading; "
      "if it displays percentile rank or 'truth score = accuracy×log(rep)', the "
      "absolute drift is irrelevant.\n")

    A("## Verdict\n")
    is_slow = monthly_rate < 0.05
    is_uniform = spread < 1.0
    is_stable = final_rho > 0.5
    n_good = sum([is_slow, is_uniform, is_stable])
    if n_good == 3:
        verdict = "**Tolerable.** Inflation is slow, roughly uniform, and rank-preserving. Display percentile rank or a derived 'truth score' instead of raw rep and the problem disappears."
    elif n_good == 2:
        verdict = "**Mostly tolerable, one rough edge.** Pick a UI workaround for the one failing dimension."
    else:
        verdict = "**Genuinely problematic.** Fix at the protocol level (Model G's zero-sum or a rebase mechanism)."
    A(verdict + "\n")

    A("### Cheap fixes that don't require Model G\n")
    A("- **Percentile display.** Show \"top 12%\" instead of \"3812 rep\". Inflation invisible.")
    A("- **Truth Score = accuracy × log(rep + 1).** log compresses the inflation; relative ordering preserved.")
    A("- **Annual rebase.** Multiply every balance by `target_total / current_total` at midnight on Jan 1. Same as a stock split.")
    A("- **Slow burn fee.** 0.5% of every stake routed to /dev/null instead of pool. Tune to match expected mint.")
    A("- **House sink.** Listing bonuses, sybil-stop deposits, claim-creation fee — all paid from pool, drain inflation.\n")

    out = os.path.join(OUT_DIR, "inflation_analysis.md")
    with open(out, "w") as f:
        f.write("\n".join(L))
    return out


def chart_supply_compare(res_F, res_G, res_F_small, out_name):
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(len(res_F['supply']))
    init = res_F['supply'][0]
    ax.plot(xs, res_F['supply'], label="F (CPMM, INIT_L=100)",
            color='#c0392b', linewidth=2)
    ax.plot(xs, res_F_small['supply'], label="F (CPMM, INIT_L=10)",
            color='#e67e22', linewidth=2)
    ax.plot(xs, res_G['supply'], label="G (zero-sum)",
            color='#27ae60', linewidth=2)
    ax.axhline(init, color='gray', linestyle='--', linewidth=1,
               label=f"initial ({init:.0f})")
    ax.set_title("Total rep supply: F vs G vs F-with-smaller-virtual-liquidity")
    ax.set_xlabel("Day"); ax.set_ylabel("Total rep")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, out_name), dpi=120)
    plt.close(fig)


def main():
    print("Simulating 180 days, Model F (INIT_L=100) ...")
    res_F = run(days=180, n_agents=200, claims_per_day=10, seed=0,
                model="F", init_L=100.0)
    print("Simulating 180 days, Model F (INIT_L=10) — smaller subsidy ...")
    res_F_small = run(days=180, n_agents=200, claims_per_day=10, seed=0,
                      model="F", init_L=10.0)
    print("Simulating 180 days, Model G (zero-sum baseline) ...")
    res_G = run(days=180, n_agents=200, claims_per_day=10, seed=0,
                model="G", init_L=100.0)

    chart_supply(res_F, "infl_01_supply.png")
    chart_supply_compare(res_F, res_G, res_F_small, "infl_06_compare.png")
    chart_percentiles(res_F, "infl_02_percentiles.png")
    chart_distribution(res_F, "infl_03_dist.png")

    rc = rank_correlation_over_time(res_F['snapshots'])
    chart_rank_stability(rc, "infl_04_rank.png")

    buckets = skill_vs_inflation(res_F['agents'], res_F['days'])
    chart_skill_buckets(buckets, "infl_05_skill_buckets.png")

    # Smaller-INIT_L F drift for the report
    drift_small = (res_F_small['supply'][-1] - res_F_small['supply'][0]) / \
                  res_F_small['supply'][0] * 100
    drift_G = (res_G['supply'][-1] - res_G['supply'][0]) / \
              res_G['supply'][0] * 100

    report = write_report(res_F, rc, buckets,
                          drift_F_small=drift_small, drift_G=drift_G)
    print(f"Done. Report: {report}")
    print(f"Charts: {CHART_DIR}/infl_*.png")


if __name__ == "__main__":
    main()
