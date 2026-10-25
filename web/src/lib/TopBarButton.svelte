<script lang="ts">
  // A button of a top bar (spec 043, specs/_design/foundation.md « Components »): its icon, if any,
  // and its label, navy on a transparent background, word blue while pressed or
  // while what it opens is open. The top bar decides its size and whether the
  // icon sits above or beside the label. The page top bar's "Compte" (spec
  // 046) is one with no icon.
  import type { Snippet } from 'svelte'
  import Icon from './Icon.svelte'
  import type { IconName } from './icons'

  let {
    testId,
    icon = null,
    label,
    ariaLabel = null,
    ariaExpanded = null,
    ariaControls = null,
    ariaHaspopup = null,
    ariaPressed = null,
    disabled = false,
    element = $bindable(null),
    onclick,
    children,
  }: {
    testId: string
    // The icon before the label, or null for a button with a label only.
    icon?: IconName | null
    label: string
    // The accessible name when it is not the label.
    ariaLabel?: string | null
    // For a button that opens a popover, a dialog or the Salon.
    ariaExpanded?: boolean | null
    ariaControls?: string | null
    ariaHaspopup?: 'dialog' | null
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
  aria-haspopup={ariaHaspopup}
  aria-pressed={ariaPressed}
  {disabled}
  bind:this={element}
  {onclick}
  >{#if icon !== null}<Icon name={icon} />{/if}<span class="topbar-label">{label}</span
  >{@render children?.()}</button
>

<style>
  .topbar-button {
    position: relative;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    border: 0;
    border-radius: 6px;
    color: var(--nock-navy);
    background: transparent;
    cursor: pointer;
  }

  .topbar-button.pressed {
    background: var(--nock-word);
  }

  .topbar-button:disabled {
    color: var(--nock-muted);
    background: transparent;
    cursor: not-allowed;
  }

  .topbar-label {
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
  }

  .topbar-button :global(.icon) {
    stroke-width: 1.8;
  }
</style>
