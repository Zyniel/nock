---
id: B-034
title: 'HTTP edge: body size, security and caching headers, the Bearer scheme'
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:serving
  - domain:server
  - domain:operations
dependencies: []
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done
- Priority: sixth (before the first public test; small)
- Domains: platform/serving (new, split from platform/server: serving the
  client, environment settings, the HTTP edge), platform/server,
  admin/operations (the scheme of the operator token)
- Architecture decision: yes, the new domain (the human, 2026-10-31); the
  rest is one middleware and the `Caddyfile` of B-009
- Criteria: serving AC-7 to AC-14 (new), serving AC-1 to AC-6 (moved from
  server AC-14 to AC-19, retired with server AC-27 to AC-33), operations
  AC-21 (new)
- Branch: feat/b-034-http-edge · PR: #75
- Problem: neither uvicorn nor the `Caddyfile` limits a request body, and
  FastAPI reads it whole before validation (B-028 M3). No answer has a
  `Content-Security-Policy`, `X-Content-Type-Options` or `Referrer-Policy`,
  and any site can frame the room page or `/ops` (L6). The ops API accepts the
  exact prefix `Bearer ` only, though the scheme is case-insensitive
  (RFC 9110), and a wrong case counts toward the throttle (L7). The page
  routes answer `index.html`, and `/assets/` its hashed files, with no
  `Cache-Control` (`server.py:711`, `:1408`; the `Caddyfile` adds none): a
  browser can keep a days-old `index.html` after a deploy and ask for
  scripts the new build no longer has, a blank page (B-039 M10).
- In scope: a body limit (lead's proposal: 64 KB) in the app (a middleware
  answering 413) and in the `Caddyfile` (`request_body max_size`); the
  headers on every answer, the CSP to `'self'` with `frame-ancestors 'none'`;
  the scheme compared case-insensitively; `Cache-Control: no-cache` on
  `index.html` for every page route, and `public, max-age=31536000,
  immutable` on `/assets/*`.
- Out of scope: the WebSocket frame size (8 KiB already); CORS (no
  cross-origin use).
- The `Caddyfile` is deployment configuration, not tooling under `CLAUDE.md`;
  the implementer changes it with the app.
- Screens: none (a CSP that breaks the page shows in the browser tests). The
  client has no inline script, no `style="…"` in its markup and no outside
  source; Svelte sets styles through the CSSOM, which a CSP does not block.
- Open questions:
  1. Where the headers are set: A (lead's default) by the app, so they hold
     behind any proxy and in the tests; B by Caddy only.
- Decisions: the human, 2026-10-31: 1A, the app sets the headers; the spec
  change approved, with `platform/server.md` split into
  `platform/serving.md` first. The lead's picks: `Referrer-Policy:
  no-referrer`, no `X-Frame-Options`, `no-cache` on the build's root files,
  the brief's CSP as it stands, one space after the scheme; server.md keeps
  rules 20 to 22 at their numbers (no reference changes).
<!-- SECTION:DESCRIPTION:END -->
