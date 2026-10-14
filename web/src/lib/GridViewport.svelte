<script lang="ts">
  import { flushSync } from 'svelte'
  import { t } from './i18n'
  import {
    ZOOM_MAX,
    ZOOM_MIN,
    arrowPosition,
    arrowSide,
    clampZoom,
    distanceBetween,
    fitCellSize,
  } from './gridLayout'
  import { actionForKey } from './letterEntry'
  import { isArrowKey, selectionAfterArrow, selectionAfterTab } from './navigation'
  import { shownCell, shownGrid } from './roomSession'
  import type { CellFlash, GridView, PendingEdit } from './roomSession'
  import { positionKey, wordKey } from './wordSelection'
  import type { Position, Selection, Word } from './wordSelection'
  import type { RemoteSelection } from './remoteSelections'

  interface Finger {
    clientX: number
    clientY: number
  }

  let {
    grid,
    words,
    selection,
    activeWord,
    onCellTap,
    onClueTap,
    onSelect,
    onLetter,
    onErase,
    onUndo,
    pendingEdits,
    flashes,
    remoteSelections,
  }: {
    grid: GridView
    words: Word[]
    selection: Selection | null
    activeWord: Word | null
    onCellTap: (row: number, column: number) => void
    onClueTap: (word: Word) => void
    onSelect: (next: Selection) => void
    onLetter: (letter: string) => void
    onErase: () => void
    // Control+z or Meta+z; absent: those keys are left to the browser.
    onUndo?: () => void
    pendingEdits: PendingEdit[]
    flashes: CellFlash[]
    // The other players' selections, in roster order (spec 013).
    remoteSelections: RemoteSelection[]
  } = $props()

  // The step between two outlines on one cell, and the most the stack may take
  // of each side of the cell, so that the innermost outline stays visible.
  const OUTLINE_STEP_PX = 3
  const OUTLINE_STACK_MAX_SHARE = 0.4
  const OUTLINE_BORDER_PX = 2
  const MAX_OUTLINES = 7

  // The inset of the outline at `rank`: 3 px per rank, scaled down on a small
  // cell so that the last of the 7 other players still has room for its border.
  function outlineInset(rank: number): number {
    const room = cellSize * OUTLINE_STACK_MAX_SHARE - OUTLINE_BORDER_PX
    const step = Math.min(OUTLINE_STEP_PX, room / (MAX_OUTLINES - 1))
    return rank * Math.max(step, 1)
  }

  // The corners where a cell can hold a label, in the order they are filled.
  const LABEL_CORNERS = ['top-left', 'bottom-right', 'top-right', 'bottom-left']
  const FOUR_SLOTS_MIN_CELL_PX = 44
  const TWO_SLOTS_MIN_CELL_PX = 20

  interface LabelPlan {
    // The number of corners the cell has (1, 2 or 4).
    slots: number
    // The first cursors, in roster order, that show their initials.
    initialsCount: number
    // The number of cursors folded into the "+k" label (0 for no label).
    overflowCount: number
  }

  function slotsFor(side: number): number {
    if (side >= FOUR_SLOTS_MIN_CELL_PX) {
      return 4
    }
    if (side >= TWO_SLOTS_MIN_CELL_PX) {
      return 2
    }
    return 1
  }

  // Who gets initials and who is folded into "+k" on a cell (spec 035 AC-11).
  function labelPlanOf(cursorCount: number, side: number): LabelPlan {
    const slots = slotsFor(side)
    if (cursorCount <= slots) {
      return { slots, initialsCount: cursorCount, overflowCount: 0 }
    }
    return { slots, initialsCount: slots - 1, overflowCount: cursorCount - slots + 1 }
  }

  // The DOM id of a cell, used by aria-activedescendant.
  function cellId(row: number, column: number): string {
    return `cell-${row}-${column}`
  }

  // The remote selections that sit on a cell, in roster order.
  function outlinesOn(row: number, column: number): RemoteSelection[] {
    return remoteSelections.filter((remote) => remote.row === row && remote.column === column)
  }

  // The remote selections whose word holds a cell, in roster order.
  function tintsOn(row: number, column: number): RemoteSelection[] {
    const key = positionKey(row, column)
    return remoteSelections.filter((remote) => remote.wordPositions.has(key))
  }

  // The colour index of the flash on a cell, or '' when it does not flash.
  function flashOf(row: number, column: number): string {
    for (const flash of flashes) {
      if (flash.row === row && flash.column === column) {
        return String(flash.colour)
      }
    }
    return ''
  }

  let gridElement: HTMLDivElement | undefined = $state()

  // The cells of each row, in column order: the grid is drawn row by row.
  let rows = $derived(rowsOf(grid))

  function rowsOf(view: GridView): GridView['cells'][number][][] {
    const result: GridView['cells'][number][][] = []
    for (let row = 0; row < view.height; row += 1) {
      result.push([])
    }
    for (const cell of view.cells) {
      result[cell.row].push(cell)
    }
    for (const rowCells of result) {
      rowCells.sort((first, second) => first.column - second.column)
    }
    return result
  }

  // What a screen reader says when the selection moves (spec 035).
  let announcement = $derived(announcementOf(selection, activeWord))

  function announcementOf(current: Selection | null, word: Word | null): string {
    if (current === null || word === null) {
      return ''
    }
    const direction = t(
      word.direction === 'across' ? 'a11y.direction.across' : 'a11y.direction.down',
    )
    if (word.cells.length === 1) {
      return t('a11y.announcement_one', { clue: word.text, direction })
    }
    const index = word.cells.findIndex(
      (cell: Position) => cell.row === current.row && cell.column === current.column,
    )
    if (index === -1) {
      return ''
    }
    return t('a11y.announcement', {
      clue: word.text,
      direction,
      length: word.cells.length,
      position: index + 1,
    })
  }

  // After Escape, the next Tab or Shift+Tab leaves the grid (spec 035).
  let isReleased = false
  let activeKey = $derived(activeWord === null ? '' : wordKey(activeWord))
  let wordPositions = $derived(
    new Set((activeWord?.cells ?? []).map((cell) => positionKey(cell.row, cell.column))),
  )

  function isSelected(row: number, column: number): boolean {
    return selection !== null && selection.row === row && selection.column === column
  }

  // One handler for the whole grid: find the cell or the clue that was tapped.
  function onGridClick(event: MouseEvent): void {
    if (!(event.target instanceof Element)) {
      return
    }
    const clueElement = event.target.closest('[data-testid="clue"]')
    const cellElement = event.target.closest('[data-testid="cell"]')
    if (cellElement === null) {
      return
    }
    const row = Number(cellElement.getAttribute('data-row'))
    const column = Number(cellElement.getAttribute('data-column'))
    if (clueElement !== null) {
      const clueIndex = Number(clueElement.getAttribute('data-clue-index'))
      const key = `${row},${column},${clueIndex}`
      const word = words.find((candidate) => wordKey(candidate) === key)
      if (word !== undefined) {
        onClueTap(word)
        gridElement?.focus()
      }
    } else if (cellElement.getAttribute('data-type') === 'letter') {
      onCellTap(row, column)
      gridElement?.focus()
    }
  }

  let viewport: HTMLDivElement | undefined = $state()
  let areaWidth = $state(0)
  let areaHeight = $state(0)
  let zoom = $state(ZOOM_MIN)

  let fitSize = $derived(fitCellSize(areaWidth, areaHeight, grid.width, grid.height))
  let cellSize = $derived(fitSize * zoom)

  // Follow the size of the viewport (the area the grid must fit in at zoom 1).
  $effect(() => {
    const element = viewport
    if (element === undefined) {
      return
    }
    function measure(): void {
      if (element !== undefined) {
        areaWidth = element.clientWidth
        areaHeight = element.clientHeight
      }
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  })

  // Put the focus back on the grid (the in-app keyboard uses it).
  export function focusGrid(): void {
    gridElement?.focus({ preventScroll: true })
  }

  // Arrow keys move the selection to the next letter cell (spec 009).
  function onArrowKey(key: string): void {
    if (selection === null || !isArrowKey(key)) {
      return
    }
    const next = selectionAfterArrow(grid, words, selection, key)
    if (next !== null) {
      onSelect(next)
    }
  }

  // Tab and Shift+Tab select the next or previous unfinished word (spec 009).
  function onTabKey(shiftKey: boolean): void {
    const next = selectionAfterTab(shownGrid(grid, pendingEdits), words, selection, shiftKey ? -1 : 1)
    if (next !== null) {
      onSelect(next)
    }
  }

  function isModifierKey(key: string): boolean {
    return key === 'Shift' || key === 'Control' || key === 'Alt' || key === 'Meta'
  }

  function onGridFocusChange(): void {
    isReleased = false
  }

  // Navigation keys (spec 009), then letter keys and Backspace (spec 008).
  function onGridKeydown(event: KeyboardEvent): void {
    if (isModifierKey(event.key)) {
      return
    }
    const wasReleased = isReleased
    isReleased = false
    const hasAnyModifier = event.ctrlKey || event.metaKey || event.altKey || event.shiftKey
    if (event.key === 'Escape' && !hasAnyModifier) {
      isReleased = true
      return
    }
    const isPlainTab = event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey
    if (isPlainTab && wasReleased) {
      return
    }
    const isUndo =
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      event.key.toLowerCase() === 'z'
    if (isUndo && onUndo !== undefined) {
      event.preventDefault()
      onUndo()
      return
    }
    const hasModifier = event.ctrlKey || event.metaKey || event.altKey
    const isTab = !hasModifier && event.key === 'Tab'
    if (isTab) {
      event.preventDefault()
      onTabKey(event.shiftKey)
      return
    }
    if (!hasModifier && isArrowKey(event.key) && selection !== null) {
      event.preventDefault()
      onArrowKey(event.key)
      return
    }
    const action = actionForKey(
      event.key,
      event.ctrlKey,
      event.metaKey,
      event.altKey,
      event.isComposing,
    )
    if (action.kind === 'ignore') {
      return
    }
    if (selection === null) {
      // Backspace never leaves the page, even with nothing selected.
      if (action.kind === 'erase') {
        event.preventDefault()
      }
      return
    }
    event.preventDefault()
    if (action.kind === 'letter') {
      onLetter(action.letter)
    } else {
      onErase()
    }
  }

  // Taps and clicks on the grid select a word; keys on the focused grid type.
  $effect(() => {
    const element = gridElement
    if (element === undefined) {
      return
    }
    element.addEventListener('click', onGridClick)
    element.addEventListener('keydown', onGridKeydown)
    element.addEventListener('focus', onGridFocusChange)
    element.addEventListener('blur', onGridFocusChange)
    return () => {
      element.removeEventListener('focus', onGridFocusChange)
      element.removeEventListener('blur', onGridFocusChange)
      element.removeEventListener('click', onGridClick)
      element.removeEventListener('keydown', onGridKeydown)
    }
  })

  // Touch gestures, handled here: one finger pans, two fingers pinch (the zoom
  // follows the ratio of the finger distances).
  $effect(() => {
    const element = viewport
    if (element === undefined) {
      return
    }
    const target: HTMLDivElement = element
    // The fingers now on the screen, with their last known position.
    const fingers = new Map<number, Finger>()
    let startDistance = 0
    let startZoom = ZOOM_MIN

    function onPointerDown(event: PointerEvent): void {
      if (event.pointerType === 'mouse') {
        return
      }
      fingers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY })
      if (fingers.size === 2) {
        const [first, second] = [...fingers.values()]
        startDistance = distanceBetween(first, second)
        startZoom = zoom
      }
    }

    function onPointerMove(event: PointerEvent): void {
      const finger = fingers.get(event.pointerId)
      if (finger === undefined) {
        return
      }
      if (fingers.size === 1) {
        target.scrollLeft -= event.clientX - finger.clientX
        target.scrollTop -= event.clientY - finger.clientY
      }
      finger.clientX = event.clientX
      finger.clientY = event.clientY
      if (fingers.size === 2 && startDistance > 0) {
        const [first, second] = [...fingers.values()]
        const ratio = distanceBetween(first, second) / startDistance
        const centerX = (first.clientX + second.clientX) / 2
        const centerY = (first.clientY + second.clientY) / 2
        zoomAround(clampZoom(startZoom * ratio), centerX, centerY)
      }
    }

    function onPointerEnd(event: PointerEvent): void {
      fingers.delete(event.pointerId)
      if (fingers.size < 2) {
        startDistance = 0
      }
    }

    // Change the zoom and scroll so the point between the fingers stays put.
    function zoomAround(newZoom: number, centerX: number, centerY: number): void {
      if (newZoom === zoom || cellSize === 0) {
        return
      }
      const box = target.getBoundingClientRect()
      const offsetX = centerX - box.left
      const offsetY = centerY - box.top
      const gridX = (target.scrollLeft + offsetX) / cellSize
      const gridY = (target.scrollTop + offsetY) / cellSize
      zoom = newZoom
      flushSync()
      target.scrollLeft = gridX * cellSize - offsetX
      target.scrollTop = gridY * cellSize - offsetY
    }

    target.addEventListener('pointerdown', onPointerDown)
    target.addEventListener('pointermove', onPointerMove)
    target.addEventListener('pointerup', onPointerEnd)
    target.addEventListener('pointercancel', onPointerEnd)
    return () => {
      target.removeEventListener('pointerdown', onPointerDown)
      target.removeEventListener('pointermove', onPointerMove)
      target.removeEventListener('pointerup', onPointerEnd)
      target.removeEventListener('pointercancel', onPointerEnd)
    }
  })
</script>

<div
  class="viewport"
  data-testid="grid-viewport"
  data-zoom={String(zoom)}
  data-zoom-min={String(ZOOM_MIN)}
  data-zoom-max={String(ZOOM_MAX)}
  bind:this={viewport}
>
  <div
    class="grid"
    data-testid="grid"
    data-width={String(grid.width)}
    data-height={String(grid.height)}
    aria-label={t('grid.label')}
    role="grid"
    tabindex="0"
    aria-describedby="grid-hint"
    aria-activedescendant={selection === null
      ? undefined
      : cellId(selection.row, selection.column)}
    bind:this={gridElement}
    data-selected-row={selection === null ? '' : String(selection.row)}
    data-selected-column={selection === null ? '' : String(selection.column)}
    data-direction={selection === null ? '' : selection.direction}
    data-word={activeKey}
    style:--cell="{cellSize}px"
    style:grid-template-columns="repeat({grid.width}, var(--cell))"
    style:grid-auto-rows="var(--cell)"
  >
    {#each rows as rowCells, rowIndex (rowIndex)}
      <div class="row" data-testid="grid-row" role="row" data-row={rowIndex}>
        {#each rowCells as cell (cell.column)}
          {#if cell.type === 'letter'}
            {@const shown = shownCell(cell, pendingEdits)}
            {@const outlines = outlinesOn(cell.row, cell.column)}
            {@const plan = labelPlanOf(outlines.length, cellSize)}
            {@const tints = tintsOn(cell.row, cell.column)}
            {@const isInWord = wordPositions.has(positionKey(cell.row, cell.column))}
            <div
              class="cell letter"
              class:locked={cell.locked}
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="letter"
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              aria-selected={isSelected(cell.row, cell.column)}
              data-letter={shown.letter ?? ''}
              data-unconfirmed={String(shown.unconfirmed)}
              data-author={cell.author ?? ''}
              data-locked={String(cell.locked)}
              data-wrong={String(cell.wrong && !shown.unconfirmed)}
              data-flash={flashOf(cell.row, cell.column)}
              data-selected={String(isSelected(cell.row, cell.column))}
              data-in-word={String(isInWord)}
              data-tinted-by={tints.map((remote) => remote.playerId).join(' ')}
              class:selected={isSelected(cell.row, cell.column)}
              class:in-word={isInWord}
              class:tinted={tints.length > 0 && !isInWord}
              style:--tint={tints.length > 0 ? `var(--player-colour-${tints[0].colour})` : null}
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            >{shown.letter ?? ''}{#each outlines as remote, rank (remote.playerId)}<span
                  class="remote-selection"
                  data-testid="remote-selection"
                  data-player-id={remote.playerId}
                  data-colour={String(remote.colour)}
                  style:--outline-colour={`var(--player-colour-${remote.colour})`}
                  style:inset="{outlineInset(rank)}px"
                  style:--shift="{outlineInset(rank) + OUTLINE_BORDER_PX}px"
                  >{#if rank < plan.initialsCount}<span
                      class="remote-label remote-initials"
                      data-corner={LABEL_CORNERS[rank]}
                      data-testid="remote-initials">{remote.initials}</span
                    >{/if}</span
                >{/each}{#if plan.overflowCount > 0}<span
                  class="remote-label remote-overflow"
                  data-corner={LABEL_CORNERS[plan.slots - 1]}
                  data-count={plan.overflowCount}
                  data-testid="remote-overflow"
                  aria-hidden="true"
                  >{t('grid.remote_overflow', { count: plan.overflowCount })}</span
                ><span class="visually-hidden" data-testid="remote-overflow-label"
                  >{t('a11y.remote_overflow', { count: plan.overflowCount })}</span
                >{/if}</div>
          {:else if cell.type === 'clue'}
            <div
              class="cell clue-cell"
              class:two={cell.clues.length === 2}
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="clue"
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            >
              {#each cell.clues as clue, index (index)}
                {#if index === 1}
                  <div class="separator" data-testid="clue-separator"></div>
                {/if}
                <div
                  class="clue"
                  data-testid="clue"
                  data-clue-index={index}
                  data-arrow={clue.arrow}
                  data-active={String(activeKey === `${cell.row},${cell.column},${index}`)}
                  class:active={activeKey === `${cell.row},${cell.column},${index}`}
                >
                  <span class="clue-text" data-testid="clue-text">{clue.text}</span>
                  <span
                    class="arrow {arrowSide(clue.arrow)}"
                    data-testid="clue-arrow"
                    data-arrow={clue.arrow}
                    data-side={arrowSide(clue.arrow)}
                    aria-hidden="true"
                    style:--along={arrowPosition(cell.clues, index)}
                  ></span>
                </div>
              {/each}
            </div>
          {:else}
            <div
              class="cell empty"
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="empty"
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            ></div>
          {/if}
        {/each}
      </div>
    {/each}
  </div>
</div>
<div
  class="visually-hidden"
  data-testid="grid-announcement"
  role="status"
  aria-live="polite"
  aria-atomic="true"
>{announcement}</div>
<div class="visually-hidden" id="grid-hint" data-testid="grid-hint">{t('a11y.grid_hint')}</div>

<style>
  .viewport {
    width: 100%;
    flex: 1 1 0;
    min-height: 0;
    overflow: auto;
    /* The app handles touch pan and pinch itself. */
    touch-action: none;
    scrollbar-width: none;
  }

  .viewport::-webkit-scrollbar {
    display: none;
  }

  .grid {
    display: grid;
    width: max-content;
    margin: 0 auto;
  }

  /* The rows only group the cells: the cells stay items of the CSS grid. */
  .row {
    display: contents;
  }

  .cell {
    box-sizing: border-box;
    min-width: 0;
    min-height: 0;
    border: 1px solid #8a8fa0;
    background: #ffffff;
  }

  .letter {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: calc(var(--cell) * 0.55);
    line-height: 1;
    text-transform: uppercase;
  }

  /* A letter found wrong by a check: the line is on the cell itself. */
  .letter[data-wrong='true'] {
    text-decoration-line: line-through;
  }

  .letter.locked {
    background: #dfe3ee;
    font-weight: 700;
  }

  .letter.in-word {
    background: #cfe3ff;
  }

  .letter.selected {
    background: #ffd54a;
    outline: 3px solid #1f2330;
    outline-offset: -3px;
  }

  /* The word of another player: their colour at low opacity. My own word
     (in-word) and my cell (selected) keep their look. */
  .letter.tinted {
    background: color-mix(in srgb, var(--tint) 28%, #ffffff);
  }

  /* The cell another player selected: a dashed border in their colour, inset
     by rank so that several outlines on one cell all stay visible. */
  .remote-selection {
    position: absolute;
    box-sizing: border-box;
    border: 2px dashed var(--outline-colour);
    pointer-events: none;
  }

  /* The initials of a player or the "+k" label, in a small white label in a
     corner of the cell. An initials label sits inside the outline span, which
     is inset: --shift (the inset plus the border) takes it back to the corner
     of the cell. The "+k" label is a child of the cell, so --shift is 0.
     No padding above or below: a label is then 1.1 times its font high, and two
     labels in diagonal corners fit one above the other from a 20px cell, the
     size where a cell gets its second slot (spec 035 AC-11). */
  .remote-label {
    --corner-offset: calc(var(--shift, 0px) * -1);
    position: absolute;
    padding: 0 1px;
    font-size: max(7px, calc(var(--cell) * 0.2));
    font-weight: 700;
    line-height: 1.1;
    color: #1f2330;
    background: #ffffff;
  }

  .remote-label[data-corner='top-left'] {
    top: var(--corner-offset);
    left: var(--corner-offset);
  }

  .remote-label[data-corner='bottom-right'] {
    bottom: var(--corner-offset);
    right: var(--corner-offset);
  }

  .remote-label[data-corner='top-right'] {
    top: var(--corner-offset);
    right: var(--corner-offset);
  }

  .remote-label[data-corner='bottom-left'] {
    bottom: var(--corner-offset);
    left: var(--corner-offset);
  }

  /* After the other states, so a flash shows over them. */
  .letter[data-flash='0'] {
    background: var(--player-colour-0);
    color: #000000;
  }

  .letter[data-flash='1'] {
    background: var(--player-colour-1);
  }

  .letter[data-flash='2'] {
    background: var(--player-colour-2);
    color: #ffffff;
  }

  .letter[data-flash='3'] {
    background: var(--player-colour-3);
  }

  .letter[data-flash='4'] {
    background: var(--player-colour-4);
    color: #ffffff;
  }

  .letter[data-flash='5'] {
    background: var(--player-colour-5);
    color: #ffffff;
  }

  .letter[data-flash='6'] {
    background: var(--player-colour-6);
    color: #ffffff;
  }

  .letter[data-flash='7'] {
    background: var(--player-colour-7);
    color: #000000;
  }

  .clue.active {
    background: #ffd54a;
  }

  /* The focus outline stays inside the scrolling viewport. */
  .grid:focus-visible {
    outline-offset: -3px;
  }

  .empty {
    background: #c9cdd8;
  }

  /* Room on the right and at the bottom for the arrows. */
  .clue-cell {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: calc(var(--cell) * 0.03) calc(var(--cell) * 0.12)
      calc(var(--cell) * 0.12) calc(var(--cell) * 0.03);
    background: #eef1fa;
  }

  .clue {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .clue-text {
    display: block;
    max-width: 100%;
    font-size: calc(var(--cell) * 0.11);
    line-height: 1.1;
    text-align: center;
    overflow-wrap: anywhere;
  }

  .two .clue-text {
    font-size: calc(var(--cell) * 0.09);
  }

  .separator {
    flex: none;
    height: 1px;
    background: #1f2330;
  }

  /* Arrows are small triangles against the cell's right or bottom edge. */
  .arrow {
    position: absolute;
    width: 0;
    height: 0;
    border: solid transparent;
  }

  .arrow.right {
    top: var(--along);
    right: calc(var(--cell) * 0.02);
    margin-top: calc(var(--cell) * -0.07);
    border-width: calc(var(--cell) * 0.07) 0 calc(var(--cell) * 0.07)
      calc(var(--cell) * 0.1);
    border-left-color: #1f2330;
  }

  .arrow.bottom {
    left: var(--along);
    bottom: calc(var(--cell) * 0.02);
    margin-left: calc(var(--cell) * -0.07);
    border-width: calc(var(--cell) * 0.1) calc(var(--cell) * 0.07) 0
      calc(var(--cell) * 0.07);
    border-top-color: #1f2330;
  }
</style>
