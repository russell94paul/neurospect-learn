import { Link, Outlet } from 'react-router-dom';
import { Settings as SettingsIcon } from 'lucide-react';
import { Sidebar } from '@/components/layout/sidebar';
import { UserMenu } from '@/components/layout/user-menu';
import { ThemeToggle } from '@/components/settings/theme-toggle';
import { Button } from '@/components/ui/button';

export function AppShell() {
  return (
    <div className="relative flex h-screen overflow-hidden">
      {/* A single low-opacity brand orb, so the app reads as the same product as
          the landing page without competing with the dense data pages. */}
      <div
        aria-hidden
        className="bg-glow -top-40 left-1/3 h-96 w-96 opacity-[0.07]"
        style={{ background: 'var(--primary)' }}
      />
      <Sidebar />
      <div className="relative flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 shrink-0 items-center justify-end gap-1 border-b bg-card px-4">
          <ThemeToggle />
          <Button variant="ghost" size="icon" asChild aria-label="Settings">
            <Link to="/settings">
              <SettingsIcon className="h-4 w-4" />
            </Link>
          </Button>
          <UserMenu />
        </header>
        {/* Main content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
