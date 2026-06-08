# Weekly Report — Image Utility (Refining-Enabled, experimental) — 2026-06-01

*An experimental copy of the Lite image tool, used to try out higher-quality background-removal edges — it adds an optional "Alpha Matting" refinement mode that produces sharper, cleaner cut-out edges in exchange for slower processing.*

## This week (May 25 – June 1)

**No development this week.** No new features, fixes, or releases. The experimental work landed in mid-May (around the 18th–19th) and hasn't been touched since.

## Open / in-flight

- **This is an experiment, not a shipped feature.** The edge-refinement work lives only in this separate copy of the tool — it has **not** been folded into the main Lite or Advanced apps the team uses.
- **The work is undocumented and un-versioned.** Its changelog and version number were never updated, so the project still reads as version 1.3.1 even though it now contains the new refinement code. In effect, this improvement is currently invisible in the project's own history.
- **Decision needed:** promote this edge-refinement into the main tool(s), or retire the experiment.

**Net this week:** No change — the experimental edge-refinement sits unmerged in a side copy, awaiting a decision.

## May

May was when this experiment was created and the refinement feature was built.

- **Spun up a separate copy of the Lite tool** specifically to improve the quality of background-removal edges.
- **Added an optional "Alpha Matting" mode** — a checkbox plus three tuning sliders (how much counts as foreground, how strict the background separation is, and how tightly to trim the edge) that trade roughly 3× slower processing for noticeably sharper, cleaner cut-out edges.
- **Added an automatic cleanup pass** that removes faint stray speckles and solidifies near-solid edges, so cut-outs come out crisper with fewer leftover artifacts.
- **Left deliberately as an experiment** — not merged into the shipping apps, and (a miss) its changelog and version were not updated to record the work.

**Net for May:** A working proof-of-concept for higher-quality background-removal edges, sitting in a separate copy and awaiting a decision on whether to fold it into the main tool. June has only just begun — no activity yet on day one.

## Retrospective

**What went right / learnings:** Proved we can get markedly sharper background-removal edges by turning on trimap-based "alpha matting" plus an automatic cleanup pass that kills speckles and solidifies edges, all exposed as user-tunable sliders — the lesson being that the quality ceiling on our cut-outs wasn't the AI model at all, it was the edge post-processing step we simply hadn't been doing.

**What to improve / for the team:** I should have updated the changelog and version as I went (this work is currently invisible in the project's own history) and decided up front whether an experiment lives as a throwaway copy or a switch inside the real app; the reusable company lesson is to log experimental work in its changelog from day one and set a clear "promote or kill" checkpoint, so good experiments don't get stranded and forgotten in side copies.
