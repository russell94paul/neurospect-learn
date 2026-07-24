import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { useAuth } from '@/lib/auth';
import { AppShell } from '@/components/layout/app-shell';
import { LoginPage } from '@/pages/login';
import { AuthCallbackPage } from '@/pages/auth-callback';
import { StubPage } from '@/pages/stub';
import { LibraryPage } from '@/pages/library';
import { ConceptReaderPage } from '@/pages/concept-reader';
import { PathPage } from '@/pages/path';
import { StageDetailPage } from '@/pages/stage-detail';
import { DrillsPage } from '@/pages/drills';
import { TodayPage } from '@/pages/today';
import { PlanPage } from '@/pages/plan';
import { PlanSetupPage } from '@/pages/plan-setup';
import { JournalPage } from '@/pages/journal';
import { JournalEntryPage } from '@/pages/journal-entry';
import { ExpectancyPage } from '@/pages/expectancy';

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
// Every protected route is a stub until its phase lands (5c–5g).
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
        element: <StubPage title="Gate" phase="Phase 5g" />,
      },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
