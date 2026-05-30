import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
import { LoginForm } from '@/components/LoginForm';
import { closeLogin, loginReturnTo } from '@/lib/auth';

export function LoginModal() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const returnTo = loginReturnTo(searchParams);

  function dismiss() {
    closeLogin(navigate, location);
  }

  function handleSuccess() {
    navigate(returnTo, { replace: true });
  }

  return (
    <Dialog open onOpenChange={(open) => !open && dismiss()}>
      <DialogContent className="max-w-md max-h-[min(90dvh,720px)] overflow-y-auto p-6">
        <DialogTitle className="sr-only">Sign in to VeriFi</DialogTitle>
        <DialogDescription className="sr-only">
          Create or restore your wallet to post, stake, and participate.
        </DialogDescription>
        <LoginForm onSuccess={handleSuccess} />
      </DialogContent>
    </Dialog>
  );
}
