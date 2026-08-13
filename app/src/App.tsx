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
import { PlanSetupPage } from '@/pages/plan-setup';
import { JournalPage } from '@/pages/journal';
import { JournalEntryPage } from '@/pages/journal-entry';
import { MissedTradeEntryPage } from '@/pages/missed-trade-entry';
import { ExpectancyPage } from '@/pages/expectancy';
import { GatePage } from '@/pages/gate';

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
        index: true,
        element: <Navigate to="/path" replace />,
      },
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
      {
        path: '/plan/setup',
        element: <PlanSetupPage />,
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
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
