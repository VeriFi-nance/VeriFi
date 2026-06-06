import { PrivyProvider } from '@privy-io/react-auth';
import { isPrivyConfigured } from '@/lib/privyAuth';

interface PrivyAppProviderProps {
  children: React.ReactNode;
}

export function PrivyAppProvider({ children }: PrivyAppProviderProps) {
  const appId = import.meta.env.VITE_PRIVY_APP_ID;
  if (!isPrivyConfigured() || !appId) {
    return children;
  }

  return (
    <PrivyProvider
      appId={appId}
      config={{
        loginMethods: ['google'],
        embeddedWallets: {
          ethereum: { createOnLogin: 'users-without-wallets' },
          showWalletUIs: false,
        },
        appearance: { theme: 'light' },
      }}
    >
      {children}
    </PrivyProvider>
  );
}
