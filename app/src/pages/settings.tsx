import { LogOut, RotateCcw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { useSettings } from '@/lib/settings';
import { usePreferences, useUpdatePreferences } from '@/lib/planner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  AppearanceControls,
  MotionControls,
} from '@/components/settings/appearance-controls';
import { PreviewPanel } from '@/components/settings/preview-panel';
import { AvailabilityForm } from '@/components/planner/availability-form';
import { RestDays } from '@/components/planner/rest-days';
import { SuiteLockup } from '@/components/brand/suite-lockup';
import { InstagramIcon } from '@/components/brand/instagram-icon';
import { RebuildButton } from '@/components/settings/rebuild-button';
import type { PreferencesIn } from '@/types/api';

const INSTAGRAM_URL = 'https://instagram.com/chartshooter618';

/**
 * /settings — appearance, motion, study availability, account.
 *
 * Also serves /plan/setup with `initialTab="study"`. That URL is linked from
 * /today and /plan and is exercised by five e2e specs, so it stays a working
 * address rather than becoming a redirect; the Study tab reproduces its
 * behaviour exactly, including returning to /today on save.
 */
export function SettingsPage({
  initialTab = 'appearance',
}: {
  initialTab?: 'appearance' | 'motion' | 'study' | 'account';
}) {
  const { reset } = useSettings();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          How the app looks and moves, when you study, and who you are signed in as.
        </p>
      </div>

      <Tabs defaultValue={initialTab}>
        <TabsList>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="motion">Motion</TabsTrigger>
          <TabsTrigger value="study">Study</TabsTrigger>
          <TabsTrigger value="account">Account</TabsTrigger>
        </TabsList>

        <TabsContent value="appearance" className="space-y-4 pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Design system</CardTitle>
              <CardDescription>
                Applies immediately and is remembered on this device.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <AppearanceControls />
            </CardContent>
          </Card>
          <PreviewPanel />
          <Button variant="outline" size="sm" onClick={reset}>
            <RotateCcw className="mr-1.5 h-4 w-4" /> Reset to defaults
          </Button>
        </TabsContent>

        <TabsContent value="motion" className="pt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Motion</CardTitle>
              <CardDescription>
                Animation is informative here, never decorative — but it is always
                optional.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <MotionControls />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="study" className="pt-4">
          <StudyTab />
        </TabsContent>

        <TabsContent value="account" className="pt-4">
          <AccountTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/**
 * The availability form, moved here from the old /plan/setup page. Reuses the
 * planner components unchanged — no new backend work.
 */
function StudyTab() {
  const prefsQuery = usePreferences();
  const update = useUpdatePreferences();
  const navigate = useNavigate();

  function save(body: PreferencesIn) {
    update.mutate(body, { onSuccess: () => navigate('/today') });
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Availability &amp; preferences</h2>
        <p className="text-sm text-muted-foreground">
          The planner turns your weekly time budget into a concrete, gated daily
          routine.
        </p>
      </div>

      {prefsQuery.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <AvailabilityForm
          defaults={prefsQuery.data}
          onSaved={save}
          isSaving={update.isPending}
          saveError={update.isError ? (update.error as Error).message : null}
        />
      )}

      {/* Declared rest days (E6). Saved on their own, NOT through the preferences
          form above — the form rewrites its whole row on every save, and a rest
          day has to be append-only and timestamped to mean anything. */}
      <RestDays />
    </div>
  );
}

function AccountTab() {
  const { user, logout } = useAuth();

  return (
    <div className="space-y-4">
      {/* Renders only when this page is served from this machine. */}
      <RebuildButton />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3">
            {user?.discord_avatar_url ? (
              <img
                src={user.discord_avatar_url}
                alt=""
                className="h-10 w-10 rounded-full"
              />
            ) : null}
            <div>
              <p className="font-medium">{user?.discord_username ?? 'Signed in'}</p>
              <p className="text-sm text-muted-foreground">
                Discord ID {user?.discord_id}
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={logout}>
            <LogOut className="mr-1.5 h-4 w-4" /> Sign out
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">About</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <SuiteLockup />
          <Separator />
          <p>
            Built by{' '}
            <a
              href={INSTAGRAM_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 font-medium text-primary underline underline-offset-2"
            >
              <InstagramIcon className="h-3.5 w-3.5" />
              @chartShooter618
            </a>
          </p>
          <p>
            Mentorship will run through this platform. Not open yet — it is announced
            here, not available here.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
