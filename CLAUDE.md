# Lineage — project context for Claude Code

Hackathon project (SwampHacks XII, UF, Oct 16-18 2026). Read SPEC.md for the full spec and
PLAN.md for phase status. Optimize for a reliable live demo.

## What it does
Reconstructs the edit family tree of a pool of images: asymmetric cost(a -> b) ("how cheaply
is b a lossy function of a") over candidate pairs, then a minimum spanning arborescence.

## Stack and commands
- Python 3.13 backend in `backend/`, venv at `.venv/` (Windows: `.venv/Scripts/python`).
  Deps: numpy, opencv-python-headless, pillow, networkx, open_clip_torch (CPU torch), fastapi.
- Run tests: `.venv/Scripts/python -m pytest backend/tests -q`
- Phase 0 pipeline (from repo root):
  - `.venv/Scripts/python backend/scripts/fetch_seeds.py`   (Met Open Access CC0 images -> data/seeds)
  - `.venv/Scripts/python backend/scripts/gen_chains.py`    (synthetic chains + truth -> data/synthetic/<run>)
  - `.venv/Scripts/python backend/scripts/eval.py data/synthetic/<run>`
- Config flags live in `.env` (see `.env.example`). `USE_FALLBACK=true` selects the temporary engine.

## Layout
```
backend/lineage/
  config.py                      cost weights dict + env flags
  types.py                       Item / Fingerprint / Edge / TreeResult dataclasses
  core/engine.py                 Pool -> fingerprints -> candidates -> cached costs -> arborescence
  core/candidates.py             HUMAN-WRITTEN (stub + tests/test_candidates.py)
  core/arborescence.py           HUMAN-WRITTEN (stub + tests/test_arborescence.py)
  core/fallback.py               TEMPORARY Claude-written stand-ins (networkx + crude cost)
  plugins/image_fingerprint.py   pHash + sign-binarized CLIP ViT-B/32
  plugins/image_cost.py          HUMAN-WRITTEN (stub + tests/test_image_cost.py)
  edits/image_edits.py           the fixed edit menu (crop/rotate/filter/caption/jpeg) as pure functions
backend/scripts/                 fetch_seeds.py, gen_chains.py, eval.py
backend/tests/                   pytest specs for the three human-written files
data/                            gitignored: seeds/, synthetic/, pool/
```

## Hard rules
- NEVER implement the bodies of candidates.py, arborescence.py, image_cost.py. They are the
  team's hand-written entry for the "Least Vibe Coded" prize. Only update their interface or
  tests if the team asks.
- The engine must never read an item's true parent. Truth lives only in generator output /
  the upload record and is used by the eval and accuracy endpoint.
- No secrets in code. `.env` only; keep `.env.example` current.
- Simple, readable code; judges will ask about every part. Prefer a few files over many.
- Every new library/API goes into the README credits. Keep the README "AI disclosure" honest.
- Commit after each working step.
