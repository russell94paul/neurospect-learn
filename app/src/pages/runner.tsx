import { useState } from 'react';
import { ChevronLeft, ChevronRight, HandMetal, Plus, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PhaseCard } from '@/components/runner/phase-card';
import { SessionPanel, TradezellaPaste } from '@/components/runner/session-panel';
import { OpenFlags, ReferenceSections } from '@/components/runner/reference';
import { runnerData, spanOf, useRunnerState } from '@/lib/runner';
import { cn } from '@/lib/utils';

/**
 * /runner — the Aura session runner (Phase S1).
 *
 * A screen to keep open BESIDE Tradezella and follow, start to finish, every
 * session. Not a dashboard you read: a protocol you work.
 *
 * Design constraints, all load-bearing:
 *  - Narrow viewport is the PRIMARY target (~a third of a screen), not an
 *    afterthought. Single column throughout; wide content scrolls in its own box.
 *  - Content is PROJECTED from the wiki, never authored here.
 *  - Writes nothing to the database. Step state is localStorage, by design.
 */
export function RunnerPage() {
  const { state, patch, toggle, setupCount, addSetup, dayDate, reset } = useRunnerState();
  const [openPhase, setOpenPhase] = useState<number | null>(0);

  const phases = runnerData.checklist.phases;
  const span = spanOf(state.span);
  const declared = Boolean(state.startDate);
  const dayDone = dayDate ? state.daysDone.includes(dayDate) : false;
  const stoodAside = dayDate ? state.daysStoodAside.includes(dayDate) : false;

  const counted = state.daysDone.length + state.daysStoodAside.length;

  const setDayFlag = (list: 'daysDone' | 'daysStoodAside') => {
    if (!dayDate) return;
    const has = state[list].includes(dayDate);
    patch({
      [list]: has ? state[list].filter((d) => d !== dayDate) : [...state[list], dayDate],
    } as never);
  };

  return (
    <div className="-mx-4 space-y-3 sm:mx-auto sm:max-w-2xl">
      {/* ---- Sticky working header ------------------------------------ */}
      <div className="sticky top-0 z-10 -mt-2 space-y-2 border-b bg-background/95 px-4 pb-2 pt-2 backdrop-blur sm:px-0">
        <div className="flex items-baseline justify-between gap-2">
          <h1 className="text-lg font-bold leading-none">Runner</h1>
          <span className="text-[11px] text-muted-foreground">
            Aura · NQ · {span.label}
          </span>
        </div>

        {declared ? (
          <>
            <div className="flex items-center gap-1.5">
              <Button
                size="icon"
                variant="outline"
                className="h-8 w-8 shrink-0"
                disabled={state.day === 0}
                onClick={() => patch({ day: Math.max(0, state.day - 1) })}
              >
                <ChevronLeft className="h-4 w-4" />
                <span className="sr-only">Previous replayed day</span>
              </Button>
              <div className="min-w-0 flex-1 text-center">
                <p className="truncate text-sm font-semibold leading-tight">
                  Replayed day {state.day + 1}
                </p>
                <p className="truncate font-mono text-[11px] text-muted-foreground">{dayDate}</p>
              </div>
              <Button
                size="icon"
                variant="outline"
                className="h-8 w-8 shrink-0"
                onClick={() => patch({ day: state.day + 1, activeSetup: 0 })}
              >
                <ChevronRight className="h-4 w-4" />
                <span className="sr-only">Next replayed day</span>
              </Button>
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                variant={dayDone ? 'default' : 'outline'}
                className="h-7 flex-1 px-2 text-xs"
                onClick={() => setDayFlag('daysDone')}
              >
                {dayDone ? 'Day counted' : 'Mark day done'}
              </Button>
              <Button
                size="sm"
                variant={stoodAside ? 'default' : 'outline'}
                className="h-7 flex-1 px-2 text-xs"
                onClick={() => setDayFlag('daysStoodAside')}
              >
                <HandMetal className="mr-1 h-3 w-3" />
                {stoodAside ? 'Stood aside' : 'Stood aside'}
              </Button>
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground">
              <strong className="text-foreground">{counted}</strong> replayed day
              {counted === 1 ? '' : 's'} counted ({state.daysDone.length} traded,{' '}
              {state.daysStoodAside.length} stood aside). A day you correctly stood aside{' '}
              <strong className="text-foreground">counts</strong> — R51.
            </p>
          </>
        ) : (
          <p className="text-[11px] leading-snug text-muted-foreground">
            Declare the span and start date below, then work one replayed day at a time.
          </p>
        )}
      </div>

      <div className="px-4 sm:px-0">
        <Tabs defaultValue="run" className="space-y-3">
          <TabsList className="grid w-full grid-cols-5 gap-0.5">
            <TabsTrigger value="run" className="px-1 text-[11px]">
              Run
            </TabsTrigger>
            <TabsTrigger value="setup" className="px-1 text-[11px]">
              Setup
            </TabsTrigger>
            <TabsTrigger value="markup" className="px-1 text-[11px]">
              Markup
            </TabsTrigger>
            <TabsTrigger value="playbook" className="px-1 text-[11px]">
              Rules
            </TabsTrigger>
            <TabsTrigger value="card" className="px-1 text-[11px]">
              Card
            </TabsTrigger>
          </TabsList>

          {/* ---- RUN ---------------------------------------------------- */}
          <TabsContent value="run" className="space-y-3">
            {!declared && <SessionPanel state={state} patch={patch} />}

            {declared && (
              <>
                {/* Stays on screen after declaring — you go straight from here to
                    Tradezella's create-session form. */}
                <TradezellaPaste state={state} />

                {/* Setup selector — only phases 3-5 repeat, so it is scoped to them. */}
                <div className="flex flex-wrap items-center gap-1.5 rounded-lg border bg-card p-2">
                  <span className="text-[11px] text-muted-foreground">Setup</span>
                  {Array.from({ length: setupCount }).map((_, i) => (
                    <Button
                      key={i}
                      size="sm"
                      variant={state.activeSetup === i ? 'default' : 'outline'}
                      className="h-7 w-7 p-0 text-xs"
                      onClick={() => patch({ activeSetup: i })}
                    >
                      {i + 1}
                    </Button>
                  ))}
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 px-2 text-xs"
                    onClick={addSetup}
                  >
                    <Plus className="mr-0.5 h-3 w-3" />
                    setup
                  </Button>
                  <span className="w-full text-[11px] leading-snug text-muted-foreground">
                    Phases 3–5 repeat per setup. Phases 0–2 and 7 are day-level and do not.
                  </span>
                </div>

                {phases.map((p) => (
                  <PhaseCard
                    key={p.index}
                    phase={p}
                    day={state.day}
                    setup={state.activeSetup}
                    ticks={state.ticks}
                    onToggle={toggle}
                    open={openPhase === p.index}
                    onOpenChange={(o) => setOpenPhase(o ? p.index : null)}
                  />
                ))}

                <OpenFlags />

                <details className="rounded-lg border bg-card p-2.5">
                  <summary className="cursor-pointer text-[13px] font-semibold">
                    Session declaration
                  </summary>
                  <div className="pt-2">
                    <SessionPanel state={state} patch={patch} />
                    <Button
                      size="sm"
                      variant="ghost"
                      className="mt-2 h-7 px-2 text-xs text-muted-foreground"
                      onClick={() => {
                        if (confirm('Clear all runner state in this browser?')) reset();
                      }}
                    >
                      <RotateCcw className="mr-1 h-3 w-3" />
                      Reset runner
                    </Button>
                  </div>
                </details>
              </>
            )}
          </TabsContent>

          {/* ---- REFERENCE TABS ----------------------------------------- */}
          <TabsContent value="setup">
            <ReferenceSections sections={runnerData.setup.sections} />
          </TabsContent>
          <TabsContent value="markup">
            <ReferenceSections sections={runnerData.markup.sections} />
          </TabsContent>
          <TabsContent value="playbook">
            <ReferenceSections sections={runnerData.mapping.sections} />
          </TabsContent>

          {/* ---- PER-TRADE CARD ----------------------------------------- */}
          <TabsContent value="card" className="space-y-2">
            <div className="rounded-lg border bg-card p-3">
              <h2 className="text-sm font-semibold">Per-trade card</h2>
              <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
                One per setup. Field names mirror the journal schema, so a card transfers cleanly
                into a Neurospect entry.
              </p>
              <div className="mt-2 overflow-x-auto">
                <pre className="min-w-[26rem] whitespace-pre rounded bg-muted p-2 text-[11px] leading-relaxed">
                  {runnerData.checklist.perTradeCard}
                </pre>
              </div>
            </div>
          </TabsContent>
        </Tabs>

        <p className={cn('pb-4 pt-3 text-[10px] leading-snug text-muted-foreground')}>
          Every rule and phase above is projected from the wiki
          ({runnerData.rules.length} rules, {phases.length} phases) and is read-only here. If the
          runner and <code>rules.md</code> disagree, <code>rules.md</code> wins. Step state lives in
          this browser only — nothing on this screen writes to the database.
        </p>
      </div>
    </div>
  );
}
