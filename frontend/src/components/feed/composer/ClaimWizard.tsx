import { useState } from 'react';
import type { AssetItem } from '@/lib/types';
import { type ClaimDraft, emptyDraft } from './types';
import { StepAsset } from './StepAsset';
import { StepTarget } from './StepTarget';
import { StepStake } from './StepStake';

interface ClaimWizardProps {
  registerAsset: (asset: AssetItem) => void;
  initialDraft?: Partial<ClaimDraft>;
  onComplete: (claim: ClaimDraft) => void;
  onCancel: () => void;
  onFillManually: () => void; // Escape hatch
}

export function ClaimWizard({
  registerAsset,
  initialDraft,
  onComplete,
  onCancel,
  onFillManually,
}: ClaimWizardProps) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ClaimDraft>(() => ({
    ...emptyDraft(),
    ...initialDraft,
  }));

  function patchDraft(patch: Partial<ClaimDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Create Claim — Step {step + 1} of 3
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
          <StepAsset
            value={draft}
            registerAsset={registerAsset}
            onChange={patchDraft}
            onNext={nextStep}
          />
        )}
        {step === 1 && (
          <StepTarget
            value={draft}
            onChange={patchDraft}
            onNext={nextStep}
            onBack={prevStep}
          />
        )}
        {step === 2 && (
          <StepStake
            value={draft}
            onChange={patchDraft}
            onComplete={() => onComplete(draft)}
            onBack={prevStep}
          />
        )}
      </div>

      {step === 0 && (
        <div className="flex justify-center pt-2">
          <button 
            onClick={onCancel}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
