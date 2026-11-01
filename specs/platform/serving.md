---
area: platform
file: serving
status: done
---

# platform/serving - Serving the client, the HTTP edge, environment settings

## Purpose

The process that runs the rooms also serves the built client, on the address
and with the database its environment gives, and bounds and labels every HTTP
answer so no browser keeps a stale page or frames one. A refused variable stops
it before it serves, with one line naming the variable.

## Depends on

- `product.md`: the page routes and their owners, what `python -m nock` runs
  (rule 27), the supported browsers and the socket frame size.
- `platform/server.md`: the store that `NOCK_DATABASE` names.
- `admin/operations.md`: the operator token's check and message, the ops API's
  `Cache-Control`.

## Rules

### Serving the client

1. The built client is `web/dist` of the repository, found from the package's
   location, never from the current directory.
2. A page route of `product.md`, when its owner serves it, answers the build's
   `index.html`, 200, `text/html`; `/r/<code>` does whenever the code is 6
   capitals or digits, whether or not the room exists.
3. A file directly in the build's root or its `assets/` folder is served at
   `/<name>` or `/assets/<name>`. Any other path that no route answers is 404,
   never `index.html`: a missing file, a folder, a deeper path, a name that
   would leave the build (encoded `..` or `\`, a drive's `:`).
4. Always 404, built or not: a path with a segment starting with `.` once
   decoded, even when the file exists; a path ending with `/` other than `/`,
   with no redirect (no answer of the app is 3xx); `/api`, any path under
   `/api/` with no route, and a plain HTTP request to a socket path; `GET
   /api/rooms`; the generated API documentation, which does not exist. Each of
   these 404s has the body `{"detail": "Not Found"}`.
5. While the build has no `index.html`, the app still starts, and a page route
   that would answer `index.html` answers 503, `text/plain`, naming `npm
   --prefix web run build`; one that would be 404 (`/r/abc123`, an unpublished
   grid, an unknown recap, `/ops` while off) stays 404, and the other routes
   answer as usual. A build made later is served without a restart.

### Environment settings

6. `python -m nock` runs `main()` (`src/nock/__main__.py`), which reads its
   variables at each call and checks them before it builds a server:
   `NOCK_OPERATOR_TOKEN` first (`admin/operations.md` rule 4), then
   `NOCK_HOST`, `NOCK_PORT` and `NOCK_DATABASE`, each only when set and not
   empty, then the four room lives and the sweep interval
   (`NOCK_CREATOR_SOLVED_ROOM_HOURS`, `NOCK_CREATOR_ROOM_HOURS`,
   `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS`, `NOCK_ANONYMOUS_ROOM_HOURS`,
   `NOCK_EXPIRY_SWEEP_MINUTES`, `lobby/lifetime.md` rule 7), then
   `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` (`lobby/rooms.md` rule 14), then
   `NOCK_SOCKETS_PER_ADDRESS` (`platform/realtime.md` rule 26), then the
   account variables by their own rules (`account/account.md` rule 2). What
   it runs: `product.md` rule 27.
7. `NOCK_HOST`, unset or empty `127.0.0.1`: only ASCII letters, ASCII digits,
   `.`, `-` and `:`. With `:` it is an IPv6 address that
   `ipaddress.IPv6Address` accepts, without brackets; else a name whose dots
   cut it into labels of 1 to 63 characters, where only the last may be
   empty. It is passed on as given.
8. `NOCK_PORT`, unset or empty 8000: ASCII digits only, any number of leading
   zeros, value 1 to 65535.
9. `NOCK_DATABASE`: a path with no character of Unicode general category Cc,
   Cf, Zl or Zp, except U+200C and U+200D; any other character passes.
   `main()` never changes it; the app reads it when it starts
   (`platform/server.md` rule 1).
10. A refused value stops `main()` before any server is built; `python -m
    nock` prints the message on stderr and exits with status 1. For
    `NOCK_HOST`, `NOCK_PORT`, `NOCK_DATABASE`, the five variables of
    `lobby/lifetime.md`, `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` and
    `NOCK_SOCKETS_PER_ADDRESS` the message is one line naming the variable and
    showing the value as `repr()` writes it, so it holds no character of Cc,
    Cf, Zl or Zp; with several of them refused, it names one, a room-life
    variable only when `NOCK_HOST`, `NOCK_PORT` and `NOCK_DATABASE` pass, the
    creation limit only when those and the five pass, and the socket cap only
    when the creation limit passes too.
    The messages of the operator token and the account variables, which never
    show a secret: `admin/operations.md` rule 4, `account/account.md` rule 3.

### The HTTP edge

11. A request body is at most 65,536 bytes, whatever the method and path. A
    request whose `Content-Length` is above that gets 413 `{"detail": "Content
    Too Large"}` with `Cache-Control: no-store` and its body unread; one sent
    without `Content-Length` (chunked) gets the same 413 once the app has read
    more than 65,536 bytes of it. This check comes before every route and
    every other rule of any domain, under `/api/ops` and `/api/account` too,
    whether operator pages and accounts are on or off: no route, guard or
    handler runs, so nothing is created, saved or counted by a throttle. The
    `Caddyfile` sets the same limit in front of the app: `request_body` with
    `max_size 64KiB`.
12. Every HTTP answer of the app, whatever its path and status (404, 405, 413,
    422, 401, 429, the 503 with no build, an unhandled error's 500), carries:
    - `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`;
    - `X-Content-Type-Options: nosniff`;
    - `Referrer-Policy: no-referrer`.

    No `X-Frame-Options`: every supported browser (`product.md` rule 10) obeys
    `frame-ancestors`. The `Caddyfile` sets none of them; the app's hold behind
    any proxy. A socket's opening handshake is not an HTTP answer: neither rule
    11 nor this one applies to it (its frames: `product.md` rule 26).
13. `Cache-Control` of the client's files, on their 200 only: `no-cache` on
    `index.html` from every page route (rule 2) and on a file directly in the
    build's root (`/favicon.svg`), whose names are not hashed; `public,
    max-age=31536000, immutable` on a file of `assets/`, whose names the build
    hashes. A 404 or 503 of these routes has no `Cache-Control`. The 413 of any
    path: rule 11. The API's: `admin/operations.md` rule 10,
    `account/account.md` rule 1.

## Acceptance criteria

- **AC-1** With a build, `GET /` answers `index.html`, 200, `text/html`, and
  `GET /r/ABC123` (no such room) `index.html` with 200; `/assets/app.js` and
  `/favicon.svg` their files; `/catalogue`, `/r/abc123`, `/r/ABC12`,
  `/r/ABC1234`, `/r/ABC123/extra`, `/assets/missing.js` and `/missing.svg`
  404, not `index.html`. (← 040 AC-1, 040 AC-2, 040 AC-4, 040 AC-5)
- **AC-2** With a build, `/api/nope`, `/api`, `/api/rooms` and an HTTP `GET
  /api/rooms/ABC123/ws` answer 404 `{"detail": "Not Found"}`; built or not, so
  do `/.env`, `/assets/.hidden.js`, `/.well-known/security.txt`, `/%2Eenv`,
  `/api/`, `/r/ABC123/`, `/favicon.svg/`, `/docs`, `/redoc` and
  `/openapi.json`, each with no redirect. (← 040 AC-3, 040 AC-27, 040 AC-28,
  040 AC-29)
- **AC-3** With no build, the app starts; `/` and `/r/ABC123` answer 503
  `text/plain` naming `npm --prefix web run build` while `/api/nope` answers
  404; once `index.html` is written, `/` serves it. (← 040 AC-6)
- **AC-4** `main()` runs `nock.server.app` with `ws_max_size` 8192 on
  127.0.0.1:8000 with both variables unset or `""`, on `0.0.0.0`:9123 when set
  so, on port 8000 for `"0" * 5000 + "8000"`, and on the host given for
  `example.org.`, 63 `a` then `.example`, `::1` and `::ffff:192.0.2.1`.
  (← 036 AC-10)
- **AC-5** `NOCK_PORT` `"0"`, `"65536"` or `" 8000"`, `NOCK_HOST` `"[::1]"`,
  `"my_host"`, `"a..b"` or `"bücher.example"`, and `NOCK_DATABASE`
  `"data/nock.sqlite3\n"` or `"nock\u200b.sqlite3"` each stop `main()` with a
  one-line message holding the name and `repr()` of the value, and no server
  runs; `python -m nock` exits with 1. (← 036 AC-11)
- **AC-6** `NOCK_DATABASE` `"/srv/jeu de mots/données/nock.sqlite3"`,
  `C:\Users\François\nock.sqlite3`, `"/srv/nock\u200ddata/nock.sqlite3"` or
  `"/srv/donn\udce9es/nock.sqlite3"` never stops `main()`, which leaves the
  variable as it was. (← 036 AC-12)
- **AC-7** `POST /api/rooms` with a `Content-Length` of 65,537 gets 413
  `{"detail": "Content Too Large"}` with `Cache-Control: no-store` and creates
  no room; with a body of
  exactly 65,536 bytes it gets the answer it gets without the limit, never 413.
- **AC-8** `POST /api/rooms` with a chunked body, no `Content-Length`, of
  65,537 bytes in all gets 413 `{"detail": "Content Too Large"}` and creates no
  room.
- **AC-9** The `Caddyfile`'s site block holds `request_body` with `max_size
  64KiB`.
- **AC-10** `GET /`, `/assets/app.js`, `/api/grids`, `/api/nope` (404), `POST
  /` (405), the 413 of AC-7, a 422 of `POST /api/rooms`, the ops dashboard's
  401, `/` with no build (503) and a route that raises (500) each carry
  `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`, and no
  `X-Frame-Options`.
- **AC-11** In each engine, the library, a room page where Ana joins and types
  `T`, and `/ops` with its dashboard work served under rule 12's headers, the
  browser reporting no violation of the policy.
- **AC-12** With a build, operator pages and accounts on, the 200 of `/`,
  `/r/ABC123`, `/ops`, `/account` and `/favicon.svg` each carry
  `Cache-Control: no-cache`.
- **AC-13** With a build, `/assets/app.js` carries `Cache-Control: public,
  max-age=31536000, immutable`; `/assets/missing.js` (404) has no
  `Cache-Control`.
- **AC-14** `POST /api/ops/dashboard` with operator pages on and off, and
  `POST /api/account` with accounts on and off, each with a `Content-Length` of
  65,537, get 413 `{"detail": "Content Too Large"}` with `Cache-Control:
  no-store`, never 404 or 405.

## Edge cases

- `NOCK_HOST` refuses a zone (`fe80::1%eth0`) and a port (`localhost:8000`)
  (AC-5).
- A missing asset's 404 is never kept by a browser (AC-13).

## Out of scope

- The run configuration, frame size and connection bounds: `product.md`.
- CORS (no cross-origin use). The `Cache-Control` of API answers other than
  the 413: the files rule 13 names.
- The store `NOCK_DATABASE` opens, the rooms in memory, undo, engine time:
  `platform/server.md`. The bounds of the room lives, the creation limit, the
  socket cap and the account variables: the files rule 6 names. Client routing
  and its pages: `client/shell.md`.

## Code

- `src/nock/server.py`: client routes, `WEB_DIST_DIR`, the body limit, headers
  and `Cache-Control` of rules 11 to 13. `Caddyfile` (repository root): the
  proxy's body limit. `src/nock/__main__.py`, `src/nock/settings.py`: the
  variables.
- Tests: `tests/test_spec_040_ac01_ac06_*`, `tests/test_spec_040_ac27_ac29_*`,
  `tests/test_spec_036_ac10_ac12_*`; `tests/test_serving_*` for AC-7 to AC-14,
  AC-11 in the browsers.
