<script lang="ts">
  import { t } from './i18n'
  import { TIMER_REFRESH_MS, timerText, timerValueMs } from './timer'

  // The shared timer of spec 027, in the top bar's timer slot (spec 043). The
  // room page gives the timer as the page keeps it and puts this component on
  // the page only while the timer is shown; it keeps the value fresh while the
  // timer runs.
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

  // The value on show, in whole milliseconds.
  let shownMs = $state(0)

  // Work the value out when the timer changes (a snapshot, a first letter, a
  // solve), then every TIMER_REFRESH_MS while it runs.
  $effect(() => {
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
</script>

<!-- A role "timer" has an implicit aria-live of "off": a screen reader does not
     read every second. It is text, never a Tab stop. -->
<span
  class="timer"
  data-testid="timer"
  role="timer"
  aria-label={t('timer.label')}
  data-running={String(isRunning)}
  data-elapsed-ms={String(shownMs)}>{timerText(shownMs)}</span
>

<style>
  /* One line, never shrunk by the top bar, and digits of one width so that the
     text does not shake from one second to the next (spec 043). */
  .timer {
    flex: none;
    padding: 0 4px;
    font: 600 1.15rem/1 var(--nock-font-ui);
    color: var(--nock-navy);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
</style>
