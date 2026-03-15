import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { ReviewClaim } from '@/lib/types';

interface ClaimCardProps {
  claim: ReviewClaim;
  onChange: (updated: ReviewClaim) => void;
}

export default function ClaimCard({ claim, onChange }: ClaimCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ReviewClaim>(claim);

  function startEdit() {
    setDraft(claim);
    setEditing(true);
  }

  function saveEdit() {
    onChange(draft);
    setEditing(false);
  }

  function cancelEdit() {
    setDraft(claim);
    setEditing(false);
  }

  function reject() {
    onChange({ ...claim, status: 'rejected' });
  }

  function undo() {
    onChange({ ...claim, status: 'confirmed' });
  }

  const isRejected = claim.status === 'rejected';

  if (editing) {
    return (
      <Card className="border border-border">
        <CardContent className="pt-4 space-y-3">
          <Textarea
            value={draft.text}
            onChange={(e) => setDraft({ ...draft, text: e.target.value })}
            rows={3}
            className="resize-none"
          />
          <div className="flex gap-2">
            <Input
              placeholder="Asset (e.g. BTC)"
              value={draft.asset}
              onChange={(e) => setDraft({ ...draft, asset: e.target.value })}
            />
            <Input
              placeholder="Direction (e.g. bullish)"
              value={draft.direction}
              onChange={(e) => setDraft({ ...draft, direction: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={cancelEdit}>
              Cancel
            </Button>
            <Button className="flex-1" onClick={saveEdit}>
              Save
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={isRejected ? 'opacity-50 border-dashed' : 'border border-border'}>
      <CardContent className="pt-4 space-y-2">
        <p className={`text-sm ${isRejected ? 'line-through text-muted-foreground' : ''}`}>
          {claim.text}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          {claim.asset && (
            <Badge variant="secondary">{claim.asset}</Badge>
          )}
          {claim.direction && (
            <Badge
              variant={claim.direction.toLowerCase() === 'bullish' ? 'default' : 'destructive'}
            >
              {claim.direction}
            </Badge>
          )}
        </div>
        <div className="flex gap-2 pt-1">
          {isRejected ? (
            <Button variant="outline" size="sm" onClick={undo}>
              Undo
            </Button>
          ) : (
            <>
              <Button variant="outline" size="sm" onClick={startEdit}>
                Edit
              </Button>
              <Button variant="destructive" size="sm" onClick={reject}>
                Reject
              </Button>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
