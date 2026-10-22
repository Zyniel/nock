<script lang="ts">
  // The navy clue bar (spec 043, "Clue bar"): ‹, the clue of the selected word
  // with its direction, « Réagir », « Je bloque » and ›. The room page decides
  // what each button does and when it is enabled.
  import type { Snippet } from 'svelte'
  import Icon from './Icon.svelte'
  import { t } from './i18n'
  import type { Word } from './wordSelection'
  import { wordKey } from './wordSelection'

  let {
    activeWord,
    width,
    isPickerOpen,
    isReactDisabled,
    isFlagPressed,
    isFlagDisabled,
    reactButton = $bindable(null),
    onPrevious,
    onNext,
    onToggleReactions,
    onFlag,
    status,
  }: {
    activeWord: Word | null
    // The bar's width in px in the column layout; null: as wide as its parent.
    width: number | null
    isPickerOpen: boolean
    isReactDisabled: boolean
    isFlagPressed: boolean
    isFlagDisabled: boolean
    reactButton?: HTMLButtonElement | null
    onPrevious: () => void
    onNext: () => void
    onToggleReactions: () => void
    onFlag: () => void
    // The completion status, when it sits in the bar's row (spec 026).
    status?: Snippet
  } = $props()

  // A pointer press on a chevron does not take the focus, so typing goes on in
  // the grid; a keyboard activation leaves the focus on the button.
  function keepFocus(event: MouseEvent): void {
    event.preventDefault()
  }
</script>

<div
  class="clue-bar nock-on-navy"
  data-testid="clue-bar"
  data-word={activeWord === null ? '' : wordKey(activeWord)}
  role="region"
  aria-label={t('clue_bar.label')}
  style:width={width === null ? null : `${width}px`}
>
  <button
    type="button"
    class="clue-bar-button chevron"
    data-testid="clue-prev"
    aria-label={t('clue_bar.previous')}
    onmousedown={keepFocus}
    onclick={onPrevious}><Icon name="chevron-left" /></button
  >
  <span class="clue-bar-text" data-testid="clue-bar-text"
    >{activeWord === null ? t('clue_bar.empty') : activeWord.text}{#if activeWord !== null}<span
        class="clue-bar-direction"
        data-testid="clue-bar-direction"
        data-direction={activeWord.direction}
        aria-hidden="true"
      ></span>{/if}</span
  >
  {@render status?.()}
  <button
    type="button"
    class="clue-bar-button pill react-button"
    class:light={isPickerOpen}
    data-testid="react-button"
    aria-label={t('reaction.button_label')}
    aria-expanded={isPickerOpen}
    aria-controls="reaction-picker"
    disabled={isReactDisabled}
    bind:this={reactButton}
    onclick={onToggleReactions}><Icon name="smile" /></button
  >
  <button
    type="button"
    class="clue-bar-button pill flag-button"
    class:light={isFlagPressed}
    data-testid="flag-button"
    aria-label={t('flag.button_label')}
    aria-pressed={isFlagPressed}
    disabled={isFlagDisabled}
    onclick={onFlag}><Icon name="flag" /></button
  >
  <button
    type="button"
    class="clue-bar-button chevron"
    data-testid="clue-next"
    aria-label={t('clue_bar.next')}
    onmousedown={keepFocus}
    onclick={onNext}><Icon name="chevron-right" /></button
  >
</div>

<style>
  .clue-bar {
    flex: none;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    height: 34px;
    max-width: 100%;
  }

  .clue-bar-button {
    flex: none;
    box-sizing: border-box;
    display: grid;
    place-items: center;
    height: 100%;
    margin: 0;
    padding: 0;
    border: 0;
    color: var(--nock-white);
    background: transparent;
    cursor: pointer;
  }

  .clue-bar-button :global(.icon) {
    width: 20px;
    height: 20px;
    stroke-width: 2;
  }

  .chevron {
    width: 36px;
  }

  .pill {
    width: 40px;
    border-radius: 6px;
  }

  /* Pressed « Je bloque », and « Réagir » while the picker is open: a white
     button with a navy icon; the flag is filled. Its focus ring is navy, so it
     is never white on white. */
  .light {
    color: var(--nock-navy);
    background: var(--nock-white);
  }

  .flag-button.light :global(.icon) {
    fill: currentColor;
  }

  .clue-bar-button.light:focus-visible {
    outline-color: var(--nock-navy);
  }

  /* A disabled button keeps 5.22:1 on navy (Open question 10). */
  .clue-bar-button:disabled {
    color: var(--nock-rule);
    background: transparent;
    cursor: not-allowed;
  }

  /* One centred line that ends with an ellipsis when too long (specs 007, 043). */
  .clue-bar-text {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    text-align: center;
    font: 500 0.95rem/1.2 var(--nock-font-ui);
    color: var(--nock-white);
  }

  /* The direction of the selected word, → or ↓: a pictogram drawn by CSS. */
  .clue-bar-direction {
    margin-left: 6px;
    opacity: 0.8;
  }

  .clue-bar-direction[data-direction='across']::after {
    content: '→';
  }

  .clue-bar-direction[data-direction='down']::after {
    content: '↓';
  }
</style>
