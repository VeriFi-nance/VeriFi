import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { CheckCircle2, XCircle, UploadCloud } from 'lucide-react';
import { verifyProofSignature, buildClaimPayload } from '@/lib/crypto';
import type { ProofBundle } from '@/lib/types';
import { truncateAddress } from '@/lib/wallet';

export function VerifyPage() {
  const [proof, setProof] = useState<ProofBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isValid, setIsValid] = useState<boolean | null>(null);

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
      const payloadStr = buildClaimPayload(parsed.payload as any);
      
      const valid = verifyProofSignature(payloadStr, parsed.signature, parsed.wallet_address);
      setIsValid(valid);

    } catch (err: any) {
      setError(err.message || 'Failed to parse JSON');
    }
    
    // Reset input
    e.target.value = '';
  };

  return (
    <div className="container max-w-2xl mx-auto py-12 px-4 space-y-6">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Verify Cryptographic Proof</h1>
        <p className="text-muted-foreground">Upload a downloaded proof file to independently verify its authenticity.</p>
      </div>

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
              <div>
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
            
            <div className="space-y-2 pt-2 border-t">
              <Label className="text-muted-foreground">Signed Payload</Label>
              <pre className="bg-muted p-3 rounded-md text-xs font-mono overflow-auto">
                {JSON.stringify(proof.payload, null, 2)}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
