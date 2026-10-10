# Nock web client

Svelte + TypeScript app built with Vite. FastAPI serves the build from `web/dist`.

```
npm --prefix web ci          # install dependencies
npm --prefix web run check   # svelte-check and tsc
npm --prefix web run build   # write web/dist
```

All user-facing text lives in `src/i18n/fr.json` and is read with `t()` from
`src/lib/i18n.ts`.
