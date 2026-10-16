<script lang="ts">
  import { t } from './i18n'
  import {
    TIMER_REFRESH_MS,
    readTimerHidden,
    timerText,
    timerValueMs,
    writeTimerHidden,
  } from './timer'

  // The shared timer of spec 027 and its toggle: the first two items of the room
  // toolbar. The room page gives the timer as the page keeps it; this component
  // shows it, keeps it fresh while it runs, and remembers whether this browser
  // hides it. The toggle sends nothing to the server.
  let {
    baseMs,
    isRunning,
    anchor,
  }: {
    // The time counted when `anchor` was read, in milliseconds.
    baseMs: number
    // True while the room's timer counts.
    isRunning: boolean
    // The performance.now() reading of the moment `baseMs` was set.
    anchor: number
  } = $props()

  // The choice is read when the page loads, and holds for every room.
  let isShown = $state(!readTimerHidden())
  // The value on show, in whole milliseconds.
  let shownMs = $state(0)

  // Work the value out when the timer changes (a snapshot, a first letter, a
  // solve) or is shown again, then every TIMER_REFRESH_MS while it runs. A hidden
  // timer needs no clock.
  $effect(() => {
    if (!isShown) {
      return
    }
    function refresh(): void {
      shownMs = timerValueMs(baseMs, isRunning, anchor, performance.now())
    }
    refresh()
    if (!isRunning) {
      return
    }
    const refreshTimer = setInterval(refresh, TIMER_REFRESH_MS)
    return () => clearInterval(refreshTimer)
  })

  function toggleShown(): void {
    isShown = !isShown
    writeTimerHidden(!isShown)
  }
</script>

<!-- A role "timer" has an implicit aria-live of "off": a screen reader does not
     read every second. It is text, never a Tab stop. -->
{#if isShown}
  <span
    class="timer"
    data-testid="timer"
    role="timer"
    aria-label={t('timer.label')}
    data-running={String(isRunning)}
    data-elapsed-ms={String(shownMs)}>{timerText(shownMs)}</span
  >
{/if}
<button
  type="button"
  class="timer-toggle"
  data-testid="timer-toggle"
  aria-label={t('timer.toggle_label')}
  aria-pressed={isShown}
  onclick={toggleShown}>{t('timer.toggle')}</button
>

<style>
  /* One line, never shrunk by the toolbar, and digits of one width so that the
     text does not shake from one second to the next. */
  .timer {
    flex: none;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* A target of 24 by 24 CSS px at least, whatever the engine's button style
     (spec 035). It never shrinks in the toolbar's row. */
  .timer-toggle {
    flex: none;
    box-sizing: border-box;
    min-width: 24px;
    min-height: 24px;
  }
</style>
