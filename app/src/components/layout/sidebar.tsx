import { NavLink } from 'react-router-dom';
import { Route, BookOpen, Dumbbell, NotebookPen, TrendingUp, ShieldCheck, Menu, CalendarDays, Calendar } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { useState } from 'react';

const navItems = [
  { to: '/today', label: 'Today', icon: CalendarDays },
  { to: '/path', label: 'Path', icon: Route },
  { to: '/library', label: 'Library', icon: BookOpen },
  { to: '/drills', label: 'Drills', icon: Dumbbell },
  { to: '/plan', label: 'Plan', icon: Calendar },
  { to: '/journal', label: 'Journal', icon: NotebookPen },
  { to: '/expectancy', label: 'Expectancy', icon: TrendingUp },
  { to: '/gate', label: 'Gate', icon: ShieldCheck },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1 p-4">
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex w-56 shrink-0 flex-col border-r bg-card">
        <div className="flex h-14 items-center border-b px-4">
          <span className="font-semibold">Neurospect Learn</span>
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
              <span className="font-semibold">Neurospect Learn</span>
            </div>
            <NavLinks onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
      </div>
    </>
  );
}
