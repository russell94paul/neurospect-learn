import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader } from '@/components/ui/card';
import { Wordmark } from '@/components/brand/wordmark';
import { Separator } from '@/components/ui/separator';

export function LoginPage() {
  const { login, debugLogin } = useAuth();
  const navigate = useNavigate();
  const [discordId, setDiscordId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasDiscordClientId = Boolean(import.meta.env.VITE_DISCORD_CLIENT_ID);
  const isDebug = import.meta.env.VITE_DEBUG === 'true';

  const handleDebugLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!discordId.trim()) return;
    setIsLoading(true);
    setError(null);
    try {
      await debugLogin(discordId.trim());
      navigate('/path', { replace: true });
    } catch (err) {
      setError('Debug login failed. Is the backend running with DEBUG=true?');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <div className="bg-grid" />
        <div
          className="bg-glow left-1/2 top-0 h-96 w-96 -translate-x-1/2 opacity-25"
          style={{ background: 'var(--primary)' }}
        />
      </div>
      <Card className="relative w-full max-w-sm">
        <CardHeader className="items-center text-center">
          <Wordmark size="lg" />
          <CardDescription className="pt-1">
            Evidence-gated ICT mastery — course, drills, journal &amp; gate
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {hasDiscordClientId && (
            <Button onClick={login} className="w-full">
              Sign in with Discord
            </Button>
          )}

          {hasDiscordClientId && isDebug && <Separator />}

          {isDebug && (
            <form onSubmit={handleDebugLogin} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="discord-id">Debug Login</Label>
                <Input
                  id="discord-id"
                  placeholder="Enter any Discord ID"
                  value={discordId}
                  onChange={(e) => setDiscordId(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" variant="outline" disabled={isLoading || !discordId.trim()}>
                {isLoading ? 'Logging in…' : 'Debug Login'}
              </Button>
            </form>
          )}

          {!hasDiscordClientId && !isDebug && (
            <p className="text-center text-sm text-muted-foreground">
              No login method configured. Set VITE_DISCORD_CLIENT_ID or VITE_DEBUG=true.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
