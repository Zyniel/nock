---
id: B-009
title: Run Nock in a Docker container, dev and prod
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels: []
dependencies: []
ordinal: 19000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved option A, 2026-10-25)
- Domains: none (deployment files and README; no behaviour of the app)
- Architecture decision: yes (options from the Plan agent on Fable; the human
  picked A: files and docs, checked once by hand; a CI check is a later item)
- Branch: feat/b-009-docker
- Problem: a maintainer cannot run Nock in a container. The two local attempts
  put `.env*`, `data/` and `.git` into the image (no `.dockerignore`), run as
  root on Python 3.13 (the project pins 3.14) with Node and dev dependencies
  left in, and behind Caddy every player shares the proxy's address, so one
  player's wrong tokens throttle everyone (uvicorn trusts only 127.0.0.1).
- In scope: a two-stage image (Node builds `web/dist`; a 3.14-slim runtime with
  the venv, `src`, `web/dist`, `web/src/i18n` and `grids` at the repo layout
  the server reads), non-root, a `/data` volume, a healthcheck on `/`, `CMD`
  the venv's `python -m nock`; `.dockerignore`; one replica; dev = the same
  image over http on port 8000 with Mailpit for mail; prod = the image behind
  Caddy, the domain from `NOCK_DOMAIN` (default `nock.zyniel.com`), TLS
  automatic, `FORWARDED_ALLOW_IPS` so players keep their address; secrets from
  an env file git ignores (`.env.dev`, `.env.prod`, `data/` in `.gitignore`);
  README's "Running in Docker" with the two `docker compose` commands, in place
  of the PowerShell scripts. Checked once by hand: both setups build, `/`
  serves, a room join works, a room survives a restart.
- Out of scope: a spec and a CI check (option B, later); the hosting choice;
  live reload in a container; Docker secrets files; more than one replica.
- Dependencies (approved with A): base images `python:3.14-slim`,
  `node:lts-slim`, `ghcr.io/astral-sh/uv`, `axllent/mailpit`, `caddy:2-alpine`.
- Screens: none.
<!-- SECTION:DESCRIPTION:END -->
