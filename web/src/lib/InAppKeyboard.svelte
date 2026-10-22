<script lang="ts">
  import { t } from './i18n'

  let {
    onLetter,
    onErase,
    onKeyUsed,
  }: {
    onLetter: (letter: string) => void
    onErase: () => void
    onKeyUsed: () => void
  } = $props()

  const ROWS: string[][] = [
    ['A', 'Z', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['Q', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L', 'M'],
    ['W', 'X', 'C', 'V', 'B', 'N'],
  ]

  // A key never takes the focus: the grid keeps it, so nothing can open the
  // system keyboard.
  function keepFocus(event: Event): void {
    event.preventDefault()
  }

  function typeLetter(letter: string): void {
    onLetter(letter)
    onKeyUsed()
  }

  function erase(): void {
    onErase()
    onKeyUsed()
  }
</script>

<div class="keyboard" data-testid="keyboard" role="group" aria-label={t('keyboard.label')}>
  {#each ROWS as letters, rowIndex (rowIndex)}
    <div class="row" data-testid="keyboard-row">
      {#each letters as letter (letter)}
        <button
          type="button"
          class="key"
          data-testid="key"
          data-key={letter}
          tabindex="-1"
          onmousedown={keepFocus}
          onclick={() => typeLetter(letter)}>{letter}</button
        >
      {/each}
      {#if rowIndex === ROWS.length - 1}
        <button
          type="button"
          class="key"
          data-testid="key-delete"
          aria-label={t('keyboard.delete')}
          tabindex="-1"
          onmousedown={keepFocus}
          onclick={erase}
        >
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path
              d="M9 5h11v14H9L3 12z M12 9l6 6 M18 9l-6 6"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
          </svg>
        </button>
      {/if}
    </div>
  {/each}
</div>

<style>
  /* Below the clue bar, at the bottom of the window. */
  .keyboard {
    flex: none;
    box-sizing: border-box;
    padding: 0.25rem;
    background: var(--nock-keyboard-bg);
    -webkit-user-select: none;
    user-select: none;
  }

  .row {
    display: flex;
    justify-content: center;
    gap: 0.25rem;
    margin-bottom: 0.25rem;
  }

  .key {
    flex: 1 1 0;
    max-width: 2.6rem;
    height: 2.4rem;
    padding: 0;
    font: inherit;
    font-size: 1.1rem;
    color: var(--nock-ink);
    background: var(--nock-key);
    border: 1px solid var(--nock-rule);
    border-radius: 0.3rem;
    display: flex;
    align-items: center;
    justify-content: center;
    touch-action: manipulation;
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

  @media (max-height: 500px) {
    .key {
      height: 1.8rem;
    }
  }
</style>
