/* eslint-disable react-refresh/only-export-components */
import { useState } from 'react';
import type { AssetItem } from '@/lib/types';
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
}

export function PositionWizard({
  registerAsset,
  initialDraft,
  onComplete,
  onCancel,
  onFillManually,
}: PositionWizardProps) {
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<PositionDraft>(() => ({
    ...defaultPositionDraft(),
    ...initialDraft,
  }));

  function patchDraft(patch: Partial<PositionDraft>) {
    setDraft((prev) => ({ ...prev, ...patch }));
  }

  const nextStep = () => setStep((s) => s + 1);
  const prevStep = () => setStep((s) => s - 1);

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Create Position — Step {step + 1} of 3
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
          <PositionStepAsset
            value={draft}
            registerAsset={registerAsset}
            onChange={patchDraft}
            onNext={nextStep}
          />
        )}
        {step === 1 && (
          <PositionStepLevels
            value={draft}
            onChange={patchDraft}
            onNext={nextStep}
            onBack={prevStep}
          />
        )}
        {step === 2 && (
          <PositionStepReview
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
