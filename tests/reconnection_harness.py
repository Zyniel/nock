"""Shared setup of the tests of `platform/reconnection.md` AC-6 to AC-9 and of the
other domains' tests of the page's connection (`social/chat.md` AC-23).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in:

- `test_reconnection_hidden_page.py`: AC-6, a hidden page the browser held back.
- `test_reconnection_retries.py`: AC-7 (the 6-second connect limit) and AC-8 (the
  jitter of the retry delays).
- `test_reconnection_worker_pings.py`: AC-9, a hidden page whose own timers stop,
  on the live server and in real time (it runs on its own, `SERIAL_TEST_FILES`).
- `test_spec_017_ac05_long_absence.py` uses the socket stand-ins too.

AC-6 to AC-8 run on spec 017's mocked room (`spec017_harness.joined_room`) and its
frozen page clock, moved by hand with `advance_page`. What a mocked socket cannot
do is done in the page by the stand-ins of `SOCKET_STAND_INS_SCRIPT`, which wraps the
page's `WebSocket` (it is added after the mock, so it wraps the mocked one):

- `window.__socketTimes`: the page clock (`performance.now()`) at the creation of
  every socket the page makes, in order, so a test reads exactly when a try came.
- `window.__hangNext`: the next sockets stay CONNECTING for ever, as on a network
  that never answers; `window.__hung` counts them, `window.__hungCloses` counts
  those the page closed and `window.__hungClosedAt` holds the page clock of the
  last such close.
- `window.__deafClose`: every socket is a controlled one (below).
- `window.__holdOpenNext`: the next socket is a controlled one whose `open` event
  waits for `window.__releaseOpen()`; until then it reads CONNECTING.
- `window.__controlAll`: every socket is a controlled one, so that
  `window.__cutQuietly()` can take the newest away without telling the page.

A controlled socket wraps the mocked one. Its `close()` is recorded in
`window.__pageCloses` and goes no further: the server side never sees it and the
page never gets a `close` event, while messages still arrive (as on a dead
network). After `window.__cutQuietly()` it reads CLOSING, drops what the page
sends (as a browser does on a socket that is no longer open) and passes nothing
on to the page, until `window.__deliverClose(code)` gives the page its `close`
event: the state of a socket that is no longer open while the page has not yet
seen its close.

Readings where the specs leave room:

- "The page is hidden": `document.hidden` and `document.visibilityState` read as
  `VISIBILITY_SCRIPT` sets them, and a `visibilitychange` event on `document`
  follows each change (`set_page_hidden`).
- "Its timers run late" (AC-6, "the browser holds back its timers, its worker's
  too"): `page.clock.fast_forward`, which moves the page clock (`Date` and
  `performance.now()`) at once and then fires each timer that came due meanwhile
  once, late (Playwright's model of a laptop lid closed and opened), on a page
  loaded without `Worker` (`spec017_harness.keep_pings_on_the_page_clock`).
- "Its own timers stop firing" (AC-9): Playwright's page clock, installed before
  the page loads and paused once the page is hidden. It does not reach a
  dedicated worker, whose timers keep running in real time.
- "Every random draw at its lowest" or "highest": `Math.random` returns 0, or the
  largest number below 1, the page drawing each delay as the base delay times
  0.8 plus 0.4 times `Math.random()` (`RANDOM_AT_LOWEST_SCRIPT`,
  `RANDOM_AT_HIGHEST_SCRIPT`).
"""

from __future__ import annotations

import math

from playwright.sync_api import Page

from spec017_harness import advance_page

SOCKET_STAND_INS_SCRIPT = """
(() => {
  const RealWebSocket = window.WebSocket;
  window.__socketTimes = [];
  window.__hangNext = false;
  window.__deafClose = false;
  window.__holdOpenNext = false;
  window.__controlAll = false;
  window.__hung = 0;
  window.__hungCloses = 0;
  window.__hungClosedAt = null;
  window.__pageCloses = [];
  window.__controlled = [];
  class HangingSocket extends EventTarget {
    constructor(url) {
      super();
      this.url = String(url);
      this.readyState = 0;
      this.protocol = '';
      this.extensions = '';
      this.bufferedAmount = 0;
      this.binaryType = 'blob';
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
    }
    send() { throw new DOMException('not open', 'InvalidStateError'); }
    close() {
      if (this.readyState < 2) {
        window.__hungCloses += 1;
        window.__hungClosedAt = performance.now();
      }
      this.readyState = 2;
    }
  }
  class ControlledSocket extends EventTarget {
    constructor(url, protocols, holdOpen) {
      super();
      this._ws = protocols === undefined
        ? new RealWebSocket(url) : new RealWebSocket(url, protocols);
      this._closedByPage = false;
      this._opened = !holdOpen;
      this._openWaiting = false;
      this._quiet = false;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      for (const type of ['open', 'message', 'error', 'close']) {
        this._ws.addEventListener(type, (event) => this._arrive(type, event));
      }
      window.__controlled.push(this);
    }
    _arrive(type, event) {
      if (this._quiet) { return; }
      if (type === 'close' && this._closedByPage) { return; }
      if (type === 'open' && !this._opened) {
        this._openWaiting = true;
        return;
      }
      this._dispatch(type, event);
    }
    _dispatch(type, event) {
      let copy = new Event(type);
      if (type === 'message') {
        copy = new MessageEvent('message', { data: event.data });
      }
      if (type === 'close') {
        copy = new CloseEvent('close', { code: event.code, reason: event.reason });
      }
      this.dispatchEvent(copy);
      const handler = this['on' + type];
      if (typeof handler === 'function') { handler.call(this, copy); }
    }
    releaseOpen() {
      this._opened = true;
      if (this._openWaiting) {
        this._openWaiting = false;
        this._dispatch('open', new Event('open'));
      }
    }
    deliverClose(code) {
      this._dispatch('close', { code: code, reason: '' });
    }
    get url() { return this._ws.url; }
    get protocol() { return this._ws.protocol; }
    get extensions() { return this._ws.extensions; }
    get bufferedAmount() { return this._ws.bufferedAmount; }
    get binaryType() { return this._ws.binaryType; }
    set binaryType(value) { this._ws.binaryType = value; }
    get readyState() {
      if (this._closedByPage || this._quiet) { return 2; }
      if (!this._opened) { return 0; }
      return this._ws.readyState;
    }
    send(data) {
      if (this._closedByPage || this._quiet) { return; }
      if (!this._opened) {
        throw new DOMException('not open', 'InvalidStateError');
      }
      this._ws.send(data);
    }
    close(code) {
      this._closedByPage = true;
      window.__pageCloses.push(code === undefined ? null : code);
    }
  }
  const newest = () => window.__controlled[window.__controlled.length - 1];
  window.__releaseOpen = () => newest().releaseOpen();
  window.__cutQuietly = () => { newest()._quiet = true; };
  window.__deliverClose = (code) => newest().deliverClose(code);
  function PatchedWebSocket(url, protocols) {
    window.__socketTimes.push(performance.now());
    if (window.__hangNext) {
      window.__hung += 1;
      return new HangingSocket(url);
    }
    if (window.__holdOpenNext) {
      window.__holdOpenNext = false;
      return new ControlledSocket(url, protocols, true);
    }
    if (window.__deafClose || window.__controlAll) {
      return new ControlledSocket(url, protocols, false);
    }
    if (protocols === undefined) { return new RealWebSocket(url); }
    return new RealWebSocket(url, protocols);
  }
  PatchedWebSocket.prototype = RealWebSocket.prototype;
  PatchedWebSocket.CONNECTING = 0;
  PatchedWebSocket.OPEN = 1;
  PatchedWebSocket.CLOSING = 2;
  PatchedWebSocket.CLOSED = 3;
  window.WebSocket = PatchedWebSocket;
})();
"""
CONTROL_ALL_SCRIPT = SOCKET_STAND_INS_SCRIPT + "window.__controlAll = true;"

VISIBILITY_SCRIPT = """
(() => {
  let hidden = false;
  Object.defineProperty(document, 'hidden', {
    configurable: true, get: () => hidden,
  });
  Object.defineProperty(document, 'visibilityState', {
    configurable: true, get: () => (hidden ? 'hidden' : 'visible'),
  });
  window.__setPageHidden = (value) => {
    hidden = value;
    document.dispatchEvent(new Event('visibilitychange'));
  };
})();
"""

RANDOM_AT_LOWEST_SCRIPT = "Math.random = () => 0;"
# The largest number `Math.random` can return: 1 - 2^-53.
RANDOM_AT_HIGHEST_SCRIPT = "Math.random = () => 1 - Number.EPSILON / 2;"

ABNORMAL_CLOSE = 1006  # the close code of a socket the network took away


def set_page_hidden(page: Page, hidden: bool) -> None:
    """Hide the page, or show it again, as `VISIBILITY_SCRIPT` lets a test do."""
    page.evaluate("hidden => window.__setPageHidden(hidden)", hidden)


def page_time(page: Page) -> float:
    """Return the page clock, `performance.now()`, in milliseconds."""
    found = page.evaluate("performance.now()")
    assert isinstance(found, int | float), found
    return float(found)


def socket_times(page: Page) -> list[float]:
    """Return the page clock at the creation of each socket the page made."""
    found = page.evaluate("window.__socketTimes")
    assert isinstance(found, list), found
    times: list[float] = []
    for value in found:
        assert isinstance(value, int | float), found
        times.append(float(value))
    return times


def page_number(page: Page, expression: str) -> float:
    """Return a number the stand-ins keep, such as `window.__hungCloses`."""
    found = page.evaluate(expression)
    assert isinstance(found, int | float), (expression, found)
    return float(found)


def advance_page_to(page: Page, target_ms: float) -> None:
    """Move the frozen page clock up to `target_ms`, or the first whole ms after.

    Args:
        page: A page whose clock is paused.
        target_ms: The page clock to reach, in milliseconds.
    """
    left_ms = math.ceil(target_ms - page_time(page))
    assert left_ms > 0, f"the page clock is already past {target_ms}"
    advance_page(page, left_ms)


def advance_page_short_of(page: Page, target_ms: float) -> None:
    """Move the frozen page clock to the last whole ms at or before `target_ms`."""
    left_ms = math.floor(target_ms - page_time(page))
    assert left_ms > 0, f"the page clock is already past {target_ms}"
    advance_page(page, left_ms)


def cut_quietly(page: Page) -> None:
    """Take the newest socket away without telling the page (`CONTROL_ALL_SCRIPT`)."""
    page.evaluate("window.__cutQuietly()")


def deliver_close(page: Page, code: int = ABNORMAL_CLOSE) -> None:
    """Give the page the `close` event of the socket `cut_quietly` took away."""
    page.evaluate("code => window.__deliverClose(code)", code)


def release_open(page: Page) -> None:
    """Let the socket made under `window.__holdOpenNext` open."""
    page.evaluate("window.__releaseOpen()")
