# Lineage — Project Spec (SwampHacks XII, UF)

Hacking started Fri Oct 16 2026, 8pm ET. Devpost closes Sun Oct 18 2026, 8:00am ET.
Rules: all code written during the event, AI use must be disclosed, every library/API credited.
Optimize for a reliable live demo, not completeness.

## What it is
Given a pool of edited versions of an image, Lineage reconstructs the family tree: which
version is the original, who was derived from whom, and what edit produced each child
(e.g. "cropped to 62%, warm filter, caption added").

Core insight: edits destroy information. A child can be cheaply explained as a lossy function
of its parent, but not vice versa. We compute an asymmetric cost(a -> b) for candidate pairs,
then take the minimum spanning arborescence (Chu-Liu/Edmonds) over the directed graph.

## The demo
- Tablet page (/edit): shows a random image from the pool. The visitor applies ONE edit from a
  fixed menu, then submits. The new image joins the pool. The server records the true parent
  id, but the engine must NEVER read it.
- Big-screen page (/tree): the tree rebuilds live as uploads arrive (D3, root at top,
  thumbnails as nodes, edit labels on edges). A live "tree accuracy" number shows the % of
  nodes whose predicted parent equals the true parent.
- Edit menu (fixed): crop, rotate (small angles), color filter (warm/cool/brightness/
  contrast/grayscale), add caption text, re-save as low-quality JPEG, AI restyle (Gemini).
- Second media type if time allows: text (paraphrase chains through the same core).

## Stack
- Backend: Python, FastAPI, NumPy, OpenCV (ORB, RANSAC homography), open_clip (ViT-B/32, CPU),
  SQLite + files on disk. Few files.
- Frontend: lightweight SPA, two routes /edit (tablet) and /tree (big screen). Live updates
  via WebSocket or 2s polling.
- AI restyle: Gemini image editing (check current docs for the model name; key in .env).
- Deploy: Vultr VM, HTTPS via Caddy, custom domain. Run locally first.
- Seed pool: 5-10 CC0 images from the Met Open Access API + pre-seed script with known chains.

## Architecture (plug-in design)
Each media type implements three plug-ins:
1. fingerprint(item) -> compact codes for candidate search
   (images: 64-bit pHash + 512-bit sign-binarized CLIP embedding)
2. cost(a, b) -> float, asymmetric: how cheaply b can be produced from a
3. explain(a, b) -> human-readable edit description

Shared core (identical for every media type):
- candidate search: top-k (k=8) likely relatives per item via fingerprints (never n^2 costs)
- directed cost graph over candidate pairs, costs cached
- minimum spanning arborescence -> tree (forest if the pool has unrelated roots)
Recompute incrementally when an item is added.

## Image cost spec (implement precisely)
cost(a -> b):
1. ORB keypoints + RANSAC homography mapping a onto b. If registration fails, fall back to
   semantic cost and mark the edge "semantic".
2. Warp a into b's frame. Coverage penalty: fraction of b's pixels NOT covered by warped a.
   Main direction signal; weight heavily.
3. Per-channel affine color transform from warped a to b on the overlap. Residual = MSE after fit.
4. Information-loss cues: JPEG blockiness energy (8x8 grid) higher in b than a => a->b likelier;
   lower effective resolution in b than a => a->b likelier.
5. Localized residual blobs (e.g. caption) present in b but not a => a->b likelier.
6. Semantic fallback: 1 - cosine(CLIP(a), CLIP(b)), scaled to always cost more than a good
   registration.
Weighted sum; weights in one config dict.

explain(a -> b): area ratio -> "cropped to N%"; homography angle -> "rotated N degrees";
color transform -> warm/cool/brighter/darker/grayscale; blobs -> "caption added"; blockiness
jump -> "re-saved as low-quality JPEG"; semantic edge -> "AI restyle (matched by meaning)".

## Core implementation notes
- core/arborescence.py is our own Chu-Liu/Edmonds, readable and commented, cross-checked
  against networkx.minimum_spanning_arborescence in the tests (networkx is a test-only dep).
- core/candidates.py: top-k by Hamming distance on pHash + binarized CLIP codes.
- plugins/image_cost.py: the cost spec above, with weights in config.WEIGHTS.

## Phases (stop and report at each gate)
- Phase 0: synthetic chain generator; cost, candidate search, arborescence with pytest;
  eval script -> tree accuracy overall and per edit type. GO/NO-GO.
- Phase 1: backend API, SQLite schema, fingerprints, candidate search, incremental tree.
- Phase 2: /edit tablet page incl. Gemini restyle.
- Phase 3: /tree live view with thumbnails, edge labels, accuracy counter, newest-node highlight.
- Phase 4: pre-seed script, deploy to Vultr with HTTPS, README.
- Phase 5 (stretch): text plug-ins.

## Working rules
- Commit after every working step. Keep CLAUDE.md and PLAN.md updated.
- README: what it is, how to run, architecture, AI disclosure (Claude wrote the code under our
  direction), credits for every library/API.
- Simple readable code. No hardcoded secrets (.env + .env.example).


---

# Spec v2 (2026-10-17): media provenance + parent/child detection

Goal: given two or more pieces of media, determine (1) whether they share a lineage, (2) which is the
PARENT and which the CHILD, (3) whether an item is AI-generated/AI-edited vs a real capture, where that
can be measured. Images first, then audio and video (only after images work fully; internet samples,
not synthetic). Also GIFs, screenshots of images, screen recordings of video.

Decisions (user, 2026-10-17 morning):
- Build the feasible parts first, then a continuous loop adds to it.
- Gemini edits: try Antigravity; if it cannot return edited images, skip Nano Banana (no billed key).
- Source photos: anything (a user's own photo, an internet original, a company's copyrighted image).
- Meme corpus: 30 families, built extensively by a dedicated agent; downloads are acceptable for a
  non-redistributed test corpus.
- "Original" = candidate original (highest-fidelity ancestor within the supplied set). If a user later
  uploads the true original it must be recognized and presented as the original.
- AI-edited: report only what is measured (semantic-only registration, C2PA manifests, noise breaks in
  edited regions); no black-box detector verdicts.
- CLI: usable at scale; compare across an existing lineage (case or pool), not just two files.
- Codex for frontend until it fails, then Claude takes over; Gemini (Antigravity) for research/vision.

Report accuracy rules (non-negotiable): every claim traces to a measured signal; return "inconclusive"
rather than guess; show the benchmark accuracy for that media/edit type next to the verdict; reports are
reproducible (tool version + input hashes recorded).

Deliverables: image pipeline (then audio, video); benchmark harness with corpora and a results report;
comparison UI with the "Why is this the parent?" evidence button; README with signals and limitations.
