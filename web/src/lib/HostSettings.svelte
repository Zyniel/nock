<script lang="ts">
  // The host's settings (spec 043, "Room sheets"; spec 014): a room sheet. The
  // lock switch sends at once; the form sends the help mode and the reveal
  // allowance when it is saved, then closes the sheet. A count that is not a
  // whole number from 0 to 99 sends nothing: the sheet stays open and shows
  // the error line (lobby/host.md rule 8).
  import { t } from './i18n'
  import { isValidCount } from './revealCount'
  import RoomSheet from './RoomSheet.svelte'

  let {
    layout,
    isLocked,
    helpMode = $bindable(),
    letters = $bindable(),
    words = $bindable(),
    onToggleLock,
    onSave,
    onClosed,
  }: {
    layout: 'sheet' | 'column'
    // The room's `settings.locked`.
    isLocked: boolean
    // The values of the form; the room page sets them from the room's settings.
    helpMode: string
    letters: number | null
    words: number | null
    onToggleLock: () => void
    // Send the form's values. Returns false when they are not valid: the sheet
    // then stays open.
    onSave: () => boolean
    // The sheet closed: by Escape, the backdrop, or a save.
    onClosed: () => void
  } = $props()

  const HELP_MODES = ['free', 'vote', 'none'] as const
  const COUNT_ERROR_ID = 'settings-count-error'

  let sheet: RoomSheet | undefined = $state()
  let lettersInput: HTMLInputElement | null = $state(null)
  let wordsInput: HTMLInputElement | null = $state(null)
  // The counts the last « Enregistrer » refused.
  let isLettersRefused = $state(false)
  let isWordsRefused = $state(false)

  // Show the sheet over the page.
  export function open(): void {
    sheet?.open()
  }

  // Close the sheet if it is open (the room is gone, or the host role went).
  // Returns whether it was open.
  export function close(): boolean {
    return sheet?.close() ?? false
  }

  // A close, whatever the cause, clears the marks.
  function sheetClosed(): void {
    isLettersRefused = false
    isWordsRefused = false
    onClosed()
  }

  function submit(event: SubmitEvent): void {
    event.preventDefault()
    isLettersRefused = !isValidCount(letters)
    isWordsRefused = !isValidCount(words)
    if (isLettersRefused) {
      lettersInput?.focus()
      return
    }
    if (isWordsRefused) {
      wordsInput?.focus()
      return
    }
    if (onSave()) {
      sheet?.close()
    }
  }
</script>

<RoomSheet
  bind:this={sheet}
  {layout}
  title={t('settings.heading')}
  titleId="host-settings-title"
  testId="host-settings"
  canCancel={true}
  closesOnBackdrop={true}
  onClosed={sheetClosed}
>
  <div class="switch-row">
    <span class="switch-label">{t('host.lock')}</span>
    <button
      type="button"
      class="switch"
      data-testid="lock-room"
      aria-pressed={isLocked}
      aria-label={t('host.lock')}
      onclick={onToggleLock}><span class="switch-knob"></span></button
    >
  </div>
  <form class="settings-form" data-testid="settings-form" novalidate onsubmit={submit}>
    <fieldset class="help-mode" data-testid="help-mode-select">
      <legend class="field-label">{t('settings.help_mode_label')}</legend>
      <div class="segments">
        {#each HELP_MODES as mode (mode)}
          <label class="segment" class:checked={helpMode === mode}
            ><input
              type="radio"
              name="help-mode"
              value={mode}
              data-testid="help-mode-option"
              bind:group={helpMode}
            /><span>{t(`settings.help_mode.${mode}`)}</span></label
          >
        {/each}
      </div>
    </fieldset>
    <div class="number-fields">
      <div class="field">
        <label class="field-label" for="reveal-letters-input"
          >{t('settings.reveal_letters_label')}</label
        >
        <input
          id="reveal-letters-input"
          class="number-input"
          type="number"
          data-testid="reveal-letters-input"
          min="0"
          max="99"
          step="1"
          aria-invalid={isLettersRefused ? 'true' : undefined}
          aria-describedby={isLettersRefused ? COUNT_ERROR_ID : undefined}
          bind:this={lettersInput}
          bind:value={letters}
        />
      </div>
      <div class="field">
        <label class="field-label" for="reveal-words-input"
          >{t('settings.reveal_words_label')}</label
        >
        <input
          id="reveal-words-input"
          class="number-input"
          type="number"
          data-testid="reveal-words-input"
          min="0"
          max="99"
          step="1"
          aria-invalid={isWordsRefused ? 'true' : undefined}
          aria-describedby={isWordsRefused ? COUNT_ERROR_ID : undefined}
          bind:this={wordsInput}
          bind:value={words}
        />
      </div>
    </div>
    {#if isLettersRefused || isWordsRefused}
      <p id={COUNT_ERROR_ID} class="nock-error-line" role="alert">
        {t('settings.error.count')}
      </p>
    {/if}
    <button
      type="submit"
      class="nock-button nock-button-primary settings-save"
      data-testid="settings-save">{t('settings.save')}</button
    >
  </form>
</RoomSheet>

<style>
  /* The switch row (specs/_design/foundation.md « Components »): the label left, the switch right. */
  .switch-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font: 500 0.95rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
  }

  /* The switch: a 42 by 24 track, rule grey when off and navy when on, with an
     18 px white knob. */
  .switch {
    position: relative;
    flex: none;
    box-sizing: border-box;
    width: 42px;
    height: 24px;
    margin: 0;
    padding: 0;
    border: 0;
    border-radius: 12px;
    background: var(--nock-rule);
    cursor: pointer;
  }

  .switch[aria-pressed='true'] {
    background: var(--nock-navy);
  }

  .switch-knob {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--nock-white);
  }

  .switch[aria-pressed='true'] .switch-knob {
    left: 21px;
  }

  .settings-form {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .help-mode {
    min-width: 0;
    margin: 0;
    padding: 0;
    border: 0;
  }

  /* The field label style (specs/_design/foundation.md « Typography »). */
  .field-label {
    padding: 0;
    font: 600 0.85rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
    white-space: nowrap;
  }

  .help-mode legend {
    margin-bottom: 6px;
  }

  /* The segmented control (specs/_design/foundation.md « Components »). It wraps rather than leave
     the sheet on a very narrow window. */
  .segments {
    display: inline-flex;
    flex-wrap: wrap;
    max-width: 100%;
    overflow: hidden;
    border: 1px solid var(--nock-navy);
    border-radius: 6px;
  }

  /* The radio covers its option and draws nothing: the option shows the
     choice, and the radio's focus ring is drawn inside it. */
  .segment {
    position: relative;
    padding: 8px 10px;
    font: 600 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-navy);
    background: transparent;
    cursor: pointer;
  }

  .segment + .segment {
    border-left: 1px solid var(--nock-navy);
  }

  .segment.checked {
    color: var(--nock-white);
    background: var(--nock-navy);
  }

  .segment input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    appearance: none;
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .segment input:focus-visible {
    outline-offset: -4px;
  }

  .segment.checked input:focus-visible {
    outline-color: var(--nock-white);
  }

  /* Two fields side by side, 16 px apart, each label 6 px above its input. */
  .number-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 14px 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .number-input {
    box-sizing: border-box;
    width: 64px;
    padding: 10px 12px;
    border: 1px solid var(--nock-rule);
    border-radius: 6px;
    font: 400 1rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
    background: var(--nock-white);
    text-align: center;
  }

  .number-input[aria-invalid='true'] {
    border-color: var(--nock-red);
  }

  .settings-save {
    align-self: flex-end;
  }
</style>
