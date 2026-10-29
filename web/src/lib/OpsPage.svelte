<script lang="ts">
  import { onMount } from 'svelte'
  import CatalogueFrame from './CatalogueFrame.svelte'
  import OpsReplay from './OpsReplay.svelte'
  import OpsSettings from './OpsSettings.svelte'
  import { t, type MessageKey } from './i18n'
  import {
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
  // Authorization header. Spec 048 draws it in the catalogue frame on the page
  // grey: the token form as a card, one line per waiting or failed state, then
  // the dashboard, the room lives (admin/overrides) and the replay as three cards.

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
  let figures = $state<DashboardFigures | null>(null)

  const metrics = $derived(figures === null ? [] : metricViews(figures))

  // Back to the token form after a 401 or a 429: the token is forgotten.
  function lock(reason: LockReason): void {
    removeOpsToken()
    token = null
    tokenError = reason === 'refused' ? 'ops.token_refused' : 'ops.throttled'
    pageState = 'locked'
  }

  // The answer to a dashboard request: its figures, the token form again after
  // a 401 or a 429, or the error for any other answer.
  function showDashboardAnswer(answer: OpsAnswer<DashboardFigures>): void {
    if (answer.kind === 'ok') {
      figures = answer.body
      pageState = 'ready'
    } else if (answer.kind === 'refused' || answer.kind === 'throttled') {
      lock(answer.kind)
    } else {
      pageState = 'error'
    }
  }

  // The first load, once the token is given or found in sessionStorage: the
  // page shows `loading` until the answer comes. It asks for no period, so the
  // server answers its default one.
  async function loadDashboard(): Promise<void> {
    if (token === null) {
      pageState = 'locked'
      return
    }
    pageState = 'loading'
    const answer = await fetchDashboard(token, null)
    showDashboardAnswer(answer)
  }

  // A press of a period button, or (with null, no period) the dashboard asked
  // again after a save of the settings card. The page stays `ready` while the
  // request is pending, so the dashboard, the replay and the focus on the button
  // stay.
  async function changePeriod(days: Period | null): Promise<void> {
    if (token === null) {
      return
    }
    const answer = await fetchDashboard(token, days)
    // A 401 or a 429 to the replay's request may have locked the page meanwhile.
    if (pageState !== 'ready') {
      return
    }
    showDashboardAnswer(answer)
  }

  function submitToken(event: SubmitEvent): void {
    event.preventDefault()
    token = typedToken
    writeOpsToken(typedToken)
    tokenError = null
    void loadDashboard()
  }

  // Once, when the page shows.
  onMount(() => {
    if (token !== null) {
      void loadDashboard()
    }
  })
</script>

<main class="nock-plain-page ops-page" data-testid="ops-page" data-state={pageState}>
  <CatalogueFrame>
    <h1 class="nock-page-heading">{t('ops.heading')}</h1>
    {#if pageState === 'locked'}
      <form class="nock-card" data-testid="ops-token-form" onsubmit={submitToken}>
        <div class="nock-field">
          <label for="ops-token-input">{t('ops.token_label')}</label>
          <input
            id="ops-token-input"
            class="nock-text-input"
            data-testid="ops-token-input"
            type="password"
            autocomplete="off"
            aria-invalid={tokenError !== null ? 'true' : undefined}
            aria-describedby={tokenError !== null ? 'ops-token-error' : undefined}
            bind:value={typedToken}
          />
        </div>
        {#if tokenError !== null}
          <p
            id="ops-token-error"
            class="nock-error-line ops-token-error"
            data-testid="ops-token-error"
            role="alert"
          >{t(tokenError)}</p>
        {/if}
        <button type="submit" class="nock-button nock-button-primary" data-testid="ops-token-submit"
          >{t('ops.token_submit')}</button
        >
      </form>
    {:else if pageState === 'loading'}
      <p class="nock-muted-line" data-testid="ops-state-line" role="status">{t('ops.loading')}</p>
    {:else if pageState === 'error'}
      <p class="nock-error-line" data-testid="ops-state-line" role="alert">{t('ops.error')}</p>
    {:else if figures !== null && token !== null}
      <section
        class="nock-card"
        data-testid="ops-dashboard"
        aria-labelledby="ops-dashboard-heading"
      >
        <h2 class="nock-card-title" id="ops-dashboard-heading">{t('ops.dashboard_heading')}</h2>
        <div class="nock-field" data-testid="ops-period-field">
          <span class="nock-field-label" id="ops-period-label">{t('ops.period_label')}</span>
          <div class="nock-button-row" role="group" aria-labelledby="ops-period-label">
            {#each figures.offered_days as days (days)}
              <button
                type="button"
                class="nock-chip"
                data-testid="ops-period"
                data-days={String(days)}
                aria-pressed={days === figures.days ? 'true' : 'false'}
                onclick={() => void changePeriod(days)}
              >
                {t(PERIOD_KEYS[days])}
              </button>
            {/each}
          </div>
        </div>
        <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
        <ul class="ops-metrics" role="list">
          {#each metrics as metric (metric.metric)}
            <li
              class="nock-card-text"
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
      <OpsSettings {token} onLocked={lock} onSaved={() => void changePeriod(null)} />
      <OpsReplay {token} onLocked={lock} />
    {/if}
  </CatalogueFrame>
</main>

<style>
  .ops-page {
    background: var(--nock-page);
  }

  /* The refusal 6 px under the input, as the screens sheet draws it (the
     card's gap is 12 px). */
  .ops-token-error {
    margin-top: -6px;
  }

  /* One tile per figure, as many per row as 270 px fit, one per row on a
     phone. */
  .ops-metrics {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 270px), 1fr));
    gap: 10px;
    justify-self: stretch;
    padding: 0;
    list-style: none;
  }

  .ops-metrics li {
    padding: 12px 14px;
    border: 1px solid var(--nock-line);
    border-radius: 8px;
    background: var(--nock-white);
    overflow-wrap: anywhere;
  }
</style>
