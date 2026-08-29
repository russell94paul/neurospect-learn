import { NavLink } from 'react-router-dom';
import {
  Route,
  BookOpen,
  Dumbbell,
  NotebookPen,
  TrendingUp,
  ShieldCheck,
  Menu,
  CalendarDays,
  Calendar,
  PlayCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Wordmark } from '@/components/brand/wordmark';
import { useState } from 'react';

/**
 * Grouped by what you are DOING, not by feature name: the work you do today,
 * the material you learn from, the record you review afterwards, and the verdict
 * that gates going live. Runner sits directly under Today because it is the
 * screen you open to do the work, not one you open to read about it.
 */
const navGroups: { label: string; items: { to: string; label: string; icon: typeof Route }[] }[] = [
  {
    label: 'Do',
    items: [
      { to: '/today', label: 'Today', icon: CalendarDays },
      { to: '/runner', label: 'Runner', icon: PlayCircle },
    ],
  },
  {
    label: 'Learn',
    items: [
      { to: '/path', label: 'Path', icon: Route },
      { to: '/library', label: 'Library', icon: BookOpen },
      { to: '/drills', label: 'Drills', icon: Dumbbell },
    ],
  },
  {
    label: 'Review',
    items: [
      { to: '/plan', label: 'Plan', icon: Calendar },
      { to: '/journal', label: 'Journal', icon: NotebookPen },
      { to: '/expectancy', label: 'Expectancy', icon: TrendingUp },
    ],
  },
  {
    label: 'Verdict',
    items: [{ to: '/gate', label: 'Gate', icon: ShieldCheck }],
  },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-4 p-4">
      {navGroups.map((group) => (
        <div key={group.label} className="flex flex-col gap-1">
          <span className="px-3 pb-1 text-[0.6875rem] font-semibold uppercase tracking-wider text-muted-foreground/70">
            {group.label}
          </span>
          {group.items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                )
              }
            >
              {({ isActive }) => (
                <>
                  {/* The active rail. Animates in with the theme's motion level. */}
                  <span
                    aria-hidden
                    className={cn(
                      'absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary transition-all',
                      isActive ? 'opacity-100' : 'scale-y-0 opacity-0'
                    )}
                  />
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="relative hidden w-56 shrink-0 flex-col border-r bg-card md:flex">
        <div className="flex h-14 items-center border-b px-4">
          <Wordmark size="sm" />
        </div>
        <NavLinks />
      </aside>

      {/* Mobile hamburger + Sheet */}
      <div className="md:hidden">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="m-2">
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-56 p-0">
            <div className="flex h-14 items-center border-b px-4">
              <Wordmark size="sm" />
            </div>
            <NavLinks onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
