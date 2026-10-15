<script lang="ts">
  import { tick } from 'svelte'
  import { t } from './i18n'
  import { REACTION_VALUES } from './roomSession'
  import type { ReactionValue } from './roomSession'

  // The reaction picker of spec 022. It is on the page only while it is open:
  // the room page decides when, and this component handles what happens inside.
  let {
    isPaced,
    isButtonDisabled,
    onPick,
    onClose,
    onDismiss,
    onFocusButton,
    onFocusGrid,
  }: {
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

  $effect(() => {
    if (picker === null) {
      return
    }
    const element = picker
    const onKeyDown = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    element.addEventListener('keydown', onKeyDown)
    return () => element.removeEventListener('keydown', onKeyDown)
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
  /* Drawn over the page below the header, like the vote banner: absolutely
     placed, so it moves nothing. The vote banner comes later in the document
     with the same z-index, so it is drawn over the picker and its buttons
     always stay uncovered. One row of five options at the left: 2.25rem and its
     border high. */
  .reaction-picker {
    position: absolute;
    z-index: 1;
    box-sizing: border-box;
    top: var(--popover-top);
    left: 0.5rem;
    display: flex;
    gap: 0.25rem;
    padding: 0.25rem;
    background: #ffffff;
    border: 1px solid #5b6070;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgb(0 0 0 / 20%);
  }

  .reaction-picker .reaction-option {
    box-sizing: border-box;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    font-size: 1rem;
    line-height: 1;
  }
</style>
