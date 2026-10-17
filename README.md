# Lineage

Given a pool of edited versions of an image, Lineage reconstructs the family tree: which
version is the original, who was derived from whom, and what edit produced each child.

Core idea: edits destroy information. A child is cheaply explained as a lossy function of its
parent, but not the other way round. We score every candidate pair with an asymmetric
cost(a -> b), then take the minimum spanning arborescence of the directed graph.

Built at SwampHacks XII (University of Florida, Oct 16-18 2026).

## Run it

```
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
.venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
copy .env.example .env                                            # add GEMINI_API_KEY for AI restyle

.venv\Scripts\python backend\scripts\fetch_seeds.py              # CC0 images from the Met
.venv\Scripts\python backend\scripts\seed_pool.py --reset        # pre-seed the demo pool with known chains
cd frontend && npm install && npm run build && cd ..              # builds frontend/dist
.venv\Scripts\python -m uvicorn app:app --app-dir backend --port 8010
```

Then open http://localhost:8010/ (about), /edit (tablet) and /tree (big screen). The first start
downloads the CLIP weights (about 350 MB). For frontend development run `npm run dev` inside
`frontend/`; it proxies the API to port 8010.

Evaluation and tests:

```
.venv\Scripts\python backend\scripts\gen_chains.py --name run1   # synthetic edit chains + truth
.venv\Scripts\python backend\scripts\eval.py data\synthetic\run1 # tree accuracy report
.venv\Scripts\python -m pytest backend\tests -q                  # 113 tests
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

The code in this repository was written with AI coding agents under our direction during the
event. We designed the approach (asymmetric information-loss cost, candidate search, minimum
spanning arborescence, the plug-in architecture, the demo flow, the evidence and calibration
protocol and the industry audit mode), specified each component, reviewed the output, and drove
the tuning from the evaluation numbers. Specifically:

- Claude Code (Anthropic, Claude Fable 5.1): the backend (cost function, candidate search, the
  Chu-Liu/Edmonds arborescence, engine, evidence and calibration, API, scripts, tests), the
  landing page, the guided edit flow and evidence UI, the docs.
- OpenAI Codex (via the Codex CLI): the explain plug-in (`plugins/image_explain.py` and its
  tests), the initial React frontend scaffold (API client, polling hook, D3 tree view, first
  versions of the edit and tree pages) and the audit workspace page.
- Google Gemini (via the Antigravity CLI): research of the current Gemini image-editing API and a
  route sanity check of the running app. Visual QA was done with Playwright screenshots reviewed
  by Claude Code.

The Chu-Liu/Edmonds implementation in `backend/lineage/core/arborescence.py` is written from
scratch (not a library call) and is cross-checked against networkx in the tests. Seed images
are CC0 works from The Met.

## Credits

Libraries: NumPy, OpenCV (opencv-python-headless), Pillow, NetworkX, PyTorch, open_clip
(OpenCLIP, ViT-B/32 weights by OpenAI), requests, python-dotenv, pytest.
APIs and data: The Metropolitan Museum of Art Open Access API (CC0 images; per-image credits
in `data/seeds/credits.json`).
Backend API: FastAPI, Uvicorn, httpx, google-genai (Gemini image models). Frontend: React, React
Router, Vite, D3, TypeScript. Deploy: Caddy, Vultr.
