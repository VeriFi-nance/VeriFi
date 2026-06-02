import { useState, useEffect, lazy, Suspense } from 'react';
import { useParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { CheckCircle2, XCircle, UploadCloud, ChevronDown, ChevronUp, Share2, Copy, Check, Loader2 } from 'lucide-react';
import { verifyProofSignature, buildClaimPayload, buildPositionPayload } from '@/lib/crypto';
import type { ProofBundle, ClaimChartData } from '@/lib/types';
import { truncateAddress } from '@/lib/wallet';
import { ClaimRow } from '@/components/feed/composer/ClaimRow';
import { getClaimChartData, getClaimProof, getPositionProof, getClaimOG, getPositionOG } from '@/lib/api';

const PriceChart = lazy(() =>
  import('@/components/feed/PriceChart').then((m) => ({ default: m.PriceChart }))
);

function buildSummaryText(proof: ProofBundle): string {
  const author = (proof.payload as any).author_username;
  const authorPrefix = author ? `@${author} predicts` : 'Predicts';
  const asset = String(proof.payload.asset_symbol || '');
  const direction = String(proof.payload.direction).toLowerCase();
  const verb = direction === 'bullish' ? 'rises' : 'falls';
  const pct = String(proof.payload.percentage || '');
  const until = new Date(String(proof.payload.until || '')).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  return `${authorPrefix} ${asset} ${verb} ${pct}% by ${until}`;
}

export function VerifyPage({ type }: { type?: 'claim' | 'position' }) {
  const { id: routeIdParam } = useParams<{ id?: string }>();
  const [proof, setProof] = useState<ProofBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isValid, setIsValid] = useState<boolean | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [chartData, setChartData] = useState<ClaimChartData | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [autoLoading, setAutoLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);

  // Auto-fetch proof when navigating to /verify/claim/:id or /verify/position/:id
  useEffect(() => {
    if (!routeIdParam || !type) return;
    const targetId = parseInt(routeIdParam, 10);
    if (isNaN(targetId)) {
      setError('Invalid ID.');
      return;
    }

    setAutoLoading(true);
    setError(null);
    setProof(null);
    setIsValid(null);

    const fetchProof = type === 'position' ? getPositionProof : getClaimProof;

    fetchProof(targetId)
      .then((parsed) => {
        if (!parsed.signature || !parsed.payload || !parsed.wallet_address) {
          throw new Error('Invalid proof data from server.');
        }
        setProof(parsed);
        const payloadStr = type === 'position' 
          ? buildPositionPayload(parsed.payload as any)
          : buildClaimPayload(parsed.payload as any);
        const valid = verifyProofSignature(payloadStr, parsed.signature, parsed.wallet_address);
        setIsValid(valid);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load proof.');
      })
      .finally(() => setAutoLoading(false));
  }, [routeIdParam, type]);

  // Fetch chart and live status when proof is verified
  useEffect(() => {
    if (!proof || !isValid) {
      setChartData(null);
      setLiveStatus(null);
      return;
    }

    if (proof.type === 'claim' && proof.claim_id) {
      setChartLoading(true);
      setChartError(null);
      getClaimChartData(proof.claim_id)
        .then(setChartData)
        .catch(err => setChartError(err.message || 'Failed to load chart data.'))
        .finally(() => setChartLoading(false));
      
      getClaimOG(proof.claim_id)
        .then(og => setLiveStatus(og.status))
        .catch(() => setLiveStatus(null));
    } else if (proof.type === 'position' && proof.position_id) {
      setChartData(null);
      getPositionOG(proof.position_id)
        .then(og => setLiveStatus(og.status))
        .catch(() => setLiveStatus(null));
    } else {
      setChartData(null);
      setLiveStatus(null);
    }
  }, [proof, isValid]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError(null);
    setProof(null);
    setIsValid(null);

    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as ProofBundle;
      
      if (!parsed.signature || !parsed.payload || !parsed.wallet_address) {
        throw new Error('Invalid proof file format');
      }

      setProof(parsed);
      
      // Rebuild canonical string to verify
      const payloadStr = parsed.type === 'position'
        ? buildPositionPayload(parsed.payload as any)
        : buildClaimPayload(parsed.payload as any);
      
      const valid = verifyProofSignature(payloadStr, parsed.signature, parsed.wallet_address);
      setIsValid(valid);

    } catch (err: any) {
      setError(err.message || 'Failed to parse JSON');
    }
    
    // Reset input
    e.target.value = '';
  };

  const getShareableUrl = () => {
    if (proof?.claim_id) {
      return `${window.location.origin}/verify/claim/${proof.claim_id}`;
    }
    if (proof?.position_id) {
      return `${window.location.origin}/verify/position/${proof.position_id}`;
    }
    return window.location.href;
  };

  const handleShareTwitter = () => {
    if (!proof) return;
    const summary = buildSummaryText(proof);
    const statusEmoji = isValid ? '✅' : '❌';
    const text = `${statusEmoji} Cryptographically verified on VeriFi: ${summary}.\n\nVerify the proof yourself:`;
    const url = getShareableUrl();
    window.open(
      `https://x.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`,
      '_blank',
      'noopener,noreferrer'
    );
  };

  const handleCopyLink = async () => {
    const url = getShareableUrl();
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
      const input = document.createElement('input');
      input.value = url;
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="container max-w-2xl mx-auto py-12 px-4 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Verify Cryptographic Proof</h1>
        <p className="text-muted-foreground">
          {routeIdParam
            ? `Verifying the cryptographic signature of this ${type}.`
            : 'Upload a downloaded proof file to independently verify its authenticity.'}
        </p>
      </div>

      {/* Auto-loading state */}
      {autoLoading && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center p-12 text-center">
              <Loader2 className="size-10 text-muted-foreground mb-4 animate-spin" />
              <h3 className="text-lg font-semibold mb-1">Loading Proof</h3>
              <p className="text-sm text-muted-foreground">Fetching and verifying {type} #{routeIdParam}…</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* File upload — only show when not in shareable URL mode */}
      {!routeIdParam && !autoLoading && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-border rounded-lg p-12 text-center hover:bg-muted/50 transition-colors">
              <UploadCloud className="size-10 text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-1">Upload Proof JSON</h3>
              <p className="text-sm text-muted-foreground mb-4">Drag and drop or click to select</p>
              <div className="relative">
                <Input 
                  type="file" 
                  accept=".json" 
                  onChange={handleFileUpload} 
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <Button variant="outline">Select File</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Alert variant="destructive">
          <XCircle className="size-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {proof && isValid !== null && (
        <Card className={isValid ? 'border-success/50 bg-success/5' : 'border-destructive/50 bg-destructive/5'}>
          <CardHeader>
            <div className="flex items-center gap-2">
              {isValid ? <CheckCircle2 className="size-6 text-success" /> : <XCircle className="size-6 text-destructive" />}
              <div className="flex-1">
                <CardTitle className={isValid ? 'text-success' : 'text-destructive'}>
                  {isValid ? 'Signature Verified' : 'Invalid Signature'}
                </CardTitle>
                <CardDescription>
                  {isValid 
                    ? 'The payload was mathematically proven to be signed by the provided wallet address.' 
                    : 'The signature does not match the payload or wallet address. This file may have been tampered with.'}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-1">
                <Label className="text-muted-foreground">Signer Address</Label>
                <div className="font-mono">{truncateAddress(proof.wallet_address)}</div>
              </div>
              {(proof.payload as any).author_username && (
                <div className="space-y-1">
                  <Label className="text-muted-foreground">Author Username</Label>
                  <div className="font-medium">@{(proof.payload as any).author_username}</div>
                </div>
              )}
              <div className="space-y-1">
                <Label className="text-muted-foreground">Proof Type</Label>
                <div className="capitalize">{proof.type || 'Unknown'}</div>
              </div>
              <div className="space-y-1">
                <Label className="text-muted-foreground">Server Timestamp</Label>
                <div>{new Date(proof.server_timestamp).toLocaleString()}</div>
              </div>
            </div>
            
            <div className="space-y-4 pt-4 border-t">
              <div className="flex items-center justify-between">
                <Label className="text-muted-foreground">Proof Details</Label>
                {liveStatus && (
                  <Badge variant={
                    liveStatus.toLowerCase() === 'confirmed' || liveStatus.toLowerCase() === 'won' ? 'success' :
                    liveStatus.toLowerCase() === 'rejected' || liveStatus.toLowerCase() === 'lost' || liveStatus.toLowerCase() === 'missed' ? 'destructive' :
                    'secondary'
                  } className="uppercase text-[10px]">
                    Current Status: {liveStatus}
                  </Badge>
                )}
              </div>
              {proof.type === 'claim' ? (
                <div className="mb-2 space-y-3">
                  <div className="text-sm font-medium">
                    {buildSummaryText(proof)}{' '}
                    (at {new Date(String(proof.payload.created_at || proof.server_timestamp)).toLocaleDateString()})
                  </div>
                  <ClaimRow
                    assetSymbol={String(proof.payload.asset_symbol || '')}
                    direction={String(proof.payload.direction || 'bullish') as any}
                    percentage={String(proof.payload.percentage || '')}
                    until={String(proof.payload.until || '')}
                  />
                  {chartLoading && <div className="text-sm text-muted-foreground animate-pulse text-center p-4">Loading chart…</div>}
                  {chartError && <div className="text-sm text-amber-500 text-center p-4">Could not load chart: {chartError}</div>}
                  {!chartLoading && !chartError && !chartData && !proof.claim_id && (
                    <div className="text-sm text-muted-foreground text-center p-4 border border-dashed rounded-md bg-muted/20">
                      Chart data is unavailable for this offline proof.
                    </div>
                  )}
                  {chartData && chartData.ohlc.length > 0 && (
                    <div className="mt-4 pt-2">
                      <Suspense fallback={null}>
                        <PriceChart data={chartData} />
                      </Suspense>
                    </div>
                  )}
                </div>
              ) : proof.type === 'position' ? (
                <div className="grid grid-cols-3 gap-2 text-sm bg-muted/30 rounded-lg p-3 border border-border mb-2">
                  <div className="col-span-3 flex items-center justify-between mb-2">
                    <Badge variant="outline" className="text-sm font-bold bg-muted/50">
                      {String(proof.payload.asset_symbol || 'Unknown')}
                    </Badge>
                    <Badge variant={String(proof.payload.direction).toLowerCase() === 'long' ? 'success' : 'destructive'} className="uppercase">
                      {String(proof.payload.direction || '')}
                    </Badge>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[10px] uppercase tracking-wider">Entry Price</div>
                    <div className="font-mono font-medium">${Number(proof.payload.entry_price || 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[10px] uppercase tracking-wider">Stop Loss</div>
                    <div className="font-mono text-danger font-medium">${Number(proof.payload.stop_loss || 0).toLocaleString()}</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground text-[10px] uppercase tracking-wider">Take Profit</div>
                    <div className="font-mono text-success font-medium">${Number(proof.payload.take_profit || 0).toLocaleString()}</div>
                  </div>
                </div>
              ) : null}

              <div>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="w-full flex justify-between items-center text-xs text-muted-foreground"
                  onClick={() => setShowJson(!showJson)}
                >
                  <span>{showJson ? 'Hide' : 'Show'} Raw JSON Payload</span>
                  {showJson ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </Button>
                
                {showJson && (
                  <pre className="bg-muted p-3 rounded-md text-xs font-mono overflow-auto mt-2 border border-border">
                    {JSON.stringify(proof.payload, null, 2)}
                  </pre>
                )}
              </div>
            </div>

            {/* Share buttons */}
            {isValid && (
              <div className="flex gap-2 pt-4 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={handleShareTwitter}
                >
                  <Share2 className="size-4 mr-2" />
                  Share on X
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={handleCopyLink}
                >
                  {copied ? <Check className="size-4 mr-2 text-success" /> : <Copy className="size-4 mr-2" />}
                  {copied ? 'Copied!' : 'Copy Link'}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
