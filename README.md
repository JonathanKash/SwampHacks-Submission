# Lineage

Given a pool of edited versions of an image, Lineage reconstructs the family tree: which
version is the original, who was derived from whom, and what edit produced each child.

Core idea: edits destroy information. A child is cheaply explained as a lossy function of its
parent, but not the other way round. We score every candidate pair with an asymmetric
cost(a -> b), then take the minimum spanning arborescence of the directed graph.

Built at SwampHacks XII (University of Florida, Oct 16-18 2026).

## Run it (Phase 0: synthetic evaluation)

```
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
copy .env.example .env

.venv\Scripts\python backend\scripts\fetch_seeds.py              # CC0 images from the Met
.venv\Scripts\python backend\scripts\gen_chains.py --name run1   # synthetic edit chains + truth
.venv\Scripts\python backend\scripts\eval.py data\synthetic\run1 # tree accuracy report
.venv\Scripts\python -m pytest backend\tests -q                  # specs for the hand-written core
```

## Architecture

```
pool of items
   |  fingerprint(item)          plug-in 1: pHash + binarized CLIP (cheap codes)
   v
candidate search (top-k)        core: Hamming distance, never n^2 costs
   |
   v
cost(a -> b) on candidate pairs plug-in 2: asymmetric "how cheaply is b made from a"
   |  (cached per pair)
   v
minimum spanning arborescence   core: Chu-Liu/Edmonds with a virtual root (forest-capable)
   |
   v
tree + explain(a -> b)          plug-in 3: "cropped to 62%, warm filter, caption added"
```

The core is media-agnostic. Images are the first media type; text is the stretch goal.

See `CLAUDE.md` for the file layout and `SPEC.md` for the full specification.

## AI disclosure

The code in this repository was written by Claude Code (Anthropic, Claude Fable 5.1) under
our direction during the event: we designed the approach (asymmetric information-loss cost,
candidate search, minimum spanning arborescence, the plug-in architecture, the demo flow and
the evaluation protocol), specified each component, reviewed the output, and drove the
tuning from the evaluation numbers. The Chu-Liu/Edmonds implementation in
`backend/lineage/core/arborescence.py` is our own code (not a library call) and is
cross-checked against networkx in the tests. Seed images are CC0 works from The Met.

## Credits

Libraries: NumPy, OpenCV (opencv-python-headless), Pillow, NetworkX, PyTorch, open_clip
(OpenCLIP, ViT-B/32 weights by OpenAI), requests, python-dotenv, pytest.
APIs and data: The Metropolitan Museum of Art Open Access API (CC0 images; per-image credits
in `data/seeds/credits.json`).
Phase 2+: FastAPI, Uvicorn, D3, Google Gemini API, Caddy, Vultr.
