import { useEffect, useState } from 'react';
import type { AssetItem } from '@/lib/types';
import { type ClaimDraft, type WizardNavState, emptyDraft } from './types';
import { StepAsset } from './StepAsset';
import { StepTarget } from './StepTarget';
import { StepStake } from './StepStake';

interface ClaimWizardProps {
  assets: AssetItem[];
  initialDraft?: Partial<ClaimDraft>;
  onComplete: (claim: ClaimDraft) => void;
  onCancel: () => void;
  onFillManually: () => void; // Escape hatch
  /** Reports nav state up so the modal footer can drive Previous/Next. Must be stable. */
  onNav: (nav: WizardNavState) => void;
}

const TOTAL_STEPS = 3;

export function ClaimWizard({
  assets,
  initialDraft,
  onComplete,
  onCancel,
  onFillManually,
  onNav,
}: ClaimWizardProps) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ClaimDraft>(() => ({
    ...emptyDraft(),
    ...initialDraft,
  }));

  function patchDraft(patch: Partial<ClaimDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  const stake = parseFloat(draft.stakeRep);
  const canNext =
    step === 0
      ? Boolean(draft.asset_id && draft.claim_type)
      : step === 1
        ? Boolean(draft.percentage && draft.until)
        : !isNaN(stake) && stake >= 10 && stake <= 100;
  const nextLabel = step === TOTAL_STEPS - 1 ? 'Attach Claim' : 'Next';

  function next() {
    if (!canNext) return;
    if (step === TOTAL_STEPS - 1) onComplete(draft);
    else setStep((s) => s + 1);
  }

  function back() {
    if (step === 0) onCancel();
    else setStep((s) => s - 1);
  }

  // Push nav state to the footer whenever it changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    onNav({ canNext, nextLabel, isFirstStep: step === 0, next, back });
  }, [step, canNext, nextLabel, draft]);

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Create Claim — Step {step + 1} of {TOTAL_STEPS}
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
          <StepAsset value={draft} assets={assets} onChange={patchDraft} />
        )}
        {step === 1 && (
          <StepTarget value={draft} onChange={patchDraft} />
        )}
        {step === 2 && (
          <StepStake value={draft} onChange={patchDraft} />
        )}
      </div>
    </div>
  );
}
