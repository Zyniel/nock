<script lang="ts">
  // The completion status (spec 026, spec 043, spec 044): its text, after the
  // ✓ pictogram once solved, and « Voir le bilan » in the band of a solved grid.
  // The room page shows it in one of two places, never both: in the clue bar's
  // row ('row') or as a band under the bar ('band'). Only the full-but-wrong
  // status sits in the row, since a solved page has no keyboard.
  import { t } from './i18n'

  let {
    status,
    text,
    placement,
    width,
    height = $bindable(0),
    onOpenRecap,
  }: {
    status: 'solved' | 'full_wrong' | null
    text: string | null
    placement: 'row' | 'band'
    // The band's width in px, as wide as the clue bar; null: no width set.
    width: number | null
    // The element's height, with its padding: the room page takes the band's
    // height from the play area's.
    height?: number
    // « Voir le bilan »: the room page opens the recap dialog.
    onOpenRecap: () => void
  } = $props()

  let recapOpenButton: HTMLButtonElement | null = $state(null)

  // The recap dialog closed: the focus goes back to the button that opens it.
  export function focusRecapButton(): void {
    recapOpenButton?.focus()
  }
</script>

<p
  class="grid-status"
  class:in-row={placement === 'row'}
  class:band={placement === 'band'}
  data-testid="grid-status"
  data-state={status}
  style:width={width === null ? null : `${width}px`}
  bind:offsetHeight={height}
>
  <span class="grid-status-text" data-testid="grid-status-text"
    >{#if status === 'solved'}<span class="status-check" aria-hidden="true"></span
      >{/if}{text}</span
  >
  {#if status === 'solved'}
    <button
      type="button"
      class="nock-button nock-button-primary recap-open"
      data-testid="recap-open"
      bind:this={recapOpenButton}
      onclick={onOpenRecap}>{t('recap.open')}</button
    >
  {/if}
</p>

<style>
  /* ---- The completion status (spec 026; specs/_design/overlays.md « End of grid ») ---- */

  .grid-status {
    margin: 0;
    font: 600 0.95rem/1.2 var(--nock-font-ui);
  }

  /* The end band under the clue bar, as wide as the bar. */
  .grid-status.band {
    flex: none;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 10px;
    max-width: 100%;
    padding: 8px 12px;
  }

  .grid-status.band[data-state='solved'] {
    color: var(--nock-green);
    background: var(--nock-green-bg);
  }

  .grid-status.band[data-state='full_wrong'] {
    color: var(--nock-navy);
    background: var(--nock-clue-bg);
  }

  /* In the clue bar's row: white text on one line, after the clue. */
  .grid-status.in-row {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 8px;
    white-space: nowrap;
    color: var(--nock-white);
  }

  /* The text of the band, after its pictogram: it wraps when the band is too
     narrow for it and "Voir le bilan" on one line (spec 047). */
  .grid-status.band .grid-status-text {
    flex: 0 1 auto;
    min-width: 0;
  }

  /* The check mark of a solved grid: a pictogram drawn by CSS, never read, a space
     before the text. */
  .status-check::before {
    content: '✓';
  }

  .status-check {
    margin-right: 0.25em;
  }

  /* "Voir le bilan" keeps its whole label on one line, on the band's
     right. */
  .recap-open {
    flex: none;
    margin-left: auto;
    padding: 7px 12px;
    font-size: 0.85rem;
    white-space: nowrap;
  }
</style>
