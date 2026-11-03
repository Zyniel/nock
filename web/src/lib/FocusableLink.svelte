<script lang="ts">
  // A link that Tab reaches in every browser (spec 035 AC-1): WebKit only
  // Tab-focuses links that have a tabindex, so the link always carries
  // `tabindex="0"`. The caller gives the link's attributes and its content;
  // `element` is the link itself, for a caller that moves the focus to it.
  //
  // The link is this component's element, so a caller's scoped style reaches
  // it only through `:global(...)`.
  import type { Snippet } from 'svelte'
  import type { HTMLAnchorAttributes } from 'svelte/elements'

  let {
    href,
    element = $bindable(null),
    children,
    ...attributes
  }: {
    href: string
    element?: HTMLAnchorElement | null
    children: Snippet
  } & Omit<HTMLAnchorAttributes, 'href' | 'tabindex' | 'children'> = $props()
</script>

<a {...attributes} {href} tabindex="0" bind:this={element}>{@render children()}</a>
