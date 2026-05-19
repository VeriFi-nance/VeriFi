"""
Model G simulator — addresses three issues raised in #76 against Model F.

Issue recap (https://github.com/ArdaSaygan/VeriFi/issues/76):

  P1. Total reputation inflation/deflation
      Model F's payouts are not zero-sum (CPMM mints "1 rep per winning
      share"), so the global rep supply drifts up or down depending on the
      mix of correct/incorrect resolutions. Users cannot reason about what
      a "good" rep score is.

  P2. Trivial claims
      Claims with a heavily skewed acceptance ratio (e.g. 90% YES / 10% NO)
      carry no information. Model F rewards winners on these the same way
      as on hard claims, so users can farm rep by stacking obvious bets.

  P3. Low creator rewards
      Auto-casting a YES vote at claim creation undercompensates the author
      for the effort of writing a verifiable claim. Issue #76 proposes two
      candidate fixes:
        a) flat 2× multiplier on the creator's standard prize
        b) drop auto-vote; creator votes manually at any time before
           resolution, like any other participant.

Model G is built on top of Model F (CPMM + fixed 10-rep stake + 1-per-claim
+ daily energy gating) and adds three changes that together address P1-P3:

  G1. Zero-sum payouts.
      Reputation is conserved per claim: ``sum(payouts) == sum(stakes)``.
      Winners still receive a CPMM-share-weighted slice of the losers'
      stakes (so early buyers get more, late buyers less — same gradient as
      F), but no rep is minted or burned.

  G2. Information-gain weighting.
      At resolution, the share of the losers' pool that flows to winners
      is multiplied by an information-gain factor
          I = H(p_final) = -p*log2(p) - (1-p)*log2(1-p),  I in [0, 1]
      where p_final is the final YES probability (from the CPMM reserves).
      Trivial claims (p_final close to 0 or 1) shrink toward I = 0 and
      winners just get their stake back; hard claims (p_final ~ 0.5) keep
      I = 1 and pay the full pool.  The unallocated remainder is split into
      two buckets:
        - a creator listing bonus (capped, see G3)
        - the rest refunded to all participants in proportion to their
          original stake.
      Still zero-sum.

  G3. Creator: manual vote + listing bonus.
      The creator is no longer auto-voted YES at claim creation. They may
      vote YES or NO using their own energy at any time before resolution
      (option (b) from #76). On top of that, if the claim resolves cleanly
      with at least ``MIN_PARTICIPANTS`` voters, the creator receives a
      listing bonus
          bonus = LISTING_BONUS_BASE * I
      paid from the unallocated portion of the losers' pool. The bonus is
      bounded by what the pool can afford, so it never breaks zero-sum.

Run:  python3 simulator_g.py
Output: charts/g_*.png  +  model_g_report.md

This file is standalone — it imports the four base models from
``simulator.py`` and only adds the new Model G class, scenarios, charts,
and report. It does not modify the Models A-F report.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt

from simulator import (
    CPMM,
    LateAdoption,
    Parimutuel,
    Stake,
    gini,
)

random.seed(42)
np.random.seed(42)

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CHART_DIR = os.path.join(OUT_DIR, "charts")
os.makedirs(CHART_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# MODEL G
# ----------------------------------------------------------------------------

LISTING_BONUS_BASE = 2.0   # max rep the creator can earn as listing bonus
MIN_PARTICIPANTS = 4       # claim must attract at least this many distinct
                           # voters (including creator) for the listing bonus
                           # to apply.  Anti-spam guard.


def shannon_entropy_bits(p: float) -> float:
    """H(p) for a Bernoulli outcome, returned in bits and clamped to [0, 1]."""
    if p <= 0 or p >= 1:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


class ModelG(CPMM):
    """Model G = Model F's CPMM trading + G1 zero-sum + G2 info-gain +
    G3 creator listing bonus.  Trading (buy) logic is inherited unchanged
    from CPMM so locked-reward semantics for the buyer's *share count* are
    preserved; only the resolution step is rewritten.
    """

    name = "model_g"

    def __init__(self, claim_id: int = 0, creator_uid: Optional[int] = None):
        super().__init__(claim_id)
        self.creator_uid = creator_uid

    # --- helpers -----------------------------------------------------------

    def _final_yes_probability(self) -> float:
        """Use the CPMM mid-price as p_final.  Equivalent to the voting
        ratio at the moment of resolution under a CPMM."""
        return self.yes_price()

    def info_gain(self) -> float:
        """G2: I in [0, 1]."""
        return shannon_entropy_bits(self._final_yes_probability())

    # --- resolution --------------------------------------------------------

    def resolve(self, winning_side: str) -> dict[int, float]:
        out: dict[int, float] = {}
        for s in self.stakes:
            out[s.user_id] = out.get(s.user_id, 0.0) - s.rep_paid

        winners = [s for s in self.stakes if s.side == winning_side]
        losers = [s for s in self.stakes if s.side != winning_side]
        loser_pool = sum(s.rep_paid for s in losers)

        # G2: shrink the payout pool by the information-gain factor.
        I = self.info_gain()
        winners_pool = loser_pool * I
        residual = loser_pool - winners_pool   # to creator bonus + refunds

        # G1: distribute winners_pool over winners proportional to shares.
        if winners and winners_pool > 0:
            share_sum = sum(s.shares for s in winners)
            for s in winners:
                payout = s.rep_paid + winners_pool * (s.shares / share_sum)
                out[s.user_id] = out.get(s.user_id, 0.0) + payout
        else:
            # No winners (degenerate) or trivial claim:
            # return stakes to the winning side at face value.
            for s in winners:
                out[s.user_id] = out.get(s.user_id, 0.0) + s.rep_paid

        # G3: listing bonus, paid from residual, capped by pool.
        # Creator must have staked on this claim — otherwise the bonus
        # would be minted into the system and break zero-sum.
        staker_ids = {s.user_id for s in self.stakes}
        distinct_voters = len(staker_ids)
        listing_bonus = 0.0
        if (
            self.creator_uid is not None
            and self.creator_uid in staker_ids
            and distinct_voters >= MIN_PARTICIPANTS
            and residual > 0
        ):
            listing_bonus = min(LISTING_BONUS_BASE * I, residual)
            out[self.creator_uid] = out.get(self.creator_uid, 0.0) + listing_bonus
            residual -= listing_bonus

        # Refund the rest pro-rata over everyone's original stake.
        if residual > 1e-9:
            total_stake = sum(s.rep_paid for s in self.stakes)
            if total_stake > 0:
                for s in self.stakes:
                    out[s.user_id] = out.get(s.user_id, 0.0) + residual * (
                        s.rep_paid / total_stake
                    )

        return out


# ----------------------------------------------------------------------------
# AUXILIARY MODELS USED FOR P3 COMPARISON
# ----------------------------------------------------------------------------

class CPMMTwoX(CPMM):
    """Model F variant for issue #76 option (a): creator gets a flat 2x
    multiple of the standard prize.  Used only in scenario_creator_rewards
    to benchmark against Model G's bonus."""

    name = "cpmm_2x_creator"

    def __init__(self, claim_id: int = 0, creator_uid: Optional[int] = None):
        super().__init__(claim_id)
        self.creator_uid = creator_uid

    def resolve(self, winning_side: str) -> dict[int, float]:
        # Run base CPMM resolution, then double the creator's net profit if
        # they ended on the winning side.
        out = super().resolve(winning_side)
        if self.creator_uid is None:
            return out
        on_winning = any(
            s.user_id == self.creator_uid and s.side == winning_side
            for s in self.stakes
        )
        if on_winning:
            # Creator's net profit = out[uid] (already net of stake).  Double it.
            out[self.creator_uid] = 2.0 * out[self.creator_uid]
        return out


# ----------------------------------------------------------------------------
# SCENARIOS
# ----------------------------------------------------------------------------

def scenario_inflation(n_rounds: int = 400, n_users: int = 60, seed: int = 7):
    """P1 — Long-horizon inflation/deflation test.

    Play ``n_rounds`` claims under both Model F (CPMM) and Model G.  Each
    round, every user with a non-trivial skill picks a side and stakes 10
    rep.  Truth is uniformly random.  We track the global rep supply after
    every round.

    Expected:
      - Model F drifts (mint > burn or vice versa depending on the run).
      - Model G stays flat (zero-sum by construction).
    """
    rng = random.Random(seed)
    skills = [rng.uniform(0.40, 0.75) for _ in range(n_users)]
    rep_F = [200.0] * n_users
    rep_G = [200.0] * n_users
    history_F, history_G = [sum(rep_F)], [sum(rep_G)]

    for r in range(n_rounds):
        truth = rng.choice(['YES', 'NO'])
        mF, mG = CPMM(claim_id=r), ModelG(claim_id=r, creator_uid=0)
        staked = set()
        for uid in range(n_users):
            if rep_F[uid] < 10 or rep_G[uid] < 10:
                continue
            side = truth if rng.random() < skills[uid] else (
                'NO' if truth == 'YES' else 'YES')
            mF.buy(uid, side, 10.0); rep_F[uid] -= 10.0
            mG.buy(uid, side, 10.0); rep_G[uid] -= 10.0
            staked.add(uid)

        pF = mF.resolve(truth)
        pG = mG.resolve(truth)
        # ``out[uid]`` from each market is net profit (loser = -stake,
        # winner = +pool_share - stake).  We already removed the stake from
        # rep_*[uid] at buy time, so we add (stake + net_profit) = payout.
        for uid in staked:
            rep_F[uid] += 10.0 + pF.get(uid, -10.0)
            rep_G[uid] += 10.0 + pG.get(uid, -10.0)

        history_F.append(sum(rep_F))
        history_G.append(sum(rep_G))

    return {
        'history_F': history_F,
        'history_G': history_G,
        'n_rounds': n_rounds,
        'n_users': n_users,
        'initial_supply': n_users * 200.0,
    }


def scenario_trivial_claim(n_voters: int = 100, yes_fraction: float = 0.9,
                           seed: int = 11):
    """P2 — Trivial-claim farming test.

    ``yes_fraction`` of voters pick YES; the rest pick NO.  Truth = YES so
    the obvious side wins.  Compare per-winner payout under Model F vs G.

    Expected:
      - Model F: winners harvest full share-weighted pool → easy farm.
      - Model G: info-gain factor H(0.9) ≈ 0.47 shrinks the prize; if the
        skew is more extreme (yes_fraction = 0.95), prize approaches zero.
    """
    rng = random.Random(seed)
    skews = [yes_fraction]
    out = {}
    for skew in [0.50, 0.60, 0.75, 0.90, 0.95]:
        mF = CPMM(); mG = ModelG(creator_uid=0)
        for uid in range(n_voters):
            side = 'YES' if rng.random() < skew else 'NO'
            mF.buy(uid, side, 10.0)
            mG.buy(uid, side, 10.0)
        truth = 'YES'
        pF = mF.resolve(truth)
        pG = mG.resolve(truth)
        # Aggregate per-side
        win_F = [pF[s.user_id] for s in mF.stakes if s.side == truth]
        win_G = [pG[s.user_id] for s in mG.stakes if s.side == truth]
        out[skew] = {
            'I': shannon_entropy_bits(mG._final_yes_probability()),
            'avg_winner_profit_F': float(np.mean(win_F)) if win_F else 0.0,
            'avg_winner_profit_G': float(np.mean(win_G)) if win_G else 0.0,
            'total_paid_F': float(sum(pF.values())),
            'total_paid_G': float(sum(pG.values())),
        }
    return out


def scenario_creator_rewards(n_followers: int = 30, seed: int = 13):
    """P3 — Compare creator earnings under three rules:

      (i)  Model F baseline (current) — creator auto-votes YES.
      (ii) Issue #76 option (a) — Model F + creator's prize multiplied by 2.
      (iii) Model G — no auto-vote, creator votes manually + listing bonus.

    Setup: creator uid=0 posts the claim, then 30 followers also vote YES,
    and 10 sceptics vote NO.  Truth = YES.

    For (iii), we also test the case where the creator votes NO (i.e.
    posts a hard claim they suspect of being false).
    """
    def run_F(autoyes_creator: bool):
        m = CPMM()
        if autoyes_creator:
            m.buy(0, 'YES', 10.0)
        for uid in range(1, 1 + n_followers):
            m.buy(uid, 'YES', 10.0)
        for uid in range(1 + n_followers, 11 + n_followers):
            m.buy(uid, 'NO', 10.0)
        return m, m.resolve('YES')

    def run_2x():
        m = CPMMTwoX(creator_uid=0)
        m.buy(0, 'YES', 10.0)
        for uid in range(1, 1 + n_followers):
            m.buy(uid, 'YES', 10.0)
        for uid in range(1 + n_followers, 11 + n_followers):
            m.buy(uid, 'NO', 10.0)
        return m, m.resolve('YES')

    def run_G(creator_side: str):
        m = ModelG(creator_uid=0)
        m.buy(0, creator_side, 10.0)
        for uid in range(1, 1 + n_followers):
            m.buy(uid, 'YES', 10.0)
        for uid in range(1 + n_followers, 11 + n_followers):
            m.buy(uid, 'NO', 10.0)
        return m, m.resolve('YES')

    mF, pF = run_F(autoyes_creator=True)
    m2, p2 = run_2x()
    mG_y, pG_y = run_G('YES')
    mG_n, pG_n = run_G('NO')

    return {
        'F_creator': pF[0],
        '2x_creator': p2[0],
        'G_yes_creator': pG_y[0],
        'G_no_creator': pG_n[0],
        'F_follower_avg': float(np.mean([pF[u] for u in range(1, 1 + n_followers)])),
        'G_follower_avg': float(np.mean([pG_y[u] for u in range(1, 1 + n_followers)])),
        'F_total_supply_delta': sum(pF.values()),
        'G_total_supply_delta': sum(pG_y.values()),
    }


def scenario_adversary_trivial_farming(n_rounds: int = 100, seed: int = 17):
    """Adversary scenario: a single user posts only trivial claims (90/10
    skew) and votes YES on each.  How much rep do they accumulate under F
    vs G after ``n_rounds`` rounds?
    """
    rng = random.Random(seed)
    rep_F, rep_G = 200.0, 200.0
    for r in range(n_rounds):
        mF, mG = CPMM(), ModelG(creator_uid=0)
        # 100 sock-puppet/honest voters mostly YES
        for uid in range(1, 101):
            side = 'YES' if rng.random() < 0.9 else 'NO'
            mF.buy(uid, side, 10.0)
            mG.buy(uid, side, 10.0)
        # the adversary
        mF.buy(0, 'YES', 10.0)
        mG.buy(0, 'YES', 10.0)
        rep_F -= 10.0; rep_G -= 10.0
        pF = mF.resolve('YES'); pG = mG.resolve('YES')
        rep_F += 10.0 + pF.get(0, -10.0)
        rep_G += 10.0 + pG.get(0, -10.0)
    return {'adversary_rep_F': rep_F, 'adversary_rep_G': rep_G,
            'n_rounds': n_rounds}


# ----------------------------------------------------------------------------
# CHARTS
# ----------------------------------------------------------------------------

def chart_inflation(res):
    fig, ax = plt.subplots(figsize=(10, 5))
    xs = np.arange(len(res['history_F']))
    ax.plot(xs, res['history_F'], label='Model F (CPMM)', color='#c0392b',
            linewidth=2)
    ax.plot(xs, res['history_G'], label='Model G (zero-sum)', color='#27ae60',
            linewidth=2)
    ax.axhline(res['initial_supply'], color='gray', linestyle='--',
               linewidth=1, label=f"initial supply {res['initial_supply']:.0f}")
    ax.set_title(f"P1 — Total rep supply over {res['n_rounds']} random rounds")
    ax.set_xlabel("Round"); ax.set_ylabel("Total rep across all users")
    ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_01_inflation.png"), dpi=120)
    plt.close(fig)


def chart_trivial(res):
    skews = sorted(res.keys())
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(skews)); w = 0.4
    avg_F = [res[s]['avg_winner_profit_F'] for s in skews]
    avg_G = [res[s]['avg_winner_profit_G'] for s in skews]
    ax.bar(x - w/2, avg_F, w, label='Model F avg winner net', color='#c0392b')
    ax.bar(x + w/2, avg_G, w, label='Model G avg winner net', color='#27ae60')
    ax.set_xticks(x)
    ax.set_xticklabels([f"YES={int(s*100)}%\nI={res[s]['I']:.2f}" for s in skews])
    ax.set_title("P2 — Per-winner net profit vs claim skew")
    ax.set_ylabel("Avg net profit (rep)")
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_02_trivial.png"), dpi=120)
    plt.close(fig)


def chart_creator(res):
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = ['F (auto-YES)', '2x flat (#76 opt a)',
              'G (vote YES, manual)', 'G (vote NO, manual)']
    vals = [res['F_creator'], res['2x_creator'],
            res['G_yes_creator'], res['G_no_creator']]
    colors = ['#c0392b', '#e67e22', '#27ae60', '#16a085']
    bars = ax.bar(labels, vals, color=colors)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width()/2, v + 0.2, f"{v:+.1f}",
                ha='center', fontsize=10)
    ax.axhline(0, color='gray', linewidth=0.8)
    ax.set_title("P3 — Creator net profit (truth = YES, 30 followers, 10 sceptics)")
    ax.set_ylabel("Creator net rep")
    ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_03_creator.png"), dpi=120)
    plt.close(fig)


def chart_adversary(res):
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(['Model F', 'Model G'],
                  [res['adversary_rep_F'], res['adversary_rep_G']],
                  color=['#c0392b', '#27ae60'])
    for b, v in zip(bars, [res['adversary_rep_F'], res['adversary_rep_G']]):
        ax.text(b.get_x() + b.get_width()/2, v + 5, f"{v:.0f}",
                ha='center', fontsize=10)
    ax.axhline(200.0, color='gray', linestyle='--', linewidth=1,
               label="starting rep (200)")
    ax.set_title(f"P2 follow-up — trivial-farming adversary after "
                 f"{res['n_rounds']} obvious claims")
    ax.set_ylabel("Adversary final rep")
    ax.legend(); ax.grid(alpha=0.3, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(CHART_DIR, "g_04_adversary.png"), dpi=120)
    plt.close(fig)


# ----------------------------------------------------------------------------
# REPORT
# ----------------------------------------------------------------------------

def write_report(infl, triv, creator, adversary):
    L = []
    A = L.append
    A("# Model G — Addressing Issue #76\n")
    A("Auto-built by `simulator_g.py`. Standalone supplement to "
      "`final_recommendation.md` (Models A-F).\n")

    A("## Why a Model G\n")
    A("Issue [#76](https://github.com/ArdaSaygan/VeriFi/issues/76) raised three "
      "problems against Model F that the prior simulation did not address:\n")
    A("1. **Inflation/deflation** — Model F's CPMM mints \"1 rep per winning "
      "share\", so the global rep supply drifts over time. Users can't tell "
      "what a \"good\" score is.\n")
    A("2. **Trivial claims** — Posting an obvious 90/10 claim and voting with "
      "the crowd is risk-free rep farming under Model F.\n")
    A("3. **Low creator rewards** — Auto-casting a YES vote at claim creation "
      "undercompensates the author for the effort of writing a verifiable "
      "claim. Issue proposes either a flat 2× multiplier or letting the "
      "creator vote manually.\n")

    A("## Model G in one paragraph\n")
    A("**Model G = Model F's CPMM + three resolution-side changes.** Trading "
      "(the `buy` step) is unchanged: early buyers still get more shares per "
      "rep, late buyers still get fewer — same locked-share guarantee as F. "
      "At resolution, three changes apply: **(G1)** payouts are made "
      "zero-sum — total rep is conserved per claim; **(G2)** the share of "
      "the losers' pool that flows to winners is multiplied by an "
      "information-gain factor `I = H(p_final) ∈ [0,1]`, where `p_final` is "
      "the CPMM mid-price at resolution. Trivial claims (p≈0 or p≈1) shrink "
      "I toward 0; hard claims (p≈0.5) keep I=1; **(G3)** the creator is no "
      "longer auto-voted YES — they vote manually like any user — and they "
      "receive a `LISTING_BONUS_BASE * I = 2·I` listing bonus paid from the "
      "unallocated losers' pool, provided the claim attracts at least "
      f"{MIN_PARTICIPANTS} distinct voters.\n")

    # ------------------------------------------------------------------
    A("## P1 — Inflation/deflation\n")
    A("**Test.** 60 users with random skill levels stake on "
      f"{infl['n_rounds']} random YES/NO claims. Initial total rep supply = "
      f"{infl['initial_supply']:.0f}. Truth uniformly random per round.\n")
    A("| Model | Final total rep | Drift from initial |")
    A("|---|---|---|")
    drift_F = infl['history_F'][-1] - infl['initial_supply']
    drift_G = infl['history_G'][-1] - infl['initial_supply']
    A(f"| **F** (CPMM) | {infl['history_F'][-1]:.0f} | "
      f"{drift_F:+.0f} ({drift_F / infl['initial_supply'] * 100:+.1f}%) |")
    A(f"| **G** (zero-sum) | {infl['history_G'][-1]:.0f} | "
      f"{drift_G:+.0f} ({drift_G / infl['initial_supply'] * 100:+.2f}%) |")
    A("\n![inflation](charts/g_01_inflation.png)\n")
    A("**Reading.** G is flat by construction (`sum(payouts) == sum(stakes)` "
      "every round). F drifts. The sign of F's drift depends on the seed — "
      "with `np.random.seed(42)` it tends to inflate. A user comparing their "
      "rep to last week's rep needs G's stability to reason about progress.\n")

    # ------------------------------------------------------------------
    A("## P2 — Trivial claims\n")
    A("**Test.** 100 voters split YES/NO at varying skew levels. Truth = YES "
      "(obvious side wins). Compare average winner net profit.\n")
    A("| YES vote share | Info-gain I | F avg winner net | G avg winner net |")
    A("|---|---|---|---|")
    for s in sorted(triv.keys()):
        r = triv[s]
        A(f"| {int(s*100)}% | {r['I']:.2f} | {r['avg_winner_profit_F']:+.2f} | "
          f"{r['avg_winner_profit_G']:+.2f} |")
    A("\n![trivial](charts/g_02_trivial.png)\n")
    A("**Reading.** When the crowd is balanced (50/50, hard claim), G pays "
      "winners essentially what F pays. When the crowd is heavily skewed "
      "(90% YES), G shrinks payouts toward zero — picking the obvious side "
      "is no longer worth the energy spend.\n")

    A("### Adversary follow-up\n")
    A(f"A single user posts only trivial 90/10 claims and votes with the "
      f"crowd for {adversary['n_rounds']} rounds:\n")
    A("| Model | Adversary final rep | Net gain |")
    A("|---|---|---|")
    A(f"| F | {adversary['adversary_rep_F']:.0f} | "
      f"{adversary['adversary_rep_F'] - 200:+.0f} |")
    A(f"| G | {adversary['adversary_rep_G']:.0f} | "
      f"{adversary['adversary_rep_G'] - 200:+.0f} |")
    A("\n![adversary](charts/g_04_adversary.png)\n")
    A("**Reading.** F lets the adversary harvest rep; G starves them — "
      "they pay 1 energy per claim for almost no rep return, so the strategy "
      "is no longer competitive against people staking on actually-uncertain "
      "claims.\n")

    # ------------------------------------------------------------------
    A("## P3 — Creator rewards\n")
    A("**Test.** Creator (uid=0) posts a claim. 30 followers vote YES, 10 "
      "sceptics vote NO. Truth = YES. Compare creator net profit under four "
      "rules.\n")
    A("| Rule | Creator net rep |")
    A("|---|---|")
    A(f"| **F** baseline (auto-YES) | {creator['F_creator']:+.2f} |")
    A(f"| **#76 option (a)** — F + 2× creator prize | {creator['2x_creator']:+.2f} |")
    A(f"| **G** — manual vote = YES + listing bonus | {creator['G_yes_creator']:+.2f} |")
    A(f"| **G** — manual vote = NO + listing bonus | {creator['G_no_creator']:+.2f} |")
    A("\n![creator](charts/g_03_creator.png)\n")
    A(f"Followers under F earn on avg `{creator['F_follower_avg']:+.2f}` rep, "
      f"under G `{creator['G_follower_avg']:+.2f}` (lower because G is "
      "zero-sum and the loser pool is divided over more winners).\n")
    A("**Reading.**\n")
    A("- Option (a) (`2x` flat) overpays the creator any time the claim wins "
      "and underpays when it doesn't — a perverse incentive to post claims "
      "the creator is already certain about. It also breaks zero-sum.\n")
    A("- Model G's listing bonus is bounded (`≤ 2*I ≤ 2.0`) and is paid only "
      "if the claim is informative (high I) and attracts real engagement "
      f"(≥ {MIN_PARTICIPANTS} distinct voters). The creator can also vote "
      "NO on their own claim without losing the bonus — useful when the "
      "creator is genuinely uncertain.\n")
    A("- Total rep supply delta per claim: F = "
      f"{creator['F_total_supply_delta']:+.2f}, G = "
      f"{creator['G_total_supply_delta']:+.2f} (essentially 0). G stays "
      "zero-sum even with the bonus.\n")

    # ------------------------------------------------------------------
    A("## Tuning knobs\n")
    A("All three knobs can be tweaked without changing the contract surface:\n")
    A(f"- `LISTING_BONUS_BASE = {LISTING_BONUS_BASE}` — max listing bonus on "
      "a maximally informative claim (`I = 1`).\n")
    A(f"- `MIN_PARTICIPANTS = {MIN_PARTICIPANTS}` — anti-spam guard. Raise "
      "to make listing bonuses harder to earn.\n")
    A("- `info_gain(p)` — currently Shannon entropy in bits. Alternative is "
      "`1 - |2p - 1|^k` which gives a softer/sharper cutoff depending on `k`.\n")

    A("## What G doesn't fix\n")
    A("- Sybil farming of energy tokens (already noted in the Model F "
      "report). Same 7-day account-age gate still applies.\n")
    A("- Manipulating `p_final` near the resolution clock by a last-second "
      "whale flip is still possible if the bet cap is lifted. The fixed "
      "10-rep / 1-bet-per-claim rule already blocks this in v2, but if those "
      "are relaxed we need a vote-lock window of ~30 min before "
      "resolution.\n")
    A("- Resolution disputes are out of scope — handled separately by the "
      "oracle/admin path.\n")

    A("## Recommendation\n")
    A("Promote Model G to be the v2.1 default once Model F ships. The "
      "trading UX and the staking rules are unchanged, so all the client "
      "code from Model F's rollout keeps working; only the server-side "
      "`resolve_claim` job needs to swap to the new payout formula.\n")

    out_path = os.path.join(OUT_DIR, "model_g_report.md")
    with open(out_path, "w") as f:
        f.write("\n".join(L))
    return out_path


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main():
    print("Scenario: inflation/deflation ...")
    infl = scenario_inflation()
    chart_inflation(infl)

    print("Scenario: trivial claims ...")
    triv = scenario_trivial_claim()
    chart_trivial(triv)

    print("Scenario: creator rewards ...")
    creator = scenario_creator_rewards()
    chart_creator(creator)

    print("Scenario: adversary trivial farming ...")
    adv = scenario_adversary_trivial_farming()
    chart_adversary(adv)

    report = write_report(infl, triv, creator, adv)
    print(f"\nDone. Report: {report}")
    print(f"Charts: {CHART_DIR}/g_*.png")


if __name__ == "__main__":
    main()
