# Demo-day runbook

Everything below assumes the server is running on the demo laptop on port 8010 and the tablet
and TV are on the same network (or the Vultr deployment at your domain).

## 30 minutes before

```
# fresh pool with three known families (stop the server first if it is running)
.venv\Scripts\python backend\scripts\seed_pool.py --families 3 --chains 2 --reset
.venv\Scripts\python -m uvicorn app:app --app-dir backend --host 0.0.0.0 --port 8010
```

- TV / projector: `http://<laptop-ip>:8010/tree` in a full-screen browser (F11). Leave it; it polls every 2 s.
- Tablet: `http://<laptop-ip>:8010/edit`, add to home screen so it opens full-screen.
- Judge laptop or second screen: `http://<laptop-ip>:8010/` (about) and `/audit`.
- Have 6 to 8 versions of one photo in a folder for the audit demo (export a few from the pool:
  `data/pool/*.png`, or use `data/synthetic/run1/f0_*.png`).
- Check `GET /api/health` returns `ok: true` and the right item count.

## The 2-minute script

See `docs/DEVPOST.md`, section "2-minute demo pitch". Beats: one idea -> tablet edit -> tree
updates with evidence -> audit batch upload -> calibrated confidence -> industry ask -> close.

## Things that can go wrong

- **AI restyle returns a local stylization** instead of a Gemini image: the key has no image
  quota (billing). The edit still works and the stored params say `model: local-opencv`.
- **Tree accuracy dips** after several edits of the same kind on the same image: siblings with
  the same edit are genuinely ambiguous; say so, the evidence panel shows the margin.
- **Caption over a caption** attaches to the sibling: known limitation, documented in PLAN.md.
- **The TV page goes dark**: an error boundary now shows the message and a Reload button; reload.
- **Port 8000 is taken** on the dev laptop; everything is on 8010.
- **Memory**: the server holds one CLIP model (~1.5 GB). Do not run `eval.py` / `calibrate.py` next to
  it on a 16 GB laptop during the demo; each loads its own copy.
- **Reset mid-event**: `POST /api/reset` with header `X-Admin-Token: <ADMIN_TOKEN>` (if set), then
  rerun `seed_pool.py` and restart the server.

## Numbers to quote

From PLAN.md (synthetic chains, 6 CC0 seeds, 3 chains each): run1 83.0% (tuned), run2 71.1% and
run3 81.1% (held out); roots found 6/6 on every run; true parent inside the top-8 candidates
98.9%; empirical precision by margin: >= 0.30 about 96%, < 0.02 about 66%. 116 tests.
Audit load test: 30 shuffled versions from 3 originals, 9 edits deep, uploaded in 29 s; 3 families
found; 28 of 30 parents correct against the hidden truth (93%).
