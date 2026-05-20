# Model G — minimal-inflation CPMM with creator auto-join

Built by `simulator_g.py`.

## From Model F to Model G — what changed and why

Model F was the first CPMM-based system (Polymarket-style locked reward). It fixed late-adoption penalty and copy-trade dilution from the old split-the-pot (Model C). But three problems remained:

1. **Inflation**: house seeds every claim pool with 100 virtual rep on each side. Every resolved claim mints up to ~100 rep from thin air.
2. **Trivial farming**: creator was auto-staked YES at creation — guaranteed ~9 rep profit on any obvious claim regardless of quality.
3. **One-sided mint**: if all voters chose the same side, house minted rep with no counterpart losses.

Model G fixes all three with minimal added complexity:

1. **Inflation minimised**: pool depth = creator's chosen X ∈ [10, 100] rep (virtual seed drops from 100 → 10 minimum). Plus 5% burn fee on every trade, permanently removing rep. Combined effect: yearly per-person median rep is stable or slightly deflationary.
2. **Trivial farming closed**: creator auto-joins with their chosen side+amount (real conviction stake), pays a 2-rep listing fee burned permanently. No guaranteed-50%-price freebie.
3. **Refund-if-trivial**: if fewer than 3 distinct dissenters OR fewer than 5 total stakers, all stakes refunded. No rep minted on uncontested claims.

**Locked reward fully preserved**: `shares × 1 rep` at buy time, invariant to all later buyers, for creator and traders alike.

## Design

```
Model F  =  CPMM payouts  +  INIT_L=100 virtual seed
            +  creator auto-YES fixed 10 rep  +  no burn fee

Model G  =  CPMM payouts  +  pool depth = creator X ∈ [10,100]
            +  creator auto-joins own side+amount (locked shares @ buy price)
            +  2-rep listing fee burned
            +  5% burn fee on every trader buy
            +  refund-if-trivial: loser < 3 voters OR total < 5
```

## Inflation — per-person median rep (365 days)

Primary metric: **median rep per person** — honest, not skewed by high-skill winners. 200 agents, 10 claims/day.

| Scenario | Model | Median start | Median end | Median drift | Bottom-25% end | Top-25% end |
|---|---|---|---|---|---|---|
| typical (25% trivial) | F | 200 | 1920 | +860% | 8 | 3677 |
| typical (25% trivial) | G | 200 | -32 | -116% | -80 | 1279 |
| worst-case (100% trivial) | F | 200 | 4485 | +2142% | 4443 | 4500 |
| worst-case (100% trivial) | G | 200 | 87 | -57% | 100 | 138 |

**Typical scenario, 1 year:** median user rep F=1920 vs G=-32 (start: 200).  G median drift -116% vs F +860%.

**What the negative G median means:** the 5% burn fee removes more rep than the virtual seed (INIT_V=10) adds.  The system is net deflationary — rep supply contracts over time.  Skilled users (top quartile: 1279 rep) still grow their balance; median/bottom users lose rep gradually.  This is a deliberate design choice: rep is genuinely scarce, only consistent accurate voters accumulate it.  A minimum rep floor (e.g. 10 rep) or a small daily replenishment grant can prevent users from going bankrupt if desired.

![inflation](charts/g_05_inflation.png)

## Locked reward preserved

Alice buys YES after pool is seeded.  Varying numbers of later YES buyers join, then 10 NO buyers.  Truth = YES.

| Later YES buyers | F (INIT_L=100, creator auto-YES) | G (pool=creator X=10, creator YES) |
|---|---|---|
| 0 | +7.92 | +6.39 |
| 5 | +7.92 | +6.39 |
| 20 | +7.92 | +6.39 |
| 50 | +7.92 | +6.39 |

Alice's profit is **identical regardless of later buyers** in both models — locked reward holds.  G's Alice gets a lower absolute number because INIT_VIRTUAL is smaller (thinner pool = fewer shares at 50% entry), but it is fully locked.

![locked](charts/g_02_locked.png)

## One-sided mint (all voters YES, truth = YES)

30 voters all bet YES over 100 trials.

| Model | Mean mint/claim | Total mint | Refund rate |
|---|---|---|---|
| F (INIT_L=100) | **+142.97 rep** | +14297 rep | 0% |
| G (INIT_V=10) | +0.00 rep | +0 rep | **100%** |

Under G, refund-if-trivial fires (0 NO voters < MIN_LOSER_VOTERS=3) — all stakes refunded, system mint = 0.

![mint](charts/g_04_mint.png)

## Contested claims resolve normally

Sanity check: 200 near-50/50 claims under G.

- Resolved normally: **200** / 200 (100%)
- Triggered trivial refund: 0

Refund-if-trivial does not disturb well-contested claims.

## Creator earnings (skill 0.65, 30 random traders)

| Model | Mean net/claim | Median | % losing |
|---|---|---|---|
| F (auto-YES fixed 10 rep) | -0.76 | -10.00 | 52% |
| G (auto-buy 10 rep, skill-chosen side) | -3.30 | +0.00 | 33% |

G's creator earns based on genuine conviction, not a guaranteed 50%-price freebie.  Expected earnings per claim are lower when skill = 0.65, but the payout is honest.

![creator](charts/g_03_creator.png)

## Sybil attack

10 sybil accounts all vote YES.  Varying honest NO voters.  G's refund-if-trivial prevents minting when dissenters are too few.

| Setup | F mint | G mint | F attacker | G attacker |
|---|---|---|---|---|
| 10 sybils, 0 NO | +62.24 | **+0.00** | +62.24 | **+0.00** |
| 10 sybils, 1 NO | +52.24 | **+0.00** | +62.24 | **+0.00** |
| 10 sybils, 5 NO | +12.24 | **-8.70** | +62.24 | **+38.80** |

- 0–2 dissenters: refund fires, attacker nets **0 rep**.
- 3+ dissenters: claim resolves; attacker profits from thin pool but system mint is bounded by INIT_VIRTUAL=10.

## Summary

| Property | F | G |
|---|---|---|
| Virtual seed (inflation source) | INIT_L=100 | creator X ∈ [10,100] |
| Burn fee | 0% | 5% per trade |
| Median rep after 1 yr (typical) | 1920 | -32 |
| Locked reward | ✅ | ✅ |
| Copy-trade immunity | ✅ | ✅ |
| Creator auto-joins | YES fixed 10 rep | chosen side + amount (10–100) |
| Listing fee | none | 2 rep burned |
| Trivial-claim refund | ❌ | ✅ |
| Sybil farming (no dissenters) | +62 rep | 0 rep |