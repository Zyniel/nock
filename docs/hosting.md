# Hosting plan

Status: **draft, 2026-10-15.** The sections that do not depend on the owner's
answers are written. The recommendation (section 4) waits for the answers to the
questions in section 0. Nothing here changes code or tooling. Section 13 lists the
tooling that the owner has to approve.

## 0. Questions for the owner

1. **Scale.** How many rooms and players at the same time, at launch and in a year?
   (One room holds at most 8 players: `MAX_PLAYERS`, `src/nock/room.py:83`.)
2. **Budget.** What monthly amount is acceptable, hosting and mail included?
3. **Region and GDPR.** Must the data stay with an EU company, or is an EU region
   of a US company acceptable? Who is the controller (you as an individual, or a
   company or association)?
4. **Domain.** Do you already have a domain? Should it be a `.fr`?
5. **Operations.** Would you rather pay more for a managed platform, or run a small
   VPS (OS updates, a reverse proxy, backups)?
6. **Deploying updates.** By hand (one command), or automatically when a tag such
   as `v1.0.0` is pushed after CI passes?
7. **Grids.** Where do the licensed grid files live (spec 005): in the repository,
   or only on the server? There is no `grids/` folder in the repository today, so a
   deployment would start with an empty catalogue (`GRIDS_DIR`,
   `src/nock/catalogue.py:32`).

## 1. What the app needs at runtime

Checked against the code on `main`, 2026-10-15, and the specs named.

| Need | Detail | Source |
| --- | --- | --- |
| One process, one instance | `python -m nock` runs one uvicorn server for the app. Rooms are live in memory, one asyncio task per room, and one SQLite file is the store. Two processes on one file are not supported. Scaling out would need rooms pinned to an instance. | `src/nock/__main__.py`, `specs/_architecture.md` "How the server works", spec 018 "Out of scope" |
| Start command | `uv run python -m nock`, not `uvicorn nock.server:app`: only `main()` applies `server_config` (8,192-byte frame limit, and with spec 038 no access log and the `warning` log level). | `src/nock/__main__.py:23-28`, `src/nock/server.py:385-405`, spec 036, spec 038 "Logs" |
| Address and port | `NOCK_HOST` (default `127.0.0.1`), `NOCK_PORT` (default `8000`). In a container the host must be `0.0.0.0`; behind a proxy on the same machine keep `127.0.0.1`. | spec 036, `src/nock/__main__.py` |
| Python and Node | Python 3.13 or later (3.14 in development) through uv; Node.js LTS only to build the client. | `pyproject.toml`, `specs/_architecture.md` "Toolchain" |
| Built client | `npm --prefix web ci && npm --prefix web run build` writes `web/dist`. Without it, pages answer 503. | `src/nock/server.py:155-164`, spec 040 |
| Files read from the source tree | `web/dist`, `grids/` and (spec 033) `web/src/i18n/fr.json` are found relative to the package's source folder. The app must run from a checkout of the repository (with `uv sync`), not from a wheel installed elsewhere. | `src/nock/server.py:47`, `src/nock/catalogue.py:32`, spec 033 `nock.i18n` |
| WebSockets end to end | Every room is a WebSocket on `/api/rooms/{code}/ws`. The page uses `wss://` when it was loaded over HTTPS. The page pings every 2 s and drops a socket silent for 4 s, so proxy idle timeouts are never reached. | `src/nock/server.py:367-380`, `web/src/lib/RoomPage.svelte:635`, spec 017 |
| Persistent disk | `NOCK_DATABASE` names the SQLite file, in WAL mode with `synchronous=FULL`. Its folder must exist. Unset means in memory: every room is lost at restart. A local block disk is required (not a network file share). | spec 018, `src/nock/server.py:136`, README "Running the server with a database" |
| TLS | The app speaks plain HTTP. TLS is the proxy's or the platform's job. `NOCK_PUBLIC_URL` must be `https://...` so the session cookie gets `Secure`. | spec 033 "Configuration" and AC-1 |
| Outgoing mail (V1) | SMTP to a provider, port 587 (STARTTLS) by default. Accounts are on only when `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set. | spec 033 "Configuration", `nock.mailer` |
| Secrets (V1) | `NOCK_OPERATOR_TOKEN` (32 to 256 URL-safe characters; unset turns `/ops` off), `NOCK_SMTP_PASSWORD`. An invalid value stops the start with a message that never shows the secret. | spec 038 "Operator access", spec 033 "Configuration" |
| Background work | An hourly sweep deletes rooms 30 days after their last edit, and (V1) expired sign-in links and sessions. It runs inside the app; no cron job is needed. | spec 032 "Expiry sweep", spec 033 "Erasure" |
| Size | Spec 036 measures one room of 8 players typing 2 letters a second each. Nothing measures many rooms at once yet (see section 13). | spec 036 AC-3 |

### Two things to set behind any proxy

The code reads the client's address from the socket (`websocket.client.host`,
`src/nock/server.py:369`) and builds the share link from the request
(`request.base_url`, `src/nock/server.py:352`). uvicorn replaces both with the
values of `X-Forwarded-For` and `X-Forwarded-Proto` only when the request comes from
an address listed in `FORWARDED_ALLOW_IPS` (default `127.0.0.1,::1`; uvicorn
0.54 reads this environment variable itself).

- **Proxy on the same machine** (VPS with Caddy or nginx): the defaults work.
- **Proxy elsewhere** (managed platform): without `FORWARDED_ALLOW_IPS`, every
  player has the proxy's address, so:
  - 10 wrong room codes in a minute from anyone block every join for a minute
    (close 4429, spec 011);
  - the limit of 10 sign-in links per hour per address (spec 033 AC-8) and the
    operator-token throttle (spec 038) become limits for everyone;
  - share links start with `http://` instead of `https://`.

  Fix: set `FORWARDED_ALLOW_IPS` to the platform's proxy addresses, or to `*` when
  the app's port can only be reached through that proxy.

Spec 011 (line 487) says that trusting `X-Forwarded-For` is out of scope, while
uvicorn already trusts it from `127.0.0.1`. **Decision for the owner:** accept
this setting as part of hosting, or have the lead add a note to spec 011.

## 2. What rules out a host

- No persistent disk, or a disk shared by several instances: SQLite and the live
  rooms need one instance with its own disk. This rules out serverless platforms,
  scale-to-zero containers, and PaaS offers with an ephemeral file system only
  (for example Heroku, Scalingo, Google Cloud Run).
- No WebSocket support, or a proxy that cuts sockets after a fixed time.
- Autoscaling to several instances: it must be pinned to exactly one.

## 3. Options

Prices are rough, in October 2026, for the smallest size that fits. Check them
before choosing.

| | A. Small VPS + Caddy | B. Fly.io machine + volume | C. Render web service + disk |
| --- | --- | --- | --- |
| What it is | A Linux server (for example Hetzner, OVH or Scaleway, 2 vCPU, 2 to 4 GB). Caddy terminates TLS and proxies to `127.0.0.1:8000`. systemd runs the app. | One machine (container) in the Paris region (`cdg`) with a volume mounted for SQLite. Fly's proxy terminates TLS. | One web service (container) in Frankfurt with a persistent disk. Render's proxy terminates TLS. |
| WebSockets | Yes (Caddy proxies them with no setting) | Yes | Yes |
| Persistent disk | Local disk | Volume tied to one machine; daily snapshots | Disk tied to one instance; daily snapshots |
| One instance | By construction | Must be kept at one machine (`fly scale count 1`) | A service with a disk cannot scale out |
| TLS and domain | Caddy gets Let's Encrypt certificates on its own | Managed certificates | Managed certificates |
| Proxy addresses (section 1) | Defaults work | `FORWARDED_ALLOW_IPS` needed | `FORWARDED_ALLOW_IPS` needed |
| Deploy downtime | A few seconds (restart) | A few seconds (a machine with a volume is replaced in place) | A few seconds (a service with a disk has no zero-downtime deploy) |
| Your work | OS updates, firewall, Caddy, backups, monitoring | A Dockerfile and `fly.toml`; backups beyond the snapshots | A Dockerfile or build command; backups beyond the snapshots |
| GDPR | EU company, EU data centre | US company, EU region | US company, EU region |
| Rough cost per month | 5 to 10 € (server, provider backups, off-site backup storage) | 5 to 10 $ (machine with 512 MB to 1 GB, 1 GB volume) | 8 to 30 $ (paid instance and 1 GB disk) |

### Option D: Oracle Cloud Always Free (asked by the owner, 2026-10-15)

This is option A at no cost: an Arm VM (Ampere A1) running Linux, with Caddy and
systemd, in an EU region such as Paris, Marseille or Frankfurt. The app needs
nothing Arm cannot run: Python and uv, plus Node to build the client. Playwright
is a dev dependency, so production does not install it.

What the free tier gives (check in the console; the figures changed in 2026):

- A1 compute: Oracle's page has long said 4 OCPUs and 24 GB in total. Reports
  from 2026 say this was cut to 2 OCPUs and 12 GB. Either is far more than one
  Nock process needs.
- 200 GB of block storage in total, boot volumes included (at least 47 GB
  each). That is enough for the system disk and the SQLite file.
- Object Storage (around 10 GB) for the off-site backups of section 6. This is
  the same provider, so for real safety keep a second copy elsewhere.
- Email Delivery: an SMTP relay with a small free allowance (Oracle has said
  100 a day, up to 3,000 a month). This is enough for spec 033's sign-in links,
  and SPF and DKIM work as described in section 8.

Risks:

- **Idle reclamation.** Oracle may stop or reclaim an Always Free instance that
  stays nearly idle over 7 days (sources quote less than 10 % to 20 % CPU,
  network or memory use). A quiet Nock server would be idle. Upgrading the
  account to Pay As You Go (a card is required) removes this risk. The Always
  Free resources stay free. Set a budget alert at 1 €.
- **Capacity.** A1 instances are often "out of capacity" in popular regions when
  you create one. Retrying can take days. The free resources exist only in the
  home region, which you choose once, at sign-up. Choose Paris or Marseille.
- **No support or uptime commitment** on free resources. Oracle can change the
  terms, as the 2026 reduction shows. Keep the setup portable: the same systemd
  and Caddy files run on any VPS (option A), so you can move in an hour with a
  backup.
- **GDPR:** Oracle is a US company with EU regions. Its DPA covers the data, as
  for options B and C.

Verdict: a good fit for a beta or a small public launch, if you accept Pay As
You Go (still free) and a fallback plan to an option A VPS.

Not retained: Scalingo and Clever Cloud (French PaaS, but no block disk suited to
SQLite); Kubernetes (far more than one process needs).

## 4. Recommendation

**Waiting for the owner's answers.** Provisional leaning, to confirm:

- If you accept a little server work: **option A** with an EU provider. It is the
  cheapest, keeps the data with an EU company, and the defaults of section 1 work
  as they are.
- If cost matters most and you accept a little server work: **option D**
  (Oracle Always Free, as option A at no cost), on a Pay As You Go account, with
  option A as the fallback.
- If you want no server to maintain: **option B** in Paris, with
  `FORWARDED_ALLOW_IPS` set and the off-site backups of section 6.

## 5. TLS and domain

- One domain or subdomain for the whole app, for example `nock.fr` or
  `jeu.example.fr`. The page and its sockets share one origin, and spec 038 AC-2
  requires that no request leaves that origin, so no separate API or CDN host is
  needed.
- DNS: an `A` and `AAAA` record to the VPS (option A), or the records the platform
  gives (B, C).
- `NOCK_PUBLIC_URL=https://<domain>` (spec 033). The links in sign-in e-mails use
  it, never the request's `Host` header.
- HTTPS only: redirect HTTP to HTTPS and send `Strict-Transport-Security` (Caddy
  redirects by default; the platforms have a setting).
- A `.fr` domain needs a holder residing in the EU (AFNIC rules). About 10 € a
  year at a French registrar.

## 6. The SQLite file

**Location.** For example `/var/lib/nock/nock.sqlite3` (VPS) or
`/data/nock.sqlite3` on the volume (B, C). The folder must exist. The `-wal` and
`-shm` files next to it are part of the database (spec 018, spec 038 AC-4).

**What it holds.** Rooms and their logs, deleted 30 days after the last edit
(spec 032); V1 adds accounts, e-mail addresses, sessions and game history
(specs 033, 029). The table in spec 038 "What the server keeps" is the reference.

**Backups.**

- Never copy the file while the app runs: with WAL, a plain copy can be
  inconsistent. Take an online copy with SQLite's backup command or
  `VACUUM INTO '<file>'`, then compress and encrypt it, then send it off the
  machine (object storage or a storage box in the EU).
- Once a day. What a backup can lose is at most a day of rooms, since a crash
  without a backup loses nothing (commit before broadcast, spec 018).
- Platform snapshots (B, C) or provider backups (A) are a second layer, not the
  only one: they live with the same provider.

**What spec 038 means for backups.** The database itself keeps no byte of a room
after its deletion (`secure_delete`, WAL checkpoint, spec 038 AC-4), and a
deleted account leaves no address behind (spec 033 AC-4). Both specs leave
backups out of scope (spec 038 "Out of scope"; spec 033 "Out of scope": "erasing
data from backups"). So hosting has to set the rule:

- Keep backups for **14 days at most** (proposal), then delete them for good.
  Deleted data then disappears from every copy within 14 days. The privacy notice
  says so.
- Encrypt them, and keep the key apart from the backups.
- **Restoring brings back deleted data.** An account deleted after the backup was
  taken comes back with its address. Rooms past their 30 days are deleted again by
  the sweep at once (spec 032), but accounts are not. So restore only after a
  disaster, and then delete again the accounts whose deletion came after the
  backup. Without a record of those deletions, the honest fallback is to tell
  those users. A small deletion journal is a possible later spec.

**Restore test.** Once a month, and after any change to backups: take the latest
backup, decrypt it on another machine, run `PRAGMA integrity_check`, start
`NOCK_DATABASE=<copy> uv run python -m nock` against it, open a room that was in
progress, then delete the copy.

## 7. Secrets and configuration

| Variable | Value in production | Secret |
| --- | --- | --- |
| `NOCK_HOST` | `127.0.0.1` (A) or `0.0.0.0` (B, C) | no |
| `NOCK_PORT` | `8000`, or the platform's | no |
| `NOCK_DATABASE` | path on the persistent disk | no |
| `FORWARDED_ALLOW_IPS` | unset (A); the platform's proxy addresses (B, C) | no |
| `NOCK_OPERATOR_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | **yes** |
| `NOCK_PUBLIC_URL` | `https://<domain>` | no |
| `NOCK_SMTP_HOST`, `NOCK_SMTP_PORT`, `NOCK_SMTP_SECURITY`, `NOCK_SMTP_USER`, `NOCK_SMTP_FROM` | from the mail provider | no (the user name is not secret, but keep it with the password) |
| `NOCK_SMTP_PASSWORD` | from the mail provider | **yes** |

- Never in the repository. VPS: a file `/etc/nock/nock.env` readable by root only,
  loaded by systemd (`EnvironmentFile=`). Fly: `fly secrets set`. Render: secret
  environment variables.
- Changing the operator token needs a restart (spec 038 "Out of scope").
- Keep a copy of the secrets in a password manager; the backups do not hold them.

## 8. Mail for spec 033

- Volume is tiny: at most 3 links per address and 10 per client address an hour
  (spec 033 decision 11). A free or entry tier is enough.
- Providers with EU data centres and an SMTP relay: Brevo (French), Mailjet,
  Scaleway Transactional Email, OVH. Pick one that signs a data processing
  agreement (section 11).
- The sender (`NOCK_SMTP_FROM`) uses your own domain, for example
  `connexion@<domain>`.
- DNS records on that domain: **SPF** (allow the provider), **DKIM** (the keys
  the provider gives), **DMARC** (start with `p=none` and a reporting address,
  then move to `quarantine`). Without them, sign-in links land in spam.
- Some VPS providers block outgoing mail ports on new accounts. Port 587
  (STARTTLS, the default of spec 033) is usually open; check with the provider.
- Before launch: send a link to Gmail, Outlook and Orange addresses and check that
  it arrives in the inbox.

## 9. Logs and monitoring within spec 038

Spec 038 makes the app's own logs clean: no access log, `warning` level, no client
address, token, address or chat text (spec 038 AC-3, spec 033 AC-10). It leaves
the hosting's logs out of scope (spec 038 "Out of scope"), so:

- **Reverse proxy** (A): no access log. Caddy writes none unless a `log` directive
  is added; nginx needs `access_log off;`. Error logs stay.
- **Platform proxy** (B, C): the platform's edge may keep its own request logs with
  client addresses. They are outside your control; list them in the privacy notice
  and the platform's data processing agreement covers them.
- **App logs**: stdout and stderr to journald (A) or the platform's log view.
  Keep them 14 days (journald `MaxRetentionSec=14day`).
- **Uptime**: an external check of `GET /` every minute or five (200 when the
  client is built, 503 when not, `src/nock/server.py:155-164`), alerting you by
  e-mail. The checker only sees its own requests, so it carries no player data.
- **Disk**: alert when the disk holding the database is 80 % full.
- **Game health**: the operator dashboard `/ops` (spec 038): rooms created,
  completion, server latency, disconnection rate. Look at it after each deploy.
- **Backups**: alert when the latest off-site backup is older than 26 hours.

## 10. Deploying updates

**What a restart costs.** Every event a player saw was committed first (spec 018
"Commit before broadcast"). On a clean stop the app saves a snapshot of every
live room (spec 018 AC-4 (d)). After the restart each room loads from the file on
its first lookup, every player becomes disconnected, and the page reconnects on
its own with its resume token within the 5-minute window, counted from the
restart (spec 017, spec 018 "After a restart", `resume_window_seconds`,
`src/nock/room.py:130`). Players see the "reconnecting" banner for a few seconds
and lose nothing. Edits typed during the gap stay queued in the page and are
resent (spec 017). Keep the downtime well under 5 minutes.

**Rules.**

- Stop the old process before starting the new one: never two processes on the
  same file (spec 018 "Out of scope"). So no blue-green or rolling deploy.
- Stop with `SIGTERM` (systemd and the platforms do), and give the process time to
  close (for example 30 s), so `close()` saves its snapshots. A kill is still
  safe (the log is replayed) but slower to load.
- Build `web/dist` before the restart, not in the live folder while players load
  pages: the server checks `index.html` on each request
  (`src/nock/server.py:155-164`).
- Deploy only a commit that passed the full gate in CI (`.github/workflows/ci.yml`),
  ideally a tag (`docs/build-plan.md`, `git tag v1.0.0`).
- Take a backup just before each deploy that changes the database (specs 032 and
  033 add tables and columns).

**Steps, option A** (by hand, or later by a workflow, section 13):

1. `git fetch --tags && git checkout v1.x.y` in a new release folder.
2. `uv sync --locked --no-dev`, `npm --prefix web ci`, `npm --prefix web run build`.
3. Backup (section 6).
4. Point the `current` link to the new folder and `systemctl restart nock`.
5. Check `GET /`, open a room, look at `/ops`. To roll back, point `current` back
   and restart (only while no database change happened in between).

**Steps, options B and C:** a Dockerfile builds the client and the Python
environment from a tagged commit; `fly deploy` or a Render deploy replaces the one
instance; the volume or disk stays.

## 11. GDPR checklist

The game is French-language, open to guests, and (V1) stores e-mail addresses.

- [ ] **Controller** named: you, or your company or association.
- [ ] **Legal notice** (mentions légales, required by French law for a public
      site): publisher, director of publication, host's name and address.
- [ ] **Privacy notice** in French, linked from every page, saying:
  - what is kept and for how long, from spec 038's table: nickname, player id and
    resume token, letters and chat of a room, until 30 days after its last edit
    (plus up to an hour); e-mail address and the account's rooms until the account
    is deleted (spec 033); game history, including team-mates' nicknames, until
    the account is deleted (spec 029); sign-in links 30 minutes; sessions 90 days;
    client addresses 60 seconds in memory for the anti-abuse throttles (specs 011,
    033, 038); app logs 14 days; backups 14 days (section 6);
  - why: to run the game (contract) and to prevent abuse (legitimate interest);
  - who receives the data: the processors below;
  - rights: deletion of the account from `/account` (spec 033); access, correction
    and other requests by e-mail to a contact address; complaint to the CNIL.
- [ ] **No cookie banner** needed: guests get no cookie, and the only cookie is
      the signed-in session, strictly needed (spec 038, spec 033). No tracker, no
      third-party request (spec 038 AC-2, spec 005).
- [ ] **Data processing agreements** (DPA) signed or accepted with: the host, the
      mail provider, the backup storage. With a US company (options B, C), check
      that its DPA covers transfers (standard contractual clauses or the
      EU-US Data Privacy Framework).
- [ ] **Record of processing** (registre des traitements): one page listing the
      above.
- [ ] **Breach procedure**: who decides, notification to the CNIL within 72 hours
      when personal data leaks.
- [ ] **Minors**: a word game attracts children. With no consent-based processing
      and no advertising, nothing more is required; the notice should still be
      readable by them.

## 12. Before the first public test

- [ ] Answers to section 0; option chosen.
- [ ] Grids with their licences on the server (spec 005).
- [ ] Domain, TLS, HTTP to HTTPS redirect.
- [ ] `NOCK_DATABASE` on the persistent disk; first backup and a restore test.
- [ ] Proxy addresses set if needed (section 1); a share link starts with
      `https://`; two players behind different networks can join one room.
- [ ] Operator token set; `/ops` works.
- [ ] V1: SMTP, SPF, DKIM, DMARC; a sign-in link reaches the inbox.
- [ ] Legal notice and privacy notice online.
- [ ] Uptime, disk and backup alerts.

## 13. Proposed next steps that need your approval

These are tooling, so they are your decision (`CLAUDE.md`, "Who may write what").
None is done.

1. **Dockerfile** (needed for B and C; optional for A): two stages, Node to build
   `web/dist`, then Python with uv (`uv sync --locked --no-dev`), running
   `python -m nock` as a non-root user, the repository tree copied in (section 1,
   files read from the source tree), `/data` as the volume.
2. **Deploy files**: for A, a systemd unit, a Caddyfile and a deploy script; for
   B, `fly.toml`; for C, `render.yaml`.
3. **Backup script** using `VACUUM INTO`, with encryption, upload, 14-day
   retention, and a timer; plus the restore-test steps as a script.
4. **Deploy workflow** in `.github/workflows/`: on a `v*` tag, after the gate
   passes, build and deploy. Needs a deploy secret in GitHub (an SSH key for A, an
   API token for B or C).
5. **Load test** (a spec): many rooms of 8 players on the chosen machine size, to
   know the capacity before a public launch (spec 036 measures one room only).
6. **Spec 011 note** on `FORWARDED_ALLOW_IPS` (section 1), if you want the spec to
   say how the client address is read behind a proxy.
7. **Deletion journal** (a spec), only if you want restores to re-apply account
   deletions on their own (section 6).
