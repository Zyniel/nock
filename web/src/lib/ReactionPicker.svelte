<script lang="ts">
  import { tick } from 'svelte'
  import { listenForEscape } from './escapeKey'
  import { t } from './i18n'
  import { REACTION_VALUES } from './roomSession'
  import type { ReactionValue } from './roomSession'

  // The reaction picker of spec 022. It is on the page only while it is open:
  // the room page decides when, and this component handles what happens inside.
  let {
    viewport,
    isPaced,
    isButtonDisabled,
    onPick,
    onClose,
    onDismiss,
    onFocusButton,
    onFocusGrid,
  }: {
    // The grid viewport: the picker floats over its bottom (spec 043).
    viewport: HTMLElement | null
    // True while the page holds back its own reactions: every option is disabled.
    isPaced: boolean
    // True when `react-button` is disabled (a mute, or no word selected).
    isButtonDisabled: boolean
    // The player chose a reaction.
    onPick: (reaction: ReactionValue) => void
    // Close the picker and put the focus on `react-button`.
    onClose: () => void
    // Close the picker and leave the focus where it is.
    onDismiss: () => void
    onFocusButton: () => void
    onFocusGrid: () => void
  } = $props()

  let picker: HTMLElement | null = $state(null)

  // The space between the picker's bottom and the viewport's (spec 043).
  const ABOVE_BOTTOM_PX = 8

  // The picker's place in the window: centred on the viewport, its bottom
  // ABOVE_BOTTOM_PX above the viewport's bottom.
  let centreX = $state(0)
  let bottom = $state(0)

  function place(): void {
    if (viewport === null) {
      return
    }
    const box = viewport.getBoundingClientRect()
    centreX = box.left + box.width / 2
    bottom = window.innerHeight - box.bottom + ABOVE_BOTTOM_PX
  }

  // Follow the viewport when the window or the play area changes size.
  $effect(() => {
    if (viewport === null) {
      return
    }
    place()
    const observer = new ResizeObserver(place)
    observer.observe(viewport)
    window.addEventListener('resize', place)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', place)
    }
  })

  // `tick` resolves once the picker is on the page. While the reactions are
  // paced, every option is disabled: the focus then stays on the button.
  async function focusFirstOption(): Promise<void> {
    await tick()
    const firstOption = picker?.querySelector('button')
    if (firstOption instanceof HTMLButtonElement && !firstOption.disabled) {
      firstOption.focus()
    } else {
      onFocusButton()
    }
  }

  void focusFirstOption()

  // Escape while the focus is inside the picker closes it.
  $effect(() => {
    if (picker === null) {
      return
    }
    return listenForEscape(picker, onClose)
  })

  // Runs before the page disables the button (a mute, or no word selected): the
  // picker closes at once and sends nothing. When the focus was inside it, the
  // focus goes to the grid instead of falling back to the page.
  $effect.pre(() => {
    if (!isButtonDisabled) {
      return
    }
    const focused = document.activeElement
    if (picker !== null && focused !== null && picker.contains(focused)) {
      onFocusGrid()
    }
    onDismiss()
  })

  function pick(reaction: ReactionValue): void {
    onPick(reaction)
    onClose()
  }
</script>

<div
  class="reaction-picker"
  id="reaction-picker"
  data-testid="reaction-picker"
  role="group"
  aria-label={t('reaction.picker_label')}
  style:left="{centreX}px"
  style:bottom="{bottom}px"
  bind:this={picker}
>
  {#each REACTION_VALUES as reaction (reaction)}
    <button
      type="button"
      class="reaction-option"
      data-testid="reaction-option"
      data-reaction={reaction}
      aria-label={t(`reaction.${reaction}_label`)}
      disabled={isPaced}
      onclick={() => pick(reaction)}>{t(`reaction.${reaction}`)}</button
    >
  {/each}
</div>

<style>
  /* Over the bottom of the grid, layer 9 (specs/_design/room.md « Layers »): drawn over the
     page, so it moves nothing. */
  .reaction-picker {
    position: fixed;
    z-index: 9;
    box-sizing: border-box;
    display: flex;
    gap: 2px;
    padding: 5px;
    transform: translateX(-50%);
    background: var(--nock-white);
    border: 1px solid var(--nock-line);
    border-radius: 24px;
    box-shadow: 0 10px 24px -10px var(--nock-shadow);
  }

  .reaction-picker .reaction-option {
    box-sizing: border-box;
    width: 40px;
    height: 40px;
    padding: 0;
    border: 0;
    border-radius: 20px;
    font-size: 22px;
    line-height: 1;
    background: transparent;
    cursor: pointer;
  }

  .reaction-picker .reaction-option:hover {
    background: var(--nock-word);
  }

  .reaction-picker .reaction-option:disabled {
    cursor: not-allowed;
  }
</style>
