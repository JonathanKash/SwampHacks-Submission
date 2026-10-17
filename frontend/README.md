# Lineage frontend

React gives us component state for two very different pages, Vite builds to static files that FastAPI serves from frontend/dist.

## Commands

```bash
npm install
npm run dev
npm run build
```

The development server proxies `/api`, `/images`, and `/thumbs` to `http://localhost:8010 (set BACKEND to override)`.
