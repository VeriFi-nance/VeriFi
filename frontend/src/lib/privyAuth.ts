import type { ConnectedWallet } from '@privy-io/react-auth';
import { setAuthMethod } from './auth';
import { setPrivySigner } from './privySigner';
import { authenticateWithEIP1193Provider } from './walletAuth';
import type { EIP1193Provider } from './walletAuth';

export function findPrivyEmbeddedWallet(
  wallets: ConnectedWallet[],
): ConnectedWallet | undefined {
  return wallets.find((w) => w.walletClientType === 'privy');
}

export function isPrivyConfigured(): boolean {
  return Boolean(import.meta.env.VITE_PRIVY_APP_ID);
}

export async function registerPrivySignerFromWallet(
  wallet: ConnectedWallet,
): Promise<void> {
  const provider = (await wallet.getEthereumProvider()) as EIP1193Provider;
  setPrivySigner(async (payloadHex, address) => {
    const signature = await provider.request({
      method: 'personal_sign',
      params: [payloadHex, address],
    });
    return signature as string;
  });
}

/** Complete VeriFi backend auth using a Privy embedded wallet. */
export async function syncPrivyWalletToVerifi(wallet: ConnectedWallet): Promise<string> {
  const provider = await wallet.getEthereumProvider();
  const address = await authenticateWithEIP1193Provider(provider, wallet.address, 'privy');
  setAuthMethod('privy');
  await registerPrivySignerFromWallet(wallet);
  return address;
}
