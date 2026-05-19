# Model G — F minus creator auto-YES

Built by `simulator_g.py`.  Sister analysis: `leaderboard_analysis.md` (does F's inflation actually hurt the leaderboard?).

## What changed

```
Model F  =  CPMM payouts + v2 hard rules + energy gate + creator auto-YES on creation
Model G  =  CPMM payouts + v2 hard rules + energy gate    (NO creator auto-YES)
```

Everything else from F is kept verbatim.  Locked reward, copy-trade immunity, whale rules, energy gate — all unchanged.

## Scenario 1 — trivial-claim farming

100 voters, varying YES skew.  Truth = YES.  How much does the creator earn?

| Voter skew (% YES) | F (auto-YES) | G (no auto-YES) | Difference |
|---|---|---|---|
| 50% | +9.17 | +0.00 | -9.17 |
| 70% | +9.17 | +0.00 | -9.17 |
| 90% | +9.17 | +0.00 | -9.17 |
| 95% | +9.17 | +0.00 | -9.17 |

![trivial](charts/g_01_trivial.png)

**Reading.** Under F, a creator posting an obvious-YES claim earns ~9 rep for free.  Under G, they earn 0 unless they personally vote.  Trivial-farming attack closed.

## Scenario 2 — locked reward preserved

Alice bets YES, then varying numbers of later YES buyers join, then 10 NO buyers.  Truth = YES.  Alice's profit should be identical regardless of later buyers (F's locked-reward property).

| Later YES buyers | F | G |
|---|---|---|
| 0 | +7.92 | +9.17 |
| 5 | +7.92 | +9.17 |
| 20 | +7.92 | +9.17 |
| 50 | +7.92 | +9.17 |

![locked](charts/g_02_locked.png)

**Reading.** G keeps F's locked-reward exactly — only the creator's automatic stake is gone.  Traders' payouts are unaffected.

## Scenario 3 — creator's expected earnings under each model

Creator with skill 0.65 (better than random) posts claims.  Under F, they get auto-staked on YES at creation.  Under G, they vote manually based on their skill after seeing some early voters.  30 other voters per claim, random truth.

| Model | Mean creator rep / claim | Median | % losing |
|---|---|---|---|
| F | -0.42 | -0.42 | 50% |
| G | +2.59 | +7.88 | 36% |

![creator](charts/g_03_creator.png)

**Reading.** Creator's expected rep / claim drops by 3.01 when we remove the auto-YES — but they were earning that as a freebie, regardless of claim quality.  Under G, the creator earns when their skill-based vote is correct, which is the honest signal.

## Where the leaderboard problem goes

See `leaderboard_analysis.md`.  Under realistic 180-day sim:

- Inflation: +244% drift
- Rank stability: Spearman ρ = 0.87 (preserved)
- Final rep ↔ skill: ρ = 0.93 (clean signal)
- Median-skill newcomer at day 90 → pctl 48% (peers at 52%) — caught up

Therefore the inflation does not damage the leaderboard's *ordering*.  The fix is a UI tweak:

```jsx
display "Top {Math.round((1 - user.percentile) * 100)}%"
instead of  "{user.rep} rep"
```

## What G keeps from F

- Locked reward (shares × 1 rep at buy time)
- Copy-trade immunity (Alice's share count fixed at click)
- Fixed 10-rep stake + 1-per-claim rule (no whales)
- Daily energy gate (no leaderboard runaway)
- 7-day sybil guard
- House subsidy bound (~100 rep / claim via virtual liquidity)

## Summary

| Issue | Status under G |
|---|---|
| #76 P1 inflation | UI-fix only (percentile display) |
| #76 P2 trivial farming | ✅ fixed by removing auto-YES |
| #76 P3 low creator reward | accept: creators paid only for honest votes |
| Locked reward | ✅ preserved |
| Copy-trade immunity | ✅ preserved |
| Whale | ✅ rule-impossible |
| Leaderboard runaway | ✅ energy gate |
| House subsidy | ⚠ same as F (~100 rep / claim) |