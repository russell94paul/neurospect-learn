import { useEffect, useRef, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpen,
  Brain,
  CalendarDays,
  Camera,
  ClipboardCheck,
  Dumbbell,
  Lock,
  NotebookPen,
  PlayCircle,
  Route as RouteIcon,
  ShieldCheck,
  Target,
  TrendingUp,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useSettings } from '@/lib/settings';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Logo } from '@/components/brand/logo';
import { Wordmark } from '@/components/brand/wordmark';
import { SuiteLockup } from '@/components/brand/suite-lockup';
import { InstagramIcon } from '@/components/brand/instagram-icon';
import { Reveal } from '@/components/landing/reveal';

const INSTAGRAM_URL = 'https://instagram.com/chartshooter618';

interface CorpusStats {
  concepts: number;
  track_stages: number;
  drills: number;
  content_pages: number;
  rubrics: number;
  rubric_items: number;
}

/**
 * Every feature line here is written from what the code actually does. Nothing
 * on this page claims flashcards, quizzes, video, community, team features or
 * AI tutoring, because none of those exist.
 */
const FEATURES = [
  {
    icon: RouteIcon,
    title: 'The Path',
    body: 'Three graded tracks — Aura, AXL/MrWitness and Unified. Each stage gates the next: hand-marking first, tools second.',
  },
  {
    icon: BookOpen,
    title: 'Library',
    body: 'The course corpus, searchable, with wikilinks resolved as you read. Ingested from the wiki, which stays canonical.',
  },
  {
    icon: Dumbbell,
    title: 'Drills',
    body: 'Both exercise libraries, with hand and tool variants tracked separately and rep counters per drill.',
  },
  {
    icon: Camera,
    title: 'Evidence capture',
    body: 'A rep exists only if a chart backs it. Reps are derived from your uploads and deduplicated by hash — no endpoint can mint one without evidence.',
  },
  {
    icon: ClipboardCheck,
    title: 'Rubrics & self-check',
    body: 'Every drill is checked against its own written bar, projected from the wiki and read-only by design.',
  },
  {
    icon: Lock,
    title: 'Pre-commitment ledger',
    body: 'Call it before you know. Commitments are frozen server-side by a database trigger — no edit, no delete, on purpose.',
  },
  {
    icon: Target,
    title: 'Calibration',
    body: 'Your resolved calls scored against what actually happened, so confidence is measured instead of remembered.',
  },
  {
    icon: CalendarDays,
    title: 'Study planner',
    body: 'Availability in, a deterministic schedule out — gate-aware, with mandatory spaced review, adherence, streaks and pace projection.',
  },
  {
    icon: PlayCircle,
    title: 'Session runner',
    body: 'The Aura protocol — 8 phases, 54 rules — in a narrow window docked beside your platform. Keeps working with the backend down.',
  },
  {
    icon: NotebookPen,
    title: 'Journal',
    body: 'Backtest, live, and the trades you did not take — logged against the model-aligned decision flow, with opportunity cost in R.',
  },
  {
    icon: TrendingUp,
    title: 'Expectancy',
    body: 'Expectancy per entry model, backtest against live, and the full R-distribution.',
  },
  {
    icon: ShieldCheck,
    title: 'The Gate',
    body: 'Am I good enough to live-trade this model yet? Computed from your ladder, your backtest expectancy and four attestations — and not overridable.',
  },
];

const SPINE = ['Learn', 'Drill', 'Prove', 'Predict', 'Journal', 'Measure', 'Gate'];

/** Counts up to `value` once mounted; static when motion is off. */
function CountUp({ value }: { value: number }) {
  const { settings } = useSettings();
  const [n, setN] = useState(value);
  const started = useRef(false);

  useEffect(() => {
    const still =
      settings.motion === 'none' ||
      (typeof matchMedia === 'function' &&
        settings.motion === 'system' &&
        matchMedia('(prefers-reduced-motion: reduce)').matches);
    if (still || started.current) {
      setN(value);
      return;
    }
    started.current = true;
    const DURATION = 900;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / DURATION);
      // easeOutCubic
      setN(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, settings.motion]);

  return <>{n}</>;
}

function StatRow() {
  // Reads the live corpus rather than hard-coding it, so the figures cannot
  // drift from the database at the next re-seed.
  const stats = useQuery({
    queryKey: ['public', 'stats'],
    queryFn: () => api.get('api/stats').json<CorpusStats>(),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  if (!stats.data) return null;
  const s = stats.data;
  const cells = [
    { n: s.concepts, label: 'concepts' },
    { n: s.track_stages, label: 'stages' },
    { n: s.drills, label: 'drills' },
    { n: s.rubrics, label: 'rubrics' },
    { n: s.content_pages, label: 'library pages' },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
      {cells.map((c) => (
        <div key={c.label} className="text-center">
          <div className="text-3xl font-bold tabular-nums text-foreground">
            <CountUp value={c.n} />
          </div>
          <div className="text-xs uppercase tracking-wider text-muted-foreground">
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}

/** `/` — the public front door. */
export function LandingPage() {
  const { token, isLoading } = useAuth();

  // Signed in? This is not the page you want. Straight through to the app.
  if (!isLoading && token) return <Navigate to="/today" replace />;

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-background">
      {/* Brand backdrop */}
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="bg-grid h-[70vh]" />
        <div
          className="bg-glow -top-32 left-[8%] h-[26rem] w-[26rem] opacity-25"
          style={{ background: 'var(--primary)' }}
        />
        <div
          className="bg-glow right-[4%] top-40 h-[22rem] w-[22rem] opacity-20"
          style={{ background: 'var(--brand-2)' }}
        />
      </div>

      <div className="relative mx-auto max-w-5xl px-6 py-10">
        {/* Nav */}
        <header className="flex items-center justify-between">
          <Wordmark />
          <Button asChild size="sm">
            <Link to="/login">Sign in</Link>
          </Button>
        </header>

        {/* Hero */}
        <section className="py-20 sm:py-28">
          <Reveal>
            <Badge variant="info-subtle" className="mb-5">
              ICT / Smart-Money mastery
            </Badge>
            <h1 className="max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
              Evidence,{' '}
              <span className="text-primary">not self-report.</span>
            </h1>
          </Reveal>
          <Reveal delay={90}>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground">
              A learning platform where progress has to be earned. Reps come from
              charts you upload, calls are frozen before the outcome is known, and
              the verdict on whether you are ready to trade live is computed — never
              declared.
            </p>
          </Reveal>
          <Reveal delay={160}>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/login">
                  Sign in with Discord <ArrowRight className="ml-1.5 h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <a href="#features">See what it does</a>
              </Button>
            </div>
          </Reveal>
        </section>

        {/* Stats */}
        <Reveal>
          <Card>
            <CardContent className="py-8">
              <StatRow />
            </CardContent>
          </Card>
        </Reveal>

        {/* The spine */}
        <section className="py-20">
          <Reveal>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              One loop, gated end to end
            </h2>
            <p className="mt-3 max-w-2xl text-muted-foreground">
              Each step has to close before the next one opens. That is the whole
              argument.
            </p>
          </Reveal>
          <Reveal delay={90}>
            <ol className="mt-8 flex flex-wrap items-center gap-2">
              {SPINE.map((step, i) => (
                <li key={step} className="flex items-center gap-2">
                  <span className="rounded-md border bg-card px-3 py-1.5 text-sm font-medium">
                    {step}
                  </span>
                  {i < SPINE.length - 1 && (
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                  )}
                </li>
              ))}
            </ol>
          </Reveal>
        </section>

        {/* Features */}
        <section id="features" className="scroll-mt-8 py-8">
          <Reveal>
            <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Everything in the platform
            </h2>
          </Reveal>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 70}>
                <Card className="h-full transition-[transform,border-color] hover:-translate-y-0.5 hover:border-primary/40">
                  <CardContent className="space-y-2 py-6">
                    <f.icon className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold">{f.title}</h3>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      {f.body}
                    </p>
                  </CardContent>
                </Card>
              </Reveal>
            ))}
          </div>

          <Reveal>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Card>
                <CardContent className="space-y-2 py-6">
                  <h3 className="font-semibold">The honesty strip</h3>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Five signals that watch how you use the app — bulk marking, rep
                    pacing, back-dating, ungraded backlog, flagged grades. Each
                    reports <span className="font-medium text-foreground">not
                    measured</span> rather than a flattering zero.
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="space-y-2 py-6">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    <h3 className="font-semibold">AI second reader</h3>
                    <Badge variant="warning-subtle">Optional</Badge>
                  </div>
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    An advisory vision pass over uploaded charts. It never blocks,
                    never retracts and never writes your ladder — and it is off by
                    default.
                  </p>
                </CardContent>
              </Card>
            </div>
          </Reveal>
        </section>

        {/* Builder */}
        <section className="py-20">
          <Reveal>
            <Card>
              <CardContent className="space-y-4 py-8">
                <div className="flex items-center gap-3">
                  <Logo size="lg" />
                  <div>
                    <h2 className="text-xl font-bold tracking-tight">
                      Built by @chartShooter618
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Funded futures trader · Irish · DJ · boxing
                    </p>
                  </div>
                </div>
                <p className="max-w-2xl leading-relaxed text-muted-foreground">
                  Paul trades futures and posts his chart work publicly. This
                  platform is the part that is harder to see: a system built by a
                  trader who wanted something that would refuse to let him fool
                  himself. Reps that cannot be minted without a chart. Predictions
                  that cannot be edited once the market has spoken. A gate with no
                  override switch. The discipline is designed in, so it does not
                  have to be remembered.
                </p>
                <div className="flex flex-wrap items-center gap-3">
                  <Button asChild variant="outline" size="sm">
                    <a href={INSTAGRAM_URL} target="_blank" rel="noreferrer noopener">
                      <InstagramIcon className="mr-1.5 h-4 w-4" /> @chartShooter618
                    </a>
                  </Button>
                  <Badge variant="info-subtle">Mentorship — coming</Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Mentorship will run through this platform. It is announced here,
                  not open yet.
                </p>
              </CardContent>
            </Card>
          </Reveal>
        </section>

        {/* Footer */}
        <footer className="flex flex-col gap-4 border-t py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <Wordmark size="sm" />
            <SuiteLockup />
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <a
              href={INSTAGRAM_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 hover:text-foreground"
            >
              <InstagramIcon className="h-4 w-4" /> @chartShooter618
            </a>
            <Link to="/login" className="hover:text-foreground">
              Sign in
            </Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
