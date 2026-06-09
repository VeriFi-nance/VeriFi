/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState } from 'react';
import type { AssetItem } from '@/lib/types';
import type { WizardNavState } from './types';
import { PositionStepAsset } from './PositionStepAsset';
import { PositionStepLevels } from './PositionStepLevels';
import { PositionStepReview } from './PositionStepReview';

export interface PositionDraft {
  assetId: string;
  assetSymbol?: string;
  direction: 'long' | 'short';
  entryPrice: string;
  stopLoss: string;
  takeProfit: string;
  entryInterval: string;
  lifetime: string;
}

export function defaultPositionDraft(): PositionDraft {
  const entry = new Date();
  entry.setDate(entry.getDate() + 2);
  const life = new Date();
  life.setDate(life.getDate() + 7);
  return {
    assetId: '',
    direction: 'long',
    entryPrice: '',
    stopLoss: '',
    takeProfit: '',
    entryInterval: entry.toISOString().slice(0, 16),
    lifetime: life.toISOString().slice(0, 16),
  };
}

interface PositionWizardProps {
  registerAsset: (asset: AssetItem) => void;
  initialDraft?: Partial<PositionDraft>;
  onComplete: (pos: PositionDraft) => void;
  onCancel: () => void;
  onFillManually: () => void;
  /** Reports nav state up so the modal footer can drive Previous/Next. Must be stable. */
  onNav: (nav: WizardNavState) => void;
}

// Steps: 0 asset, 1 levels (3 chart phases), 2 review.
type LevelPhase = 0 | 1 | 2; // entry, take-profit, stop-loss

export function PositionWizard({
  registerAsset,
  initialDraft,
  onComplete,
  onCancel,
  onFillManually,
  onNav,
}: PositionWizardProps) {
  const [step, setStep] = useState(0);
  const [levelPhase, setLevelPhase] = useState<LevelPhase>(0);
  const [error, setError] = useState('');
  const [draft, setDraft] = useState<PositionDraft>(() => ({
    ...defaultPositionDraft(),
    ...initialDraft,
  }));

  function patchDraft(patch: Partial<PositionDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  function validateAndComplete() {
    setError('');
    const en = parseFloat(draft.entryPrice);
    const sl = parseFloat(draft.stopLoss);
    const tp = parseFloat(draft.takeProfit);
    if (isNaN(en) || isNaN(sl) || isNaN(tp)) {
      setError('Entry, TP, and SL must be valid numbers.');
      return;
    }
    const isLong = draft.direction === 'long';
    if (isLong && !(sl < en && en < tp)) {
      setError('For LONG: Stop Loss < Entry < Take Profit.');
      return;
    }
    if (!isLong && !(tp < en && en < sl)) {
      setError('For SHORT: Take Profit < Entry < Stop Loss.');
      return;
    }
    const now = new Date();
    if (new Date(draft.entryInterval) <= now) {
      setError('Entry interval must be in the future.');
      return;
    }
    if (new Date(draft.lifetime) <= new Date(draft.entryInterval)) {
      setError('Lifetime must be after the entry interval.');
      return;
    }
    onComplete(draft);
  }

  // ── Derived nav state ──────────────────────────────
  let canNext = false;
  let nextLabel = 'Next';
  if (step === 0) {
    canNext = Boolean(draft.assetId);
  } else if (step === 1) {
    canNext =
      levelPhase === 0
        ? Boolean(draft.entryPrice)
        : levelPhase === 1
          ? Boolean(draft.takeProfit)
          : Boolean(draft.stopLoss);
    nextLabel = levelPhase === 2 ? 'Review Position' : 'Next';
  } else {
    canNext = true;
    nextLabel = 'Attach Position';
  }
  const isFirstStep = step === 0;

  function next() {
    if (!canNext) return;
    if (step === 0) {
      setStep(1);
      setLevelPhase(0);
    } else if (step === 1) {
      if (levelPhase < 2) {
        setLevelPhase((p) => (p + 1) as LevelPhase);
      } else {
        // Commit direction from entry vs take-profit, then go to review.
        const en = parseFloat(draft.entryPrice);
        const tp = parseFloat(draft.takeProfit);
        patchDraft({ direction: tp >= en ? 'long' : 'short' });
        setStep(2);
      }
    } else {
      validateAndComplete();
    }
  }

  function back() {
    setError('');
    if (step === 0) {
      onCancel();
    } else if (step === 1) {
      if (levelPhase > 0) setLevelPhase((p) => (p - 1) as LevelPhase);
      else setStep(0);
    } else {
      setStep(1);
      setLevelPhase(2);
    }
  }

  // `next`/`back`/`onNav` excluded by design: recreated each render, only need to
  // fire on the primitive state changes below (including them would loop).
  useEffect(() => {
    onNav({ canNext, nextLabel, isFirstStep, next, back });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, levelPhase, canNext, nextLabel, draft]);

  const stepLabel = step === 0 ? 1 : step === 1 ? 2 : 3;

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Create Position — Step {stepLabel} of 3
        </p>
        <button
          onClick={onFillManually}
          className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
        >
          Fill Manually
        </button>
      </div>

      <div className="relative">
        {step === 0 && (
          <PositionStepAsset value={draft} registerAsset={registerAsset} onChange={patchDraft} />
        )}
        {step === 1 && (
          <PositionStepLevels value={draft} onChange={patchDraft} phase={levelPhase} />
        )}
        {step === 2 && (
          <PositionStepReview value={draft} onChange={patchDraft} error={error} />
        )}
      </div>
    </div>
  );
}
