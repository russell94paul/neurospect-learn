# Raw bar exports — deliberately NOT committed (2026-08-29)

**171 MB** of verbatim OHLC exported from Tradezella session `831607` by
`api/scripts/aura_bar_receiver.py` — NQ, ES, YM and CHFUSD at 5m / 15m / 60m / 240m / D / W,
plus a repacked form under `packed/`.

## Why this directory is not in git

The repo's `.git` was **50 MB** before this session. Adding these files would take it past
**220 MB permanently** — git cannot shrink that later without rewriting history, and every clone
would pay for it forever.

## Why that is a real cost, not a free win

The evidence rules require an analysis to be **reproducible**. These bars are the source data for
every S1c / S1d / S1e number, and without them none of it can be re-derived from scratch — only
re-read from the committed derived files (`computed-setups.json`, `chart-shapes-spec.json`,
`level-sheet.json`, `figure-pack.json`, `guided-pack.json`), which ARE committed.

So the trade being made is: **derived results are reproducible-on-inspection, but not
reproducible-from-source**, until Paul decides otherwise.

## The three options, for whoever picks this up

1. **Leave as is.** Bars live on this machine only. Cheapest; loses the raw source if the machine does.
2. **git-lfs.** `git lfs track "api/docs/evidence/s1e/bars/**"` — keeps them versioned without
   bloating the pack. The usual answer for this shape of problem.
3. **Commit them plainly.** Accept a ~220 MB repo.

Nothing is gitignored, so `git status` will keep showing these files — that is intentional. A
decision this size should stay visible rather than being silenced by a gitignore line.
