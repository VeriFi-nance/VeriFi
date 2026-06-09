import { useMemo, useReducer, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  ChevronDown,
  ChevronUp,
  RotateCcw,
  TrendingUp,
  TrendingDown,
  Shuffle,
  Gavel,
  Search,
  Zap,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Reputation Score simulator — a faithful, clickable model of the real backend.
//
// Source of truth: backend/posts/rep_market.py ("Model G" CPMM) and
// backend/accounts/energy.py. Constants below are copied 1:1 so the numbers
// users see here match what production actually does on resolve().
//
//   ENERGY  — a daily action budget (NOT the score). Posting a claim or
//             staking each costs 1 energy. You start with 4, +3 every UTC day.
//   REP     — the reputation score that moves. Every claim is a YES/NO market;
//             stakes set the live odds; the winning side splits the pool.
//
// The creator always takes the YES side (you only open a market on a claim you
// believe), so there is no side toggle here.
// ---------------------------------------------------------------------------

// --- energy (accounts/energy.py) --------------------------------------------
const INITIAL_ENERGY = 4;
const DAILY_GRANT = 3;
const CLAIM_ENERGY_COST = 1;
const STAKE_ENERGY_COST = 1;

// --- rep market (posts/rep_market.py) ---------------------------------------
const TRADER_STAKE = 10;
const VIRTUAL_SEED = 10;
const BURN_FEE = 0.05;
const LISTING_FEE = 2;
const CREATOR_CUT_PCT = 0.05;
const MIN_LOSER_VOTERS = 3;
const MIN_TOTAL_VOTERS = 5;
const CREATOR_MIN_STAKE = 10;
const CREATOR_MAX_STAKE = 100;
const CREATOR_SIDE = 'YES' as const;

type Side = 'YES' | 'NO';

interface Stake {
  id: number;
  side: Side;
  shares: number;
  stakeAmount: number;
  netPaid: number;
  isCreator?: boolean;
}

interface SimState {
  stakes: Stake[];
  yReserve: number;
  nReserve: number;
  yesHistory: number[];
  voteHistory: number[];
  creatorStake: number;
  resolvedSide: Side | null;
  trivial: boolean;
  payouts: Record<number, number>;
}

function cpmmBuy(yReserve: number, nReserve: number, side: Side, r: number) {
  let shares: number;
  let newY: number;
  let newN: number;
  if (side === 'YES') {
    shares = r + ((yReserve + r) * r) / (nReserve + 2 * r);
    newY = ((yReserve + r) * (nReserve + r)) / (nReserve + 2 * r);
    newN = nReserve + 2 * r;
  } else {
    shares = r + ((nReserve + r) * r) / (yReserve + 2 * r);
    newN = ((nReserve + r) * (yReserve + r)) / (yReserve + 2 * r);
    newY = yReserve + 2 * r;
  }
  return { shares, yReserve: newY, nReserve: newN };
}

function yesPriceOf(yReserve: number, nReserve: number) {
  return nReserve / (yReserve + nReserve);
}

function freshState(creatorStake: number): SimState {
  const net = creatorStake * (1 - BURN_FEE);
  const v = VIRTUAL_SEED;
  const shares = net + ((v + net) * net) / (v + 2 * net);
  const yReserve = v + net;
  const nReserve = v + net;
  const creator: Stake = {
    id: 1,
    side: CREATOR_SIDE,
    shares,
    stakeAmount: creatorStake,
    netPaid: net,
    isCreator: true,
  };
  return {
    stakes: [creator],
    yReserve,
    nReserve,
    yesHistory: [0.5, yesPriceOf(yReserve, nReserve)],
    voteHistory: [0, 1],
    creatorStake,
    resolvedSide: null,
    trivial: false,
    payouts: {},
  };
}

function isTrivial(stakes: Stake[], winningSide: Side) {
  const losingSide: Side = winningSide === 'YES' ? 'NO' : 'YES';
  const loserVoters = stakes.filter((s) => s.side === losingSide).length;
  return loserVoters < MIN_LOSER_VOTERS || stakes.length < MIN_TOTAL_VOTERS;
}

function resolvePayouts(stakes: Stake[], winningSide: Side) {
  const trivial = isTrivial(stakes, winningSide);
  const payouts: Record<number, number> = {};
  if (trivial) {
    for (const s of stakes) payouts[s.id] = s.netPaid;
    return { trivial, payouts };
  }
  for (const s of stakes) payouts[s.id] = s.side === winningSide ? s.shares : 0;
  const losingSide: Side = winningSide === 'YES' ? 'NO' : 'YES';
  const creator = stakes.find((s) => s.isCreator && s.side === winningSide);
  if (creator) {
    const losersPool = stakes.filter((s) => s.side === losingSide).reduce((a, s) => a + s.netPaid, 0);
    payouts[creator.id] += CREATOR_CUT_PCT * losersPool;
  }
  return { trivial, payouts };
}

function profitFor(stakes: Stake[], s: Stake, winningSide: Side) {
  const { payouts } = resolvePayouts(stakes, winningSide);
  const creatorFee = s.isCreator ? LISTING_FEE : 0;
  return payouts[s.id] - s.stakeAmount - creatorFee;
}

type Action =
  | { type: 'add'; side: Side }
  | { type: 'addMany'; side: Side; count: number }
  | { type: 'random'; count: number }
  | { type: 'resolve'; side: Side }
  | { type: 'reset'; creatorStake: number };

function addOne(state: SimState, side: Side): SimState {
  if (state.resolvedSide) return state;
  const net = TRADER_STAKE * (1 - BURN_FEE);
  const { shares, yReserve, nReserve } = cpmmBuy(state.yReserve, state.nReserve, side, net);
  const stakes = [
    ...state.stakes,
    { id: state.stakes.length + 1, side, shares, stakeAmount: TRADER_STAKE, netPaid: net },
  ];
  return {
    ...state,
    stakes,
    yReserve,
    nReserve,
    yesHistory: [...state.yesHistory, yesPriceOf(yReserve, nReserve)],
    voteHistory: [...state.voteHistory, stakes.length],
  };
}

function reducer(state: SimState, action: Action): SimState {
  switch (action.type) {
    case 'add':
      return addOne(state, action.side);
    case 'addMany': {
      let next = state;
      for (let i = 0; i < action.count; i++) next = addOne(next, action.side);
      return next;
    }
    case 'random': {
      let next = state;
      for (let i = 0; i < action.count; i++) next = addOne(next, Math.random() < 0.5 ? 'YES' : 'NO');
      return next;
    }
    case 'resolve': {
      if (state.resolvedSide) return state;
      const { trivial, payouts } = resolvePayouts(state.stakes, action.side);
      return { ...state, resolvedSide: action.side, trivial, payouts };
    }
    case 'reset':
      return freshState(action.creatorStake);
  }
}

function YesPriceChart({ votes, prices }: { votes: number[]; prices: number[] }) {
  const W = 600;
  const H = 200;
  const padX = 28;
  const padY = 16;
  const maxX = Math.max(10, votes[votes.length - 1] || 10);
  const x = (v: number) => padX + (v / maxX) * (W - padX * 2);
  const y = (p: number) => padY + (1 - p) * (H - padY * 2);
  const points = prices.map((p, i) => `${x(votes[i])},${y(p)}`).join(' ');
  const area = `${padX},${H - padY} ${points} ${x(votes[votes.length - 1] || 0)},${H - padY}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40" preserveAspectRatio="none" role="img" aria-label="YES price over votes">
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <line key={g} x1={padX} x2={W - padX} y1={y(g)} y2={y(g)} className="stroke-border" strokeWidth={1} strokeDasharray={g === 0.5 ? '0' : '3 4'} />
      ))}
      <polygon points={area} className="fill-emerald-500/10" />
      <polyline points={points} fill="none" className="stroke-emerald-500" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      {prices.map((p, i) => (
        <circle key={i} cx={x(votes[i])} cy={y(p)} r={2.5} className="fill-emerald-500" />
      ))}
    </svg>
  );
}

function Money({ value }: { value: number }) {
  if (value > 0.005) return <span className="font-semibold text-emerald-600 dark:text-emerald-400">+{value.toFixed(1)}</span>;
  if (value < -0.005) return <span className="font-semibold text-red-600 dark:text-red-400">{value.toFixed(1)}</span>;
  return <span className="text-muted-foreground">0.0</span>;
}

const QUESTION = 'Will BTC close above $100k by Dec 31?';
const PAGE_SIZE = 6;

export default function RepScoreSim() {
  const [creatorStake, setCreatorStake] = useState(TRADER_STAKE);
  const [state, dispatch] = useReducer(reducer, undefined, () => freshState(TRADER_STAKE));
  const [showMath, setShowMath] = useState(false);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);

  const resolved = state.resolvedSide;
  const yesPrice = yesPriceOf(state.yReserve, state.nReserve);
  const yesPct = yesPrice * 100;
  const noPct = 100 - yesPct;
  const pool = state.stakes.reduce((a, s) => a + s.stakeAmount, 0);
  const yesVotes = state.stakes.filter((s) => s.side === 'YES').length;
  const noVotes = state.stakes.length - yesVotes;

  const rows = useMemo(
    () =>
      state.stakes.map((s) => ({
        ...s,
        label: s.isCreator ? 'Creator' : `User ${s.id}`,
        yesProfit: profitFor(state.stakes, s, 'YES'),
        noProfit: profitFor(state.stakes, s, 'NO'),
        paid: resolved ? state.payouts[s.id] ?? 0 : 0,
        netResolved: resolved ? profitFor(state.stakes, s, resolved) : 0,
        odds: (TRADER_STAKE / s.shares) * 100,
      })),
    [state.stakes, state.payouts, resolved],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const base = q ? rows.filter((r) => r.label.toLowerCase().includes(q) || r.side.toLowerCase().includes(q)) : rows;
    return base.slice().reverse();
  }, [rows, query]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function applyCreator() {
    const clamped = Math.min(CREATOR_MAX_STAKE, Math.max(CREATOR_MIN_STAKE, Math.round(creatorStake / 10) * 10));
    setCreatorStake(clamped);
    setPage(0);
    setQuery('');
    dispatch({ type: 'reset', creatorStake: clamped });
  }

  const totalPaid = resolved ? Object.values(state.payouts).reduce((a, b) => a + b, 0) : 0;
  const paidCount = resolved ? Object.values(state.payouts).filter((v) => v > 0.005).length : 0;

  return (
    <div className="space-y-4 text-sm">
      <p className="text-muted-foreground leading-relaxed">
        Every claim is a market. People stake <strong>Reputation (Rep)</strong> on{' '}
        <span className="text-emerald-600 dark:text-emerald-400 font-medium">YES</span> or{' '}
        <span className="text-red-600 dark:text-red-400 font-medium">NO</span>; the crowd's stakes set the live odds.
        When the claim resolves, the winning side splits the pool — so being <strong>early and right</strong> pays the
        most. This is the exact production formula; play with it below.
      </p>

      {/* Creator setup */}
      <div className="rounded-lg border p-3 space-y-2">
        <div className="font-medium">1 · Open the market</div>
        <p className="text-xs text-muted-foreground">
          The creator always takes <strong className="text-emerald-600 dark:text-emerald-400">YES</strong> (you only open
          a market on a claim you believe). It costs <strong className="text-foreground">1 energy</strong> + a{' '}
          <strong className="text-foreground">{LISTING_FEE}-Rep listing fee</strong> (burned), plus a stake between{' '}
          {CREATOR_MIN_STAKE} and {CREATOR_MAX_STAKE} Rep.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label htmlFor="repsim-stake" className="text-xs font-medium text-muted-foreground">
              Creator stake ({CREATOR_MIN_STAKE}–{CREATOR_MAX_STAKE} Rep)
            </label>
            <div className="flex items-center gap-3">
              <input
                id="repsim-stake"
                type="range"
                min={CREATOR_MIN_STAKE}
                max={CREATOR_MAX_STAKE}
                step={10}
                value={creatorStake}
                onChange={(e) => setCreatorStake(Number(e.target.value))}
                className="w-36 accent-primary"
              />
              <Input
                type="number"
                min={CREATOR_MIN_STAKE}
                max={CREATOR_MAX_STAKE}
                step={10}
                value={creatorStake}
                onChange={(e) => setCreatorStake(Number(e.target.value))}
                className="w-20 h-8"
              />
            </div>
          </div>
          <Button size="sm" onClick={applyCreator}>
            <RotateCcw /> Open / reset
          </Button>
        </div>
      </div>

      {/* Market */}
      <div className="rounded-lg border p-3 space-y-3">
        <div>
          <div className="font-medium">2 · {QUESTION}</div>
          <div className="text-xs text-muted-foreground">
            Pool: <strong className="text-foreground">{pool.toFixed(0)} Rep</strong> · {state.stakes.length} predictions ·
            creator staked {state.creatorStake} on{' '}
            <span className="text-emerald-600 dark:text-emerald-400">YES</span>
            {resolved && (
              <span className="ml-2 inline-flex items-center rounded-full bg-foreground/10 px-2 py-0.5 font-medium text-foreground">
                Resolved · {resolved} won{state.trivial ? ' (trivial refund)' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Odds bar */}
        <div>
          <div className="flex justify-between text-xs font-medium mb-1">
            <span className="text-emerald-600 dark:text-emerald-400">YES {yesPct.toFixed(0)}%</span>
            <span className="text-red-600 dark:text-red-400">NO {noPct.toFixed(0)}%</span>
          </div>
          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted">
            <div className="bg-emerald-500 transition-all" style={{ width: `${yesPct}%` }} />
            <div className="bg-red-500 transition-all" style={{ width: `${noPct}%` }} />
          </div>
        </div>

        {/* Stake actions */}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" disabled={!!resolved} onClick={() => dispatch({ type: 'add', side: 'YES' })}>
            <TrendingUp /> Stake YES
          </Button>
          <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white" disabled={!!resolved} onClick={() => dispatch({ type: 'add', side: 'NO' })}>
            <TrendingDown /> Stake NO
          </Button>
          <Button size="sm" variant="outline" disabled={!!resolved} onClick={() => dispatch({ type: 'addMany', side: 'YES', count: 10 })}>
            +10 YES
          </Button>
          <Button size="sm" variant="outline" disabled={!!resolved} onClick={() => dispatch({ type: 'addMany', side: 'NO', count: 10 })}>
            +10 NO
          </Button>
          <Button size="sm" variant="outline" disabled={!!resolved} onClick={() => dispatch({ type: 'random', count: 25 })}>
            <Shuffle /> 25 random
          </Button>
        </div>

        {/* Chart */}
        <div className="rounded-lg border bg-muted/30 p-2">
          <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
            <span>YES odds over time</span>
            <span>{yesVotes} YES · {noVotes} NO</span>
          </div>
          <YesPriceChart votes={state.voteHistory} prices={state.yesHistory} />
        </div>

        {/* Resolve */}
        <div className="rounded-lg border bg-muted/30 p-2.5 space-y-2">
          <div className="flex items-center gap-2 font-medium">
            <Gavel className="size-4" /> 3 · Resolve the claim
          </div>
          {!resolved ? (
            <>
              <p className="text-xs text-muted-foreground">
                At the deadline the oracle decides the real outcome. Pick the winner to see who gets paid.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white" onClick={() => dispatch({ type: 'resolve', side: 'YES' })}>
                  Resolve: YES wins
                </Button>
                <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white" onClick={() => dispatch({ type: 'resolve', side: 'NO' })}>
                  Resolve: NO wins
                </Button>
              </div>
            </>
          ) : (
            <>
              <p>
                <strong className={resolved === 'YES' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
                  {resolved} won.
                </strong>{' '}
                {state.trivial ? (
                  <span className="text-muted-foreground">
                    Too few contested it ({'<'}
                    {MIN_LOSER_VOTERS} losers or {'<'}
                    {MIN_TOTAL_VOTERS} total) — everyone refunded their net stake. No score changes hands.
                  </span>
                ) : (
                  <span className="text-muted-foreground">
                    {paidCount} winner{paidCount === 1 ? '' : 's'} shared{' '}
                    <strong className="text-foreground">{totalPaid.toFixed(1)} Rep</strong> from the pool.
                  </span>
                )}
              </p>
              <Button size="sm" variant="ghost" onClick={applyCreator}>
                <RotateCcw /> New market
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Participants */}
      <div className="rounded-lg border">
        <div className="border-b p-3 space-y-2">
          <div className="font-medium">Who earns what</div>
          <div className="text-xs text-muted-foreground">
            {resolved ? 'Final Rep credited to each participant, and their net P/L.' : 'Net Rep change per participant, depending on which side wins.'}
          </div>
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              placeholder="Search participant or side…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(0);
              }}
              className="pl-8 h-8"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="px-3 py-2 text-left font-medium">Participant</th>
                <th className="px-3 py-2 text-left font-medium">Side</th>
                <th className="px-3 py-2 text-right font-medium">Entry odds</th>
                {resolved ? (
                  <>
                    <th className="px-3 py-2 text-right font-medium">Paid</th>
                    <th className="px-3 py-2 text-right font-medium">Net P/L</th>
                  </>
                ) : (
                  <>
                    <th className="px-3 py-2 text-right font-medium">If YES</th>
                    <th className="px-3 py-2 text-right font-medium">If NO</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r) => {
                const won = resolved && r.side === resolved && !state.trivial;
                return (
                  <tr key={r.id} className={cn('border-b last:border-0', won && 'bg-emerald-500/5')}>
                    <td className="px-3 py-1.5 whitespace-nowrap">
                      {r.isCreator ? <span className="font-medium text-primary">Creator</span> : <span className="text-muted-foreground">{r.label}</span>}
                    </td>
                    <td className="px-3 py-1.5">
                      <span className={cn('font-semibold', r.side === 'YES' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400')}>{r.side}</span>
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums text-muted-foreground">{r.odds.toFixed(0)}%</td>
                    {resolved ? (
                      <>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          {r.paid > 0.005 ? <span className="font-semibold text-foreground">{r.paid.toFixed(1)}</span> : <span className="text-muted-foreground">0.0</span>}
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          <Money value={r.netResolved} />
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          <Money value={r.yesProfit} />
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">
                          <Money value={r.noProfit} />
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
              {pageRows.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-3 py-5 text-center text-muted-foreground">
                    No participants match “{query}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between border-t px-3 py-2 text-xs text-muted-foreground">
          <span>
            {filtered.length} participant{filtered.length === 1 ? '' : 's'}
            {query && ' (filtered)'}
          </span>
          <div className="flex items-center gap-2">
            <Button size="xs" variant="outline" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
              Prev
            </Button>
            <span>
              {safePage + 1} / {pageCount}
            </span>
            <Button size="xs" variant="outline" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
              Next
            </Button>
          </div>
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-lg border">
        <button className="flex w-full items-center justify-between px-3 py-2.5 text-left font-medium" onClick={() => setShowMath((v) => !v)}>
          How the maths works
          {showMath ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>
        {showMath && (
          <div className="border-t p-3 text-muted-foreground space-y-3 leading-relaxed">
            <div className="rounded-lg border bg-muted/30 p-2.5 flex gap-2">
              <Zap className="size-4 shrink-0 text-amber-500 mt-0.5" />
              <span>
                <strong className="text-foreground">Energy ≠ Rep.</strong> Energy is your daily action budget — start with{' '}
                {INITIAL_ENERGY}, +{DAILY_GRANT} each UTC day. Posting a claim costs {CLAIM_ENERGY_COST} energy and each
                stake costs {STAKE_ENERGY_COST}. Rep is the score the market moves; running out of energy only
                rate-limits you.
              </span>
            </div>
            <ul className="space-y-1.5 list-disc pl-5">
              <li>
                <strong className="text-foreground">Odds set the payout.</strong> Markets open at 50/50. Your reward per
                Rep is locked at the odds you entered, so early movers on the winning side keep more.
              </li>
              <li>
                <strong className="text-foreground">Winners split the pool.</strong> On resolve the losing side's Rep
                flows to winners by locked shares. Lose, and you forfeit your stake.
              </li>
              <li>
                <strong className="text-foreground">Small burn ({(BURN_FEE * 100).toFixed(0)}%).</strong> A slice of every
                stake is burned, so spamming junk predictions bleeds Rep.
              </li>
              <li>
                <strong className="text-foreground">Creator incentive.</strong> A {LISTING_FEE}-Rep listing fee is burned
                on open; if YES wins, the creator earns a {(CREATOR_CUT_PCT * 100).toFixed(0)}% cut of the losing pool.
              </li>
              <li>
                <strong className="text-foreground">Trivial markets refund.</strong> Fewer than {MIN_LOSER_VOTERS} losers
                or {MIN_TOTAL_VOTERS} total → everyone refunded their net stake. No free score from an uncontested call.
              </li>
              <li>
                <strong className="text-foreground">Zero inflation.</strong> No Rep is minted on payout; it only moves
                between winners and losers.
              </li>
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
