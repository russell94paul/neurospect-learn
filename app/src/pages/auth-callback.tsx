import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import type { TokenResponse } from '@/types/api';

export function AuthCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      setError('No authorization code received from Discord.');
      return;
    }

    const redirectUri =
      import.meta.env.VITE_DISCORD_REDIRECT_URI ?? 'http://localhost:5173/auth/callback';

    api
      .post('auth/discord/token', { json: { code, redirect_uri: redirectUri } })
      .json<TokenResponse>()
      .then(async (data) => {
        await setToken(data.access_token);
        navigate('/path', { replace: true });
      })
      .catch(() => {
        setError('Authentication failed. Please try again.');
      });
  }, []); // run once on mount

  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4">
        <p className="text-destructive">{error}</p>
        <Link to="/login" className="text-sm underline">
          Back to login
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <p className="text-muted-foreground">Completing sign-in…</p>
    </div>
  );
}
