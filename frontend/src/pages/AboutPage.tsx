import { lazy, Suspense } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Info, KeyRound, Layers, ShieldCheck, Loader2 } from 'lucide-react';
import { RepIcon } from '@/components/RepIcon';

const RepScoreSim = lazy(() => import('@/components/info/RepScoreSim'));

function CryptoRow({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border p-3 sm:p-4">
      <div className="font-medium text-foreground text-sm mb-1">{title}</div>
      <div className="text-xs text-muted-foreground leading-relaxed break-words [&_code]:break-all">
        {children}
      </div>
    </div>
  );
}

export default function AboutPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = ['about', 'crypto', 'rep', 'stack'].includes(searchParams.get('tab') ?? '')
    ? searchParams.get('tab')!
    : 'about';

  const handleTabChange = (tab: string) => {
    setSearchParams(tab === 'about' ? {} : { tab });
  };

  return (
    <div className="mx-auto w-full max-w-3xl">
      <Card className="overflow-hidden">
        <CardHeader className="border-b px-4 py-4 sm:px-6">
          <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
            <Info className="size-5 shrink-0 text-primary" /> About VeriFi
          </CardTitle>
          <CardDescription className="text-sm leading-relaxed">
            Verifiable finance predictions — how the project works under the hood.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-4 pt-4 sm:px-6">
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <div className="-mx-1 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:mx-0 sm:overflow-visible">
              <TabsList className="inline-flex h-auto w-max min-w-full justify-start gap-0.5 p-1 sm:w-full sm:flex-wrap">
                <TabsTrigger value="about" className="shrink-0 flex-none gap-1 px-2.5 text-xs sm:flex-1 sm:px-3 sm:text-sm">
                  <ShieldCheck className="size-3.5" /> About
                </TabsTrigger>
                <TabsTrigger value="crypto" className="shrink-0 flex-none gap-1 px-2.5 text-xs sm:flex-1 sm:px-3 sm:text-sm">
                  <KeyRound className="size-3.5" /> Cryptography
                </TabsTrigger>
                <TabsTrigger value="rep" className="shrink-0 flex-none gap-1 px-2.5 text-xs sm:flex-1 sm:px-3 sm:text-sm">
                  <RepIcon size="xs" /> Rep Score
                </TabsTrigger>
                <TabsTrigger value="stack" className="shrink-0 flex-none gap-1 px-2.5 text-xs sm:flex-1 sm:px-3 sm:text-sm">
                  <Layers className="size-3.5" /> Stack
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="pt-4">
              {/* About */}
              <TabsContent value="about" className="space-y-3 text-sm text-muted-foreground leading-relaxed">
                <p>
                  <strong className="text-foreground">VeriFi</strong> turns finance predictions into accountable,
                  on-chain-style claims. Anyone can post a <strong className="text-foreground">hard claim</strong> — an
                  asset, a direction, a target, and a deadline — which is cryptographically signed at the moment it's made.
                </p>
                <p>
                  Each claim opens a YES/NO <strong className="text-foreground">prediction market</strong>. The crowd stakes
                  Reputation; an automated <strong className="text-foreground">oracle</strong> resolves it against real
                  market data at the deadline. Winners gain Rep, so a user's track record can't be faked or cherry-picked.
                </p>
                <p>
                  Every resolved claim produces a downloadable <strong className="text-foreground">proof bundle</strong> that
                  anyone can verify independently — no need to trust VeriFi's servers.
                </p>
              </TabsContent>

              {/* Cryptography */}
              <TabsContent value="crypto" className="space-y-2.5">
                <p className="text-xs text-muted-foreground">
                  Accounts are real wallets, not username/password rows. Keys are generated and used entirely client-side.
                </p>
                <CryptoRow title="Key generation — BIP39 / BIP32">
                  A 12-word mnemonic (<code className="text-foreground">@scure/bip39</code>) seeds a BIP32 HD wallet
                  (<code className="text-foreground">@scure/bip32</code>). The private key never leaves the browser.
                </CryptoRow>
                <CryptoRow title="Addresses — secp256k1 + keccak256">
                  The public key comes from secp256k1 (<code className="text-foreground">@noble/secp256k1</code>); the
                  Ethereum-style address is the last 20 bytes of <code className="text-foreground">keccak256</code> of the
                  uncompressed key.
                </CryptoRow>
                <CryptoRow title="Login — EIP-191 challenge / response">
                  The server issues a random nonce. The client signs it with EIP-191{' '}
                  <code className="text-foreground">personal_sign</code> (<code className="text-foreground">\x19Ethereum
                  Signed Message</code> prefix → keccak256 → ECDSA). The backend recovers the address with{' '}
                  <code className="text-foreground">eth_account</code> and issues a JWT — no password ever transmitted.
                </CryptoRow>
                <CryptoRow title="Key storage — AES-256-GCM + PBKDF2">
                  The private key is encrypted with AES-256-GCM, keyed by PBKDF2-SHA256 (100k iterations) over the user's
                  passphrase, via the Web Crypto API. Only the ciphertext, salt and IV live in localStorage.
                </CryptoRow>
                <CryptoRow title="Claim proofs — signed payloads">
                  Each claim and position is signed and bundled with the server timestamp and reference price, so anyone can
                  re-verify the signature and the outcome offline.
                </CryptoRow>
                <CryptoRow title="Also supported">
                  MetaMask (browser wallet) and Privy (embedded/social) authenticate through the same EIP-191 signature flow.
                </CryptoRow>
              </TabsContent>

              {/* Rep Score */}
              <TabsContent value="rep">
                <Suspense
                  fallback={
                    <div className="flex items-center justify-center py-10 text-muted-foreground">
                      <Loader2 className="size-5 animate-spin" />
                    </div>
                  }
                >
                  <RepScoreSim />
                </Suspense>
              </TabsContent>

              {/* Stack */}
              <TabsContent value="stack" className="space-y-2.5 text-sm">
                <CryptoRow title="Frontend">
                  Vite + React 19 + TypeScript, Tailwind CSS v4, shadcn/ui, React Router. Deployed on Vercel.
                </CryptoRow>
                <CryptoRow title="Backend">
                  Django 6 + Django REST Framework, SimpleJWT auth, <code className="text-foreground">eth-account</code> for
                  signature recovery. Managed with uv, served by gunicorn on Render.
                </CryptoRow>
                <CryptoRow title="Markets & oracle">
                  A constant-product (CPMM) reputation market per claim, plus a scheduled oracle job that fetches OHLC price
                  data to resolve claims automatically.
                </CryptoRow>
                <CryptoRow title="Crypto libraries">
                  <code className="text-foreground">@noble/secp256k1</code>, <code className="text-foreground">@noble/hashes</code>,{' '}
                  <code className="text-foreground">@scure/bip39</code>, <code className="text-foreground">@scure/bip32</code>,
                  Web Crypto API.
                </CryptoRow>
              </TabsContent>
            </div>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
