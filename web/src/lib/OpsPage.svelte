<script lang="ts">
  import { onMount } from 'svelte'
  import OpsReplay from './OpsReplay.svelte'
  import { t, type MessageKey } from './i18n'
  import {
    FIRST_PERIOD,
    PERIODS,
    fetchDashboard,
    metricViews,
    readOpsToken,
    removeOpsToken,
    writeOpsToken,
    type DashboardFigures,
    type LockReason,
    type OpsAnswer,
    type Period,
  } from './ops'

  // The operator's page of spec 038, at /ops: the token form, then the dashboard
  // of the rooms and the replay of one room. The token is kept in this tab's
  // sessionStorage only, and every ops API request sends it in its
  // Authorization header.

  type PageState = 'locked' | 'loading' | 'ready' | 'error'

  const PERIOD_KEYS: Record<Period, MessageKey> = {
    1: 'ops.period.one_day',
    7: 'ops.period.seven_days',
    30: 'ops.period.thirty_days',
  }

  // With a token kept by this tab, the dashboard loads at once, without the form.
  const keptToken = readOpsToken()

  let token = $state<string | null>(keptToken)
  let pageState: PageState = $state(keptToken === null ? 'locked' : 'loading')
  let tokenError = $state<MessageKey | null>(null)
  let typedToken = $state('')
  let shownPeriod: Period = $state(FIRST_PERIOD)
  let figures = $state<DashboardFigures | null>(null)

  const metrics = $derived(figures === null ? [] : metricViews(figures))

  // Back to the token form after a 401 or a 429: the token is forgotten.
  function lock(reason: LockReason): void {
    removeOpsToken()
    token = null
    tokenError = reason === 'refused' ? 'ops.token_refused' : 'ops.throttled'
    pageState = 'locked'
  }

  // The answer to a dashboard request of `days` days: its figures, the token
  // form again after a 401 or a 429, or the error for any other answer.
  function showDashboardAnswer(days: Period, answer: OpsAnswer<DashboardFigures>): void {
    if (answer.kind === 'ok') {
      figures = answer.body
      shownPeriod = days
      pageState = 'ready'
    } else if (answer.kind === 'refused' || answer.kind === 'throttled') {
      lock(answer.kind)
    } else {
      pageState = 'error'
    }
  }

  // The first load, once the token is given or found in sessionStorage: the
  // page shows `loading` until the answer comes.
  async function loadDashboard(days: Period): Promise<void> {
    if (token === null) {
      pageState = 'locked'
      return
    }
    pageState = 'loading'
    const answer = await fetchDashboard(token, days)
    showDashboardAnswer(days, answer)
  }

  // A press of a period button. The page stays `ready` while the request is
  // pending, so the dashboard, the replay and the focus on the button stay.
  async function changePeriod(days: Period): Promise<void> {
    if (token === null) {
      return
    }
    const answer = await fetchDashboard(token, days)
    // A 401 or a 429 to the replay's request may have locked the page meanwhile.
    if (pageState !== 'ready') {
      return
    }
    showDashboardAnswer(days, answer)
  }

  function submitToken(event: SubmitEvent): void {
    event.preventDefault()
    token = typedToken
    writeOpsToken(typedToken)
    tokenError = null
    void loadDashboard(shownPeriod)
  }

  // Once, when the page shows.
  onMount(() => {
    if (token !== null) {
      void loadDashboard(shownPeriod)
    }
  })
</script>

<main class="ops-page" data-testid="ops-page" data-state={pageState}>
  <h1>{t('ops.heading')}</h1>
  {#if pageState === 'locked'}
    <form class="ops-token-form" data-testid="ops-token-form" onsubmit={submitToken}>
      <label for="ops-token-input">{t('ops.token_label')}</label>
      <input
        id="ops-token-input"
        data-testid="ops-token-input"
        type="password"
        autocomplete="off"
        bind:value={typedToken}
      />
      <button type="submit" data-testid="ops-token-submit">{t('ops.token_submit')}</button>
    </form>
    {#if tokenError !== null}
      <p data-testid="ops-token-error" role="alert">{t(tokenError)}</p>
    {/if}
  {:else if pageState === 'loading'}
    <p role="status">{t('ops.loading')}</p>
  {:else if pageState === 'error'}
    <p>{t('ops.error')}</p>
  {:else if figures !== null && token !== null}
    <section
      class="ops-dashboard"
      data-testid="ops-dashboard"
      aria-labelledby="ops-dashboard-heading"
    >
      <h2 id="ops-dashboard-heading">{t('ops.dashboard_heading')}</h2>
      <div class="ops-periods" role="group" aria-label={t('ops.period_label')}>
        {#each PERIODS as days (days)}
          <button
            type="button"
            data-testid="ops-period"
            data-days={String(days)}
            aria-pressed={days === shownPeriod ? 'true' : 'false'}
            onclick={() => void changePeriod(days)}
          >
            {t(PERIOD_KEYS[days])}
          </button>
        {/each}
      </div>
      <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
      <ul class="ops-metrics" role="list">
        {#each metrics as metric (metric.metric)}
          <li
            data-testid="ops-metric"
            data-metric={metric.metric}
            data-value={metric.value}
            data-p95={metric.p95}
          >
            {metric.text}
          </li>
        {/each}
      </ul>
    </section>
    <OpsReplay {token} onLocked={lock} />
  {/if}
</main>

<style>
  .ops-dashboard h2 {
    margin: 1.5rem 0 0.5rem;
    font-size: 1.25rem;
  }

  .ops-token-form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .ops-token-form input {
    min-width: 0;
    max-width: 100%;
  }

  /* The buttons wrap in a narrow window, so the page never scrolls sideways. */
  .ops-periods {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0 0 1rem;
  }

  .ops-periods button {
    padding: 0.4rem 0.75rem;
    border: 1px solid #1f2330;
    border-radius: 0.25rem;
    background: #ffffff;
    color: #1f2330;
    font: inherit;
  }

  .ops-periods button[aria-pressed='true'] {
    background: #1f2330;
    color: #ffffff;
  }

  .ops-metrics {
    display: grid;
    gap: 0.5rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .ops-metrics li {
    overflow-wrap: anywhere;
  }
</style>
