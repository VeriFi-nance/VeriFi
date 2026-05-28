# Inflation reduction fixes — sweep

Each fix tested against three scenarios. 180 days, 200 users, 10 claims/day.

## Fixes tested

- **A** — `INIT_L=30`: lower CPMM virtual seed.
- **B** — `vote_share_refund=0.15`: refund if losing side < 15% of total voters (in addition to the absolute count rule).
- **C** — `burn_bps=100`: 1% of every stake burned.
- **D** — `mint_cap=20`: if a claim would mint > 20 rep, scale winning payouts down to fit the cap.

## Scenario: typical (25% trivial, skill 0.4-0.75)

| Fix | 180-day drift |
|---|---|
| F (baseline) | +431% |
| G (current) | +176% |
| G + A: INIT_L=30 | +145% |
| G + B: vote-share refund 15% | +170% |
| G + C: burn 1% | +180% |
| G + D: mint cap 20/claim | -82% |
| G + A+B+C (all) | +148% |

## Scenario: worst-case trivial (100% trivial)

| Fix | 180-day drift |
|---|---|
| F (baseline) | +1049% |
| G (current) | +73% |
| G + A: INIT_L=30 | +68% |
| G + B: vote-share refund 15% | +0% |
| G + C: burn 1% | +73% |
| G + D: mint cap 20/claim | -2% |
| G + A+B+C (all) | +0% |

## Scenario: homogeneous high skill (no synthetic trivial)

| Fix | 180-day drift |
|---|---|
| F (baseline) | +900% |
| G (current) | +752% |
| G + A: INIT_L=30 | +684% |
| G + B: vote-share refund 15% | +47% |
| G + C: burn 1% | +746% |
| G + D: mint cap 20/claim | -78% |
| G + A+B+C (all) | +40% |

## Recommendation

**Best across all 3 scenarios:** `G + D: mint cap 20/claim` — minimises the worst-case drift across knobs tested.
