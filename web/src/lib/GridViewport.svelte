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
  import type { GridView } from './roomSession'
  import { positionKey, wordKey } from './wordSelection'
  import type { Selection, Word } from './wordSelection'

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
  } = $props()

  let gridElement: HTMLDivElement | undefined = $state()
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
    const next = selectionAfterTab(grid, words, selection, shiftKey ? -1 : 1)
    if (next !== null) {
      onSelect(next)
    }
  }

  // Navigation keys (spec 009), then letter keys and Backspace (spec 008).
  function onGridKeydown(event: KeyboardEvent): void {
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
    return () => {
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
    bind:this={gridElement}
    data-selected-row={selection === null ? '' : String(selection.row)}
    data-selected-column={selection === null ? '' : String(selection.column)}
    data-direction={selection === null ? '' : selection.direction}
    data-word={activeKey}
    style:--cell="{cellSize}px"
    style:grid-template-columns="repeat({grid.width}, var(--cell))"
    style:grid-auto-rows="var(--cell)"
  >
    {#each grid.cells as cell (cell.row * grid.width + cell.column)}
      {#if cell.type === 'letter'}
        <div
          class="cell letter"
          class:locked={cell.locked}
          data-testid="cell"
          data-row={cell.row}
          data-column={cell.column}
          data-type="letter"
          data-letter={cell.letter ?? ''}
          data-locked={String(cell.locked)}
          data-selected={String(isSelected(cell.row, cell.column))}
          data-in-word={String(wordPositions.has(positionKey(cell.row, cell.column)))}
          class:selected={isSelected(cell.row, cell.column)}
          class:in-word={wordPositions.has(positionKey(cell.row, cell.column))}
          style:grid-row={cell.row + 1}
          style:grid-column={cell.column + 1}
        >{cell.letter ?? ''}</div>
      {:else if cell.type === 'clue'}
        <div
          class="cell clue-cell"
          class:two={cell.clues.length === 2}
          data-testid="cell"
          data-row={cell.row}
          data-column={cell.column}
          data-type="clue"
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
          style:grid-row={cell.row + 1}
          style:grid-column={cell.column + 1}
        ></div>
      {/if}
    {/each}
  </div>
</div>

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

  .cell {
    box-sizing: border-box;
    min-width: 0;
    min-height: 0;
    border: 1px solid #8a8fa0;
    background: #ffffff;
  }

  .letter {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: calc(var(--cell) * 0.55);
    line-height: 1;
    text-transform: uppercase;
  }

  .letter.locked {
    background: #dfe3ee;
  }

  .letter.in-word {
    background: #cfe3ff;
  }

  .letter.selected {
    background: #ffd54a;
  }

  .clue.active {
    background: #ffd54a;
  }

  .grid:focus {
    outline: none;
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
