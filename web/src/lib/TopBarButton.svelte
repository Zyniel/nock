<script lang="ts">
  // A button of the room's top bar (spec 043, _design.md section 11): its icon
  // and its label, navy on a transparent background, word blue while pressed or
  // while what it opens is open. The top bar decides its size and whether the
  // icon sits above or beside the label.
  import type { Snippet } from 'svelte'
  import Icon from './Icon.svelte'
  import type { IconName } from './icons'

  let {
    testId,
    icon,
    label,
    ariaLabel = null,
    ariaExpanded = null,
    ariaControls = null,
    ariaPressed = null,
    disabled = false,
    element = $bindable(null),
    onclick,
    children,
  }: {
    testId: string
    icon: IconName
    label: string
    // The accessible name when it is not the label.
    ariaLabel?: string | null
    // For a button that opens a popover or the Salon.
    ariaExpanded?: boolean | null
    ariaControls?: string | null
    // For a button that switches a mode on and off.
    ariaPressed?: boolean | null
    disabled?: boolean
    element?: HTMLButtonElement | null
    onclick: () => void
    // What follows the label: the Aide caret, the unread badge.
    children?: Snippet
  } = $props()

  let isPressed = $derived(ariaExpanded === true || ariaPressed === true)
</script>

<button
  type="button"
  class="topbar-button"
  class:pressed={isPressed}
  data-testid={testId}
  aria-label={ariaLabel}
  aria-expanded={ariaExpanded}
  aria-controls={ariaControls}
  aria-pressed={ariaPressed}
  {disabled}
  bind:this={element}
  {onclick}
  ><Icon name={icon} /><span class="topbar-label">{label}</span>{@render children?.()}</button
>
