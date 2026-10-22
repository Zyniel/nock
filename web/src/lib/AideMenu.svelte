<script lang="ts">
  // The content of the Aide menu (spec 043, "Aide menu"): the pencil confirm
  // while a pencil letter is selected, then « Vérifier » and « Révéler » while
  // the room has help, or one muted line when it would hold nothing. The room
  // page decides what is enabled and what each item does; an item's handler
  // closes the menu before it sends.
  import { t } from './i18n'

  let {
    isConfirmShown,
    isHelpShown,
    isCheckLetterDisabled,
    isCheckWordDisabled,
    isCheckGridDisabled,
    isRevealLetterDisabled,
    isRevealWordDisabled,
    lettersLeft,
    wordsLeft,
    onConfirmPencil,
    onCheckLetter,
    onCheckWord,
    onCheckGrid,
    onRevealLetter,
    onRevealWord,
  }: {
    // True while the selected cell shows a pencil letter it can confirm.
    isConfirmShown: boolean
    // True while the room's help mode is not `none` (spec 025).
    isHelpShown: boolean
    isCheckLetterDisabled: boolean
    isCheckWordDisabled: boolean
    isCheckGridDisabled: boolean
    isRevealLetterDisabled: boolean
    isRevealWordDisabled: boolean
    // What is left of the reveal budget (spec 024).
    lettersLeft: number
    wordsLeft: number
    onConfirmPencil: () => void
    onCheckLetter: () => void
    onCheckWord: () => void
    onCheckGrid: () => void
    onRevealLetter: () => void
    onRevealWord: () => void
  } = $props()

  // What is left of the letters: « n restantes », « 1 restante », or why the
  // item is disabled.
  function lettersLeftText(count: number): string {
    if (count === 0) {
      return t('reveal.letter_none')
    }
    if (count === 1) {
      return t('reveal.letters_left_one')
    }
    return t('reveal.letters_left', { count })
  }

  function wordsLeftText(count: number): string {
    if (count === 0) {
      return t('reveal.word_none')
    }
    if (count === 1) {
      return t('reveal.words_left_one')
    }
    return t('reveal.words_left', { count })
  }
</script>

{#if isConfirmShown}
  <button
    type="button"
    class="nock-menu-item confirm-pencil"
    data-testid="confirm-pencil"
    onclick={onConfirmPencil}
    ><span>{t('pencil.confirm')}</span><span
      class="nock-menu-detail pencil-detail"
      aria-hidden="true"
    ></span></button
  >
  <hr class="nock-menu-separator" />
{/if}
{#if isHelpShown}
  <div class="aide-group" data-testid="check-panel" role="group" aria-labelledby="check-heading">
    <div class="nock-menu-heading" id="check-heading" data-testid="check-heading"
      >{t('check.label')}</div
    >
    <button
      type="button"
      class="nock-menu-item"
      data-testid="check-letter"
      disabled={isCheckLetterDisabled}
      onclick={onCheckLetter}><span>{t('check.letter')}</span></button
    >
    <button
      type="button"
      class="nock-menu-item"
      data-testid="check-word"
      disabled={isCheckWordDisabled}
      onclick={onCheckWord}><span>{t('check.word')}</span></button
    >
    <button
      type="button"
      class="nock-menu-item"
      data-testid="check-grid"
      disabled={isCheckGridDisabled}
      onclick={onCheckGrid}><span>{t('check.grid')}</span></button
    >
  </div>
  <hr class="nock-menu-separator" />
  <div
    class="aide-group"
    data-testid="reveal-panel"
    role="group"
    aria-labelledby="reveal-heading"
  >
    <div class="nock-menu-heading" id="reveal-heading" data-testid="reveal-heading"
      >{t('reveal.label')}</div
    >
    <button
      type="button"
      class="nock-menu-item"
      data-testid="reveal-letter"
      disabled={isRevealLetterDisabled}
      onclick={onRevealLetter}
      ><span>{t('reveal.letter')}</span><span
        class="nock-menu-detail"
        data-testid="reveal-letter-detail">{lettersLeftText(lettersLeft)}</span
      ></button
    >
    <button
      type="button"
      class="nock-menu-item"
      data-testid="reveal-word"
      disabled={isRevealWordDisabled}
      onclick={onRevealWord}
      ><span>{t('reveal.word')}</span><span
        class="nock-menu-detail"
        data-testid="reveal-word-detail">{wordsLeftText(wordsLeft)}</span
      ></button
    >
  </div>
{:else if !isConfirmShown}
  <p class="aide-empty" data-testid="aide-empty">{t('aide.empty')}</p>
{/if}

<style>
  .confirm-pencil {
    font-weight: 600;
  }

  /* The ✎ of the pencil confirm: a pictogram drawn by CSS, never read. */
  .pencil-detail::after {
    content: '✎';
  }

  .aide-empty {
    margin: 6px 16px 2px;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-muted);
  }
</style>
