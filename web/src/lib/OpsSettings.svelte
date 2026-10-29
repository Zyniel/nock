<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { t } from './i18n'
  import {
    fetchDryRun,
    fetchSettings,
    saveSetting,
    SETTING_TITLE_KEYS,
    SOURCE_KEYS,
    type LockReason,
    type OpsAnswer,
    type Setting,
    type SettingsList,
  } from './ops'

  // The card « Durées de vie des salons » of the operator's page
  // (admin/overrides): the four room lives and the sweep interval, each with its
  // effective value, its source, a number input, « Enregistrer » and « Rétablir ».
  // A life shorter than the effective one asks first how many rooms it deletes.

  type CardState = 'loading' | 'ready' | 'error'
  type Button = 'save' | 'reset'

  // The question that is open: the row and the button that asked, the value to
  // send (null for a reset) and the dry run's count.
  interface Question {
    name: string
    button: Button
    value: number | null
    count: number
  }

  interface Props {
    token: string
    // A 401 or a 429 of the card: the page goes back to the token form.
    onLocked: (reason: LockReason) => void
    // A save or a reset was done: the page asks the dashboard again.
    onSaved: () => void
  }

  const { token, onLocked, onSaved }: Props = $props()

  let cardState = $state<CardState>('loading')
  let durable = $state(true)
  let settings = $state<Setting[]>([])
  // What each number input holds, by setting name; null or undefined when empty.
  let typed = $state<Record<string, number | null | undefined>>({})
  // The error line of each row, by setting name; "" for none.
  let errors = $state<Record<string, string>>({})
  let question = $state<Question | null>(null)

  const SHORT_UNITS = { hours: 'h', minutes: 'min' }
  // The question's block, which « Enregistrer » and « Rétablir » disclose.
  const QUESTION_ID = 'ops-settings-question'

  function showList(list: SettingsList): void {
    durable = list.durable
    settings = list.settings
  }

  // A 401 or a 429 locks the page; any other failure is the row's error line.
  function showFailure(answer: OpsAnswer<unknown>, name: string): void {
    if (answer.kind === 'refused' || answer.kind === 'throttled') {
      onLocked(answer.kind)
    } else {
      errors[name] = t('ops.error')
    }
  }

  async function loadSettings(): Promise<void> {
    const answer = await fetchSettings(token)
    if (answer.kind === 'ok') {
      showList(answer.body)
      cardState = 'ready'
    } else if (answer.kind === 'refused' || answer.kind === 'throttled') {
      onLocked(answer.kind)
    } else {
      cardState = 'error'
    }
  }

  function buttonId(name: string, button: Button): string {
    return `ops-setting-${button}-${name}`
  }

  function inputId(name: string): string {
    return `ops-setting-${name}`
  }

  // The focus goes back to the button that asked, as a disclosure does.
  function focusButton(name: string, button: Button): void {
    document.getElementById(buttonId(name, button))?.focus()
  }

  // After a confirmed question: back to the button that asked, unless it is now
  // disabled (« Rétablir » with no override left), then to the row's input.
  function focusAfterConfirm(name: string, button: Button): void {
    const asking = document.getElementById(buttonId(name, button))
    if (asking instanceof HTMLButtonElement && !asking.disabled) {
      asking.focus()
    } else {
      document.getElementById(inputId(name))?.focus()
    }
  }

  function boundsText(setting: Setting): string {
    return t('ops.setting_out_of_bounds', {
      min: setting.min,
      max: setting.max,
      unit: SHORT_UNITS[setting.unit],
    })
  }

  function isWithinBounds(setting: Setting, value: number | null | undefined): value is number {
    return (
      typeof value === 'number' &&
      Number.isInteger(value) &&
      value >= setting.min &&
      value <= setting.max
    )
  }

  // Send the save (or the reset, with a null value) and show the answer.
  async function send(setting: Setting, value: number | null): Promise<void> {
    const answer = await saveSetting(token, setting.name, value)
    if (answer.kind !== 'ok') {
      showFailure(answer, setting.name)
      return
    }
    showList(answer.body)
    typed[setting.name] = null
    errors[setting.name] = ''
    onSaved()
  }

  // Ask how many rooms the shorter life deletes, and open the question.
  async function ask(setting: Setting, button: Button, value: number | null): Promise<void> {
    const answer = await fetchDryRun(token, setting.name, value)
    if (answer.kind === 'ok') {
      question = { name: setting.name, button, value, count: answer.body.rooms }
    } else {
      showFailure(answer, setting.name)
    }
  }

  // A press of « Enregistrer » or « Rétablir ». A second press of the button
  // that asked closes the question with nothing sent.
  async function press(setting: Setting, button: Button): Promise<void> {
    if (question !== null && question.name === setting.name && question.button === button) {
      question = null
      return
    }
    question = null
    errors[setting.name] = ''
    let value: number | null = null
    if (button === 'save') {
      const typedValue = typed[setting.name]
      if (!isWithinBounds(setting, typedValue)) {
        errors[setting.name] = boundsText(setting)
        return
      }
      value = typedValue
    }
    // The value a reset falls back to is the variable's, else the default.
    const proposed = value ?? setting.environment ?? setting.default
    if (setting.unit === 'hours' && proposed < setting.value) {
      await ask(setting, button, value)
    } else {
      await send(setting, value)
    }
  }

  function cancel(): void {
    if (question === null) {
      return
    }
    const { name, button } = question
    question = null
    focusButton(name, button)
  }

  async function confirm(): Promise<void> {
    if (question === null) {
      return
    }
    const { name, button, value } = question
    const setting = settings.find((candidate) => candidate.name === name)
    question = null
    if (setting === undefined) {
      return
    }
    await send(setting, value)
    // Let the rows show the answer, so that « Rétablir » is disabled by now.
    await tick()
    focusAfterConfirm(name, button)
  }

  function valueText(setting: Setting): string {
    const key = setting.unit === 'hours' ? 'ops.hours_value' : 'ops.minutes_value'
    return t(key, { value: setting.value })
  }

  function questionText(count: number): string {
    return t(count <= 1 ? 'ops.setting_confirm_one' : 'ops.setting_confirm_many', { count })
  }

  onMount(() => {
    void loadSettings()
  })
</script>

<section class="nock-card" data-testid="ops-settings" aria-labelledby="ops-settings-heading">
  <h2 class="nock-card-title" id="ops-settings-heading">{t('ops.settings_heading')}</h2>
  {#if cardState === 'loading'}
    <p class="nock-muted-line" data-testid="ops-settings-state-line" role="status">
      {t('ops.loading')}
    </p>
  {:else if cardState === 'error'}
    <p class="nock-error-line" data-testid="ops-settings-state-line" role="alert">
      {t('ops.error')}
    </p>
  {:else}
    {#if !durable}
      <p class="nock-muted-line" data-testid="ops-settings-in-memory">
        {t('ops.settings_in_memory')}
      </p>
    {/if}
    <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
    <ul class="ops-settings-rows" role="list">
      {#each settings as setting (setting.name)}
        {@const rowInputId = inputId(setting.name)}
        {@const errorId = `ops-setting-error-${setting.name}`}
        {@const hasError = errors[setting.name] !== undefined && errors[setting.name] !== ''}
        {@const isSavePressed =
          question !== null && question.name === setting.name && question.button === 'save'}
        {@const isResetPressed =
          question !== null && question.name === setting.name && question.button === 'reset'}
        <li
          class="nock-list-row ops-setting-row"
          data-testid="ops-setting"
          data-name={setting.name}
        >
          <div class="nock-row-text ops-setting-text">
            <label class="ops-setting-title" for={rowInputId}
              >{t(SETTING_TITLE_KEYS[setting.name])}</label
            >
            <span class="ops-setting-value"
              >{valueText(setting)}<span class="ops-setting-tag" data-source={setting.source}
                >{t(SOURCE_KEYS[setting.source])}</span
              ></span
            >
          </div>
          <form
            class="ops-setting-form"
            novalidate
            onsubmit={(event) => {
              event.preventDefault()
              void press(setting, 'save')
            }}
          >
            <input
              id={rowInputId}
              class="nock-text-input ops-setting-input"
              data-testid="ops-setting-input"
              type="number"
              inputmode="numeric"
              min={setting.min}
              max={setting.max}
              step="1"
              bind:value={typed[setting.name]}
              aria-invalid={hasError ? 'true' : undefined}
              aria-describedby={hasError ? errorId : undefined}
            />
            <!-- Pressed (quiet) while the question it asked is open. -->
            <button
              type="submit"
              id={buttonId(setting.name, 'save')}
              class="nock-button"
              class:nock-button-primary={!isSavePressed}
              class:nock-button-quiet={isSavePressed}
              data-testid="ops-setting-save"
              aria-expanded={isSavePressed ? 'true' : 'false'}
              aria-controls={QUESTION_ID}
              >{t('ops.setting_save')}</button
            >
            <button
              type="button"
              id={buttonId(setting.name, 'reset')}
              class="nock-button nock-button-quiet"
              data-testid="ops-setting-reset"
              aria-expanded={isResetPressed ? 'true' : 'false'}
              aria-controls={QUESTION_ID}
              disabled={setting.source !== 'override'}
              onclick={() => void press(setting, 'reset')}>{t('ops.setting_reset')}</button
            >
          </form>
          {#if hasError}
            <p class="nock-error-line ops-setting-error" id={errorId} role="alert">
              {errors[setting.name]}
            </p>
          {/if}
        </li>
      {/each}
    </ul>
    {#if question !== null}
      <div id={QUESTION_ID} class="ops-settings-question" data-testid="ops-settings-question">
        <p class="nock-card-text">{questionText(question.count)}</p>
        <div class="nock-button-row">
          <button
            type="button"
            class="nock-button nock-button-primary"
            data-testid="ops-settings-confirm"
            onclick={() => void confirm()}>{t('ops.setting_confirm')}</button
          >
          <button
            type="button"
            class="nock-button nock-button-secondary"
            data-testid="ops-settings-cancel"
            onclick={cancel}>{t('ops.setting_cancel')}</button
          >
        </div>
      </div>
    {/if}
  {/if}
</section>

<style>
  /* Five rows, 10 px apart, as wide as the card's content. */
  .ops-settings-rows {
    display: grid;
    gap: 10px;
    justify-self: stretch;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* A list row (.nock-list-row) that wraps: the form goes under the text column
     when they do not fit side by side, and the error line takes a full line. */
  .ops-setting-row {
    flex-wrap: wrap;
  }

  .ops-setting-text {
    flex-basis: 160px;
    min-width: 160px;
  }

  .ops-setting-title {
    font: 700 1rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
    overflow-wrap: anywhere;
  }

  /* The effective value and its source tag, 8 px apart. */
  .ops-setting-value {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font: 400 0.95rem var(--nock-font-ui);
    color: var(--nock-ink);
    font-variant-numeric: tabular-nums;
  }

  .ops-setting-tag {
    padding: 2px 8px;
    border-radius: 10px;
    font: 600 0.72rem/1.3 var(--nock-font-ui);
    color: var(--nock-navy);
    background: var(--nock-clue-bg);
  }

  .ops-setting-form {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  /* 64 px wide, without the spin buttons that would hide the digits. */
  .ops-setting-input {
    width: 64px;
    padding: 8px 10px;
    text-align: center;
    appearance: textfield;
  }

  .ops-setting-input::-webkit-inner-spin-button,
  .ops-setting-input::-webkit-outer-spin-button {
    margin: 0;
    appearance: none;
  }

  .ops-setting-error {
    flex-basis: 100%;
  }

  /* The question stands under the rows, 12 px under a line-grey divider, as
     wide as the card's content. */
  .ops-settings-question {
    display: grid;
    gap: 12px;
    justify-items: start;
    justify-self: stretch;
    padding-top: 12px;
    border-top: 1px solid var(--nock-line);
  }

  /* Under 600 px the row stacks: the text column, then the form. */
  @media (max-width: 599px) {
    .ops-setting-text {
      flex-basis: 100%;
    }
  }
</style>
