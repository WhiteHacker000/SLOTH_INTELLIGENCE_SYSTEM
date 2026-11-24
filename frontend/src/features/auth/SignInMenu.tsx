import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { AuthStatus } from "@/types/api";

interface Props {
  auth: AuthStatus;
  onSignedOut: () => void;
}

/** A sign-in link, or the signed-in user with a way to sign out. */
export function SignInMenu({ auth, onSignedOut }: Props) {
  if (!auth.sign_in_enabled) return null;

  if (!auth.user) {
    return (
      <a
        href="/api/v1/auth/login"
        className="inline-flex items-center rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white hover:bg-slate-700"
      >
        Sign in with GitHub
      </a>
    );
  }

  async function signOut() {
    await api("/auth/logout", {}).catch(() => undefined);
    onSignedOut();
  }

  return (
    <div className="flex items-center gap-3">
      {auth.user.avatar_url && (
        <img src={auth.user.avatar_url} alt="" className="h-8 w-8 rounded-full" />
      )}
      <span className="text-sm font-medium text-slate-800">{auth.user.login}</span>
      <Button variant="secondary" onClick={signOut}>
        Sign out
      </Button>
    </div>
  );
}
