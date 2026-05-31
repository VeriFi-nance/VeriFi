import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { ClaimForm } from './composer/ClaimForm';
import { emptyDraft, validateDraft, type ClaimDraft } from './composer/types';
import { createHardClaim, getAssets } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import type { AssetItem } from '@/lib/types';
import { buildClaimPayload } from '@/lib/crypto';
import { signPayload } from '@/lib/signing';

interface Props {
  onCreated: () => void;
}

/** Standalone dialog for creating a single HardClaim (no parent post). */
export function CreateClaimDialog({ onCreated }: Props) {
  const openLogin = useOpenLogin();
  const auth = useAuthState();
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [draft, setDraft] = useState<ClaimDraft>(emptyDraft);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) getAssets().then(setAssets).catch(console.error);
  }, [open]);

  function patch(p: Partial<ClaimDraft>) {
    setDraft((d) => ({ ...d, ...p }));
  }

  function handleTriggerClick(e: React.MouseEvent) {
    if (!auth.authenticated) {
      e.preventDefault();
      openLogin();
    }
  }

  async function handleSubmit() {
    if (!auth.authenticated) {
      openLogin();
      return;
    }
    const result = validateDraft(draft, assets);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      const payloadObj = {
        asset_symbol: result.value.asset.symbol,
        direction: result.value.direction,
        percentage: result.value.percentage,
        until: result.value.until,
        created_at: new Date().toISOString(),
      };
      
      const payloadStr = buildClaimPayload(payloadObj);
      const signature = await signPayload(payloadStr);

      await createHardClaim({
        asset_id: result.value.asset.id,
        direction: result.value.direction,
        percentage: result.value.percentage,
        until: result.value.until,
        signature,
        claim_payload: payloadObj,
        ...(result.value.market ? { market: result.value.market } : {}),
      });
      setOpen(false);
      setDraft(emptyDraft());
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create claim.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RD.Root open={open} onOpenChange={setOpen}>
      <RD.Trigger asChild>
        <Button size="sm" onClick={handleTriggerClick}>+ New Claim</Button>
      </RD.Trigger>
      <RD.Content>
        <RD.Header>
          <RD.Title>New Hard Claim</RD.Title>
          <RD.Description>Submit a verifiable prediction.</RD.Description>
        </RD.Header>

        <div className="space-y-3">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <ClaimForm
            value={draft}
            assets={assets}
            onChange={patch}
            onSubmit={handleSubmit}
            submitLabel={submitting ? 'Creating…' : 'Submit Claim'}
          />
        </div>
      </RD.Content>
    </RD.Root>
  );
}
