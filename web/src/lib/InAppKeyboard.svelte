<script lang="ts">
  // The in-app keyboard of a touch screen (spec 009, spec 044, _design.md
  // section 8): three AZERTY rows, with ✎ (pencil mode), ⇄ (the other
  // direction of the selected cell) and ⌫ (erase) in the last one. The room
  // page decides when it shows and what each key does.
  import Icon from './Icon.svelte'
  import { t } from './i18n'

  let {
    isPencilMode,
    onLetter,
    onErase,
    onTogglePencil,
    onSwap,
    onKeyUsed,
  }: {
    // Pencil mode: ✎ is pressed and the letter keys show it.
    isPencilMode: boolean
    onLetter: (letter: string) => void
    onErase: () => void
    onTogglePencil: () => void
    onSwap: () => void
    // After every key: the grid takes the focus back.
    onKeyUsed: () => void
  } = $props()

  const FIRST_ROW = ['A', 'Z', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']
  const SECOND_ROW = ['Q', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M']
  // The letters of the third row, between ✎ on the left and ⇄ ⌫ on the right.
  const THIRD_ROW = ['W', 'X', 'C', 'V', 'B', 'N']

  // A key never takes the focus: the grid keeps it, so nothing can open the
  // system keyboard.
  function keepFocus(event: Event): void {
    event.preventDefault()
  }

  // Do what a key does, then give the focus back to the grid.
  function useKey(action: () => void): void {
    action()
    onKeyUsed()
  }
</script>

{#snippet letterKey(letter: string)}
  <button
    type="button"
    class="key letter"
    class:pencil={isPencilMode}
    data-testid="key"
    data-key={letter}
    tabindex="-1"
    onmousedown={keepFocus}
    onclick={() => useKey(() => onLetter(letter))}>{letter}</button
  >
{/snippet}

<div class="keyboard" data-testid="keyboard" role="group" aria-label={t('keyboard.label')}>
  <div class="row" data-testid="keyboard-row">
    {#each FIRST_ROW as letter (letter)}
      {@render letterKey(letter)}
    {/each}
  </div>
  <div class="row" data-testid="keyboard-row">
    {#each SECOND_ROW as letter (letter)}
      {@render letterKey(letter)}
    {/each}
  </div>
  <div class="row" data-testid="keyboard-row">
    <button
      type="button"
      class="key wide"
      class:pressed={isPencilMode}
      data-testid="key-pencil"
      aria-label={t('pencil.toggle')}
      aria-pressed={isPencilMode}
      tabindex="-1"
      onmousedown={keepFocus}
      onclick={() => useKey(onTogglePencil)}><Icon name="crayon" /></button
    >
    {#each THIRD_ROW as letter (letter)}
      {@render letterKey(letter)}
    {/each}
    <button
      type="button"
      class="key"
      data-testid="key-swap"
      aria-label={t('keyboard.swap')}
      tabindex="-1"
      onmousedown={keepFocus}
      onclick={() => useKey(onSwap)}><Icon name="swap" /></button
    >
    <button
      type="button"
      class="key wide"
      data-testid="key-delete"
      aria-label={t('keyboard.delete')}
      tabindex="-1"
      onmousedown={keepFocus}
      onclick={() => useKey(onErase)}><Icon name="effacer" /></button
    >
  </div>
</div>

<style>
  /* Under the clue bar, at the bottom of the window. */
  .keyboard {
    flex: none;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 6px 3px 8px;
    background: var(--nock-keyboard-bg);
    -webkit-user-select: none;
    user-select: none;
  }

  .row {
    display: flex;
    justify-content: center;
    gap: 4px;
  }

  /* Every key: the letter keys and ⇄ share the row's width, up to 33 px. */
  .key {
    flex: 1 1 0;
    max-width: 33px;
    height: 44px;
    margin: 0;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font: 500 1.3rem/1 var(--nock-font-ui);
    color: var(--nock-ink);
    background: var(--nock-key);
    border: 0;
    border-radius: 5px;
    box-shadow: 0 1px 0 var(--nock-key-shadow);
    touch-action: manipulation;
  }

  /* ✎ and ⌫ are wider. */
  .key.wide {
    flex: 1.5 1 48px;
    max-width: 48px;
  }

  .key :global(.icon) {
    width: 22px;
    height: 22px;
    stroke-width: 1.8;
  }

  /* Pencil mode: ✎ is navy with a white icon, and every letter key shows its
     letter as a pencil letter. */
  .key.pressed {
    color: var(--nock-white);
    background: var(--nock-navy);
  }

  .key.pressed :global(.icon) {
    fill: var(--nock-pen-fill);
  }

  .key.letter.pencil {
    font-style: italic;
    color: var(--nock-pencil);
  }

  /* A key is never focused by a pointer (a tap keeps the focus on the grid), and
     it is out of the Tab order, so it has the focus only when a screen reader or
     a script gives it (spec 035 AC-10). In Firefox, a key that a script focused
     with focus() after a pointer interaction (a tap that put the focus on the
     grid) did not match :focus-visible, so the outline of app.css is drawn on
     :focus here. */
  .key:focus {
    outline: var(--focus-outline);
    outline-offset: 2px;
  }

  /* On a low window the keys are lower, so the grid keeps its room (spec 044,
     Decision 3). */
  @media (max-height: 500px) {
    .key {
      height: 28px;
    }
  }
</style>
