# Model G v2 — locked rewards + harder trivial defense

Stack:
- No creator auto-YES (kept from v1)
- Listing fee: creator pays 2.0 rep at claim creation, burned permanently (anti-spam, small deflation).
- Min loser voters: refund if < 3 distinct dissenters (kept from v1).
- Min total voters: refund if claim attracts < 5 voters total (new — closes 'just bring 3 alts on each side' loophole).
- INIT_L = 30.0 (was 100): per-claim mint cap drops from ~+143 to ~+43 rep.

## Locked reward intact

Alice bets YES, vary late YES buyers, truth=YES:

| Later YES buyers | F | G v1 | G v2 |
|---|---|---|---|
| 0 | +9.17 | +9.17 | +8.00 |
| 5 | +9.17 | +9.17 | +8.00 |
| 20 | +9.17 | +9.17 | +8.00 |
| 50 | +9.17 | +9.17 | +8.00 |

Alice's profit is invariant across late buyers in every model — locked reward holds.  v2's Alice gets a lower absolute number than v1 because INIT_L is smaller (fewer subsidised shares per stake), but it's still locked.

## Trivial farming attack

Attacker brings 10 sybil accounts all voting YES.  Honest NO voters vary.  How much does the attacker pocket?

| Honest NO voters | F attacker net | G v1 attacker | G v2 attacker | F mint | G v1 mint | G v2 mint |
|---|---|---|---|---|---|---|
| 0 | +62.2 | +0.0 | -2.0 | +62.2 | +0.0 | -2.0 |
| 1 | +62.2 | +0.0 | -2.0 | +52.2 | +0.0 | -2.0 |
| 2 | +62.2 | +0.0 | -2.0 | +42.2 | +0.0 | -2.0 |
| 3 | +62.2 | +62.2 | +45.6 | +32.2 | +32.2 | +15.6 |
| 5 | +62.2 | +62.2 | +45.6 | +12.2 | +12.2 | -4.4 |
| 10 | +62.2 | +62.2 | +45.6 | -37.8 | -37.8 | -54.4 |

## Inflation 180-day drift

| Scenario | F | G v1 | G v2 |
|---|---|---|---|
| typical (25% trivial) | +422% | +173% | +154% |
| worst trivial (100%) | +1050% | +77% | +62% |
