import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { AppShell } from '@/components/layout/app-shell';
import { LoginPage } from '@/pages/login';
import { AuthCallbackPage } from '@/pages/auth-callback';
import { LibraryPage } from '@/pages/library';
import { ConceptReaderPage } from '@/pages/concept-reader';
import { PathPage } from '@/pages/path';
import { StageDetailPage } from '@/pages/stage-detail';
import { DrillsPage } from '@/pages/drills';
import { TodayPage } from '@/pages/today';
import { RunnerPage } from '@/pages/runner';
import { PlanPage } from '@/pages/plan';
import { JournalPage } from '@/pages/journal';
import { JournalEntryPage } from '@/pages/journal-entry';
import { MissedTradeEntryPage } from '@/pages/missed-trade-entry';
import { ExpectancyPage } from '@/pages/expectancy';
import { GatePage } from '@/pages/gate';
import { SettingsPage } from '@/pages/settings';
import { LandingPage } from '@/pages/landing';

// ============================================================
// Protected layout — redirects to /login if not authenticated
// ============================================================

function ProtectedLayout() {
  const { token, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <AppShell />;
}

// ============================================================
// Router — route taxonomy per learning-platform.md §Route taxonomy.
// Fully implemented as of Phase 5g: no route is a stub any more.
// ============================================================

const router = createBrowserRouter([
  // The public front door. Signed-in visitors are sent straight into the app;
  // signed-out ones get the overview instead of a bare auth card.
  {
    path: '/',
    element: <LandingPage />,
  },
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/auth/callback',
    element: <AuthCallbackPage />,
  },
  {
    element: <ProtectedLayout />,
    children: [
      {
        path: '/path',
        element: <PathPage />,
      },
      {
        path: '/path/:track/:stage',
        element: <StageDetailPage />,
      },
      {
        path: '/library',
        element: <LibraryPage />,
      },
      {
        path: '/concepts/:slug',
        element: <ConceptReaderPage />,
      },
      {
        path: '/drills',
        element: <DrillsPage />,
      },
      {
        path: '/today',
        element: <TodayPage />,
      },
      // S1 — the Aura session runner. A new TOP-LEVEL section on purpose: every
      // other page is a dashboard you read, this is a protocol you work, live,
      // in a narrow window docked beside Tradezella.
      {
        path: '/runner',
        element: <RunnerPage />,
      },
      {
        path: '/plan',
        element: <PlanPage />,
      },
      // Availability moved into Settings → Study. This URL stays a real address
      // rather than a redirect: it is linked from /today and /plan, may be
      // bookmarked, and five e2e specs drive it.
      {
        path: '/plan/setup',
        element: <SettingsPage initialTab="study" />,
      },
      {
        path: '/journal',
        element: <JournalPage />,
      },
      {
        path: '/journal/new',
        element: <JournalEntryPage />,
      },
      // The missed/canceled log (6b) lives under /journal — same journaling
      // surface, separate record type. Two static segments, so these rank above
      // the single-segment /journal/:id below.
      {
        path: '/journal/missed/new',
        element: <MissedTradeEntryPage />,
      },
      {
        path: '/journal/missed/:id',
        element: <MissedTradeEntryPage />,
      },
      {
        path: '/journal/:id',
        element: <JournalEntryPage />,
      },
      {
        path: '/expectancy',
        element: <ExpectancyPage />,
      },
      {
        path: '/gate',
        element: <GatePage />,
      },
      {
        path: '/settings',
        element: <SettingsPage />,
      },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
