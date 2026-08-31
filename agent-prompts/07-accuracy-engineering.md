# 07 — Accuracy Engineering

Owned NFRs: NFR-004, NFR-005. Owning milestone: M12.

## The threshold is an operating point, not a truth

`tau = 0.45` is the spec's default (§5.4). It is a conventional operating point for ArcFace
`r100` on glint360k. **It is not calibrated until measured.** Treat it as a hypothesis M12 tests.

`tau` stays configurable via `--threshold` and `Config.threshold`. Never hardcode it in
`pipeline`.

## What to measure

Given a labelled set of face pairs:

```text
same-identity similarity distribution      (mean, min, max)
different-identity similarity distribution (mean, min, max)
false positives at tau
false negatives at tau
separation between the two distributions
```

Report to `eval/threshold_report.md` and summarise in the README (spec §5.4 requires the chosen
value and its observed separation to be recorded there).

## Language rules — non-negotiable

Cosine similarity is **not** a probability and **not** a confidence.

```text
CORRECT:   cosine similarity 0.7123 (threshold 0.45)
CORRECT:   similarity score: 0.7123
WRONG:     71.23% confidence
WRONG:     71% match
WRONG:     confidence: 0.7123
```

`similarityBps = 10000` means cosine 1.0. It does not mean "100% certain". This is the one
artifact a judge sees on a block explorer without the README beside it (FR-051, HC-19).

The audit sweep in `99-final-audit.md` greps for a `%` adjacent to a similarity value and fails
on a hit.

## AMB-01 blocks this milestone

**The spec never says where the labelled evaluation set comes from.** Master §19 wants
same-identity and different-identity pairs; spec §15 says the tool is not pointed at private
individuals. Collecting labelled face pairs has consent implications the spec does not resolve.

Do not silently scrape a face dataset. Ask (AMB-01), and offer these options:

- **A** — public figures only, images already public, documented in the README with the same
  disclosure the demo subject gets. Smallest ethical delta from what the demo already does.
- **B** — an established academic benchmark subset (e.g. LFW) under its stated licence, cited.
  Standard practice, but check the licence permits this use.
- **C** — the author's own face plus consenting volunteers. Cleanest consent story, smallest set,
  weakest statistics.

Recommend **B** for the different-identity distribution and **A or C** for same-identity pairs,
and say which was used in the README.

## Degraded accuracy is expected and must be stated

Face recognition accuracy drops sharply across pose, illumination, age gap, occlusion, and —
well documented in the literature — across demographic groups. A single cosine score carries no
fairness guarantee. The README says this plainly (spec §15).

## Gate

M12 passes when: `tau` has a measured basis, the distributions are recorded, the README carries
the result, and no output anywhere renders similarity as a percentage.
