# Lineage

Rebuild the family tree of edited images from pixels alone.

## Inspiration

Every edit destroys information. A crop loses its edges, a JPEG re-save loses detail, and a grayscale conversion loses color. That makes the cost of explaining one image from another asymmetric: producing a child from its parent is cheap, while reconstructing the parent from the child requires inventing what is gone. The cheap direction is parent → child, and connecting those directions reconstructs the family tree.

## What it does

For auditors, every decision comes with a visual diff plate (the source aligned onto the copy, the copy, and a residual heatmap), a tamper-evident footprint (SHA-256, pHash, dimensions), reliability tiers on the calibrated precision, and a self-contained HTML report with an evidence inventory and a limitations section.

A second media type ships too: paste several versions of a paragraph at `/text` and the same core, with MinHash fingerprints and a word-loss cost swapped in, reports which copy was trimmed, reworded or rewritten.

In the live demo, a visitor uses the tablet `/edit` page to choose an image and apply one edit. Lineage returns a verdict and the evidence behind it, while the big-screen `/tree` page adds the result to a live forest with labeled edges, an evidence panel, and a tree-accuracy scoreboard.

The `/audit` workspace applies the same engine to industry provenance work without known ground truth. An analyst can create cases, batch-upload images, inspect likely originals and edit paths, review calibrated confidence and metadata hints, and download a JSON report.

Lineage is designed for newsroom verification, trust and safety investigations, legal discovery, and digital asset management: settings where a team receives many related images and needs to know which came first, what changed, and which decisions require review.

## How we built it

Each image receives a 64-bit pHash and a 512-bit binarized CLIP fingerprint. We use Hamming distance to select the top eight likely relatives, then run the expensive directed comparison only on those candidates rather than on every possible pair.

For each candidate direction, ORB keypoints and a RANSAC homography register the images. The cost combines coverage, a moment-matched per-channel color fit, and gated information-loss cues for JPEG blockiness, resolution, chroma, and entropy. It also measures removed-content blobs, falls back to semantic CLIP similarity when pixels no longer align, adds a minimum-description-length prior for detected edit operations, and uses a small specificity tie-break to prefer the closest ancestor. Our own Chu-Liu/Edmonds implementation selects the minimum-cost directed forest through a virtual root. The chosen cost, reverse cost, runner-up, and margin become human-readable evidence, and the margin maps to empirical precision calibrated on synthetic edit chains.

The stack is Python, FastAPI, OpenCV, OpenCLIP, and SQLite on the backend; React, Vite, TypeScript, and D3 on the frontend; the Gemini image API with an OpenCV fallback for restyling; and Docker with Caddy for deployment.

## Challenges

The hardest errors were not wrong families or reversed directions. They were ties between a true parent and grandparent: a crop of a crop can still look like one crop from the original, and a JPEG of a JPEG can look like one re-save from the clean source. The edit-operation prior resolved many of those cases, but double-JPEG ancestry remains the weakest case.

Our first run of hand tuning overfit by about 20 percentage points. We replaced broad heuristics with principled gates around tint on grayscale images, grayscale entropy, and residual-blob weighting, then evaluated on a second held-out synthetic run.

Gemini image models required a billing-enabled key, so the demo keeps the same restyle flow alive with a clearly recorded OpenCV fallback when image quota is unavailable. We also found a `created_at` number-versus-string bug that blanked the tree and audit pages; Playwright screenshots exposed it, and an error boundary plus the type fix made the failure visible and the pages reliable.

## Accomplishments

On the tuned first synthetic run, Lineage recovered 73 of 88 parent links, or 83.0%. On the held-out second run it recovered 64 of 90, or 71.1%, and it found all six roots in each run. Direction flips were rare; most remaining errors chose another ancestor in the correct family.

Across both calibration runs, empirical precision by decision-margin bucket was 44/67 (66%) below 0.02, 15/21 (71%) from 0.02–0.05, 45/53 (85%) from 0.05–0.10, 14/17 (82%) from 0.10–0.30, and 23/24 (96%) at 0.30 or higher. We built 112 pytest cases around candidate search, the arborescence, image cost, explanations, restyling, the pool API, and audit cases.

The live experience works end to end: one edit from the tablet enters the pool, the forest updates within the polling cycle, the verdict exposes its evidence, and the scoreboard checks the hidden truth. In audit mode, a six-image shuffled batch reconstructed the correct two-family forest and produced its JSON report.

## What we learned

Information loss is a strong signal for roots and direction, but it is weaker for choosing the immediate ancestor among several valid ancestors. A small, interpretable prior can settle near-ties more reliably than another large visual heuristic. We also learned that evidence is part of the product: forward and reverse costs, rejected circular choices, margins, and calibration make a result reviewable instead of merely plausible. Finally, held-out evaluation caught problems that a good-looking live demo would not have revealed.

## What's next

We want to add a web mode that brings in candidates from reverse-image providers, double-JPEG detection for compression chains (our first attempt, an AC-sparsity cue, lost accuracy and was reverted), more media plug-ins on the same core, and C2PA ingestion so signed provenance can complement pixel-based inference.

## Built with

Python, FastAPI, Uvicorn, NumPy, OpenCV (`opencv-python-headless`), Pillow, NetworkX, PyTorch, `open_clip`/OpenCLIP with OpenAI ViT-B/32 weights, requests, python-dotenv, pytest, httpx, `google-genai` and the Gemini image API, SQLite, React, React Router, Vite, D3, TypeScript, The Metropolitan Museum of Art Open Access API and CC0 collection, Caddy, Docker, Vultr.

## AI disclosure

We built Lineage with AI coding agents under our direction: Claude Code contributed the backend, core algorithms, evidence and calibration work, API, tests, and parts of the interface and documentation; OpenAI Codex contributed the explanation plug-in, initial React scaffold, tree UI, and audit workspace; and Google Gemini via Antigravity researched the current Gemini image-editing API and sanity-checked the deployed routes (visual QA itself was done with Playwright screenshots). We designed the asymmetric information-loss approach, candidate and plug-in architecture, demo flow, evidence model, and evaluation protocol; we reviewed the output and made the engineering and tuning decisions. The approach and decisions are the team's.

## 2-minute demo pitch

### 0:00–0:15 — Hook

“Every image edit throws information away. A crop loses edges; a JPEG loses detail. So one direction is cheap to explain—parent to child—and the reverse is expensive. Lineage turns that asymmetry into an image family tree.”

### 0:15–0:42 — Tablet edit

“Here on the tablet, I pick an image and make exactly one edit. I’ll crop this one and submit it. The server keeps the real parent only for the demo scoreboard; the lineage engine never sees it. It compares pixels, chooses a parent, and gives us a verdict with the measured evidence.”

### 0:42–1:05 — Live tree and evidence

“Now look at the big screen. The new image appears in the live forest under its predicted parent, and the edge names the edit. The scoreboard checks that edge against the hidden truth. If I select it, the evidence panel shows keypoint alignment, coverage, color fit, both directional costs, the runner-up, and the margin.”

### 1:05–1:30 — Audit workspace

“A live demo has truth. Real investigations usually do not. In the audit workspace I can create a case and batch-drop a folder of related images. Lineage separates families, identifies likely originals, reconstructs each edit path, flags low-confidence edges, and exports the whole analysis as JSON.”

### 1:30–1:44 — Calibrated confidence

“That confidence is not a generic model probability. It is empirical precision from synthetic edit chains for decisions in the same margin bucket. At a margin of 0.30 or more, 23 of 24 evaluated decisions were correct—96%.”

### 1:44–1:54 — Industry ask

“If you work in newsroom verification, trust and safety, legal discovery, or asset management, bring us the messy image sets where provenance costs time. We want to learn which evidence your reviewers need.”

### 1:54–2:00 — Close

“No filenames, timestamps, or trusted metadata—just the information left in the pixels. That is Lineage.”
