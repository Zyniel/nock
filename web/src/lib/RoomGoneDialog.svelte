<script lang="ts">
  import { onMount } from 'svelte'
  import { t } from './i18n'

  // The room-gone dialog (client/hud.md rule 16): the room was deleted once it
  // had shown. A modal alert dialog with the recap's frame (app.css, room
  // sheet): centred in the column layout, a bottom sheet in the sheet layout,
  // over the dialog scrim that covers the whole window. Its one control is the
  // link to the catalogue; nothing else closes it, so the room under it stays
  // inert until the player follows the link.
  let {
    layout,
  }: {
    // The room's layout: a dialog in the column layout, a bottom sheet in the
    // sheet layout.
    layout: 'sheet' | 'column'
  } = $props()

  let dialog: HTMLDialogElement | null = $state(null)
  let homeLink: HTMLAnchorElement | null = $state(null)

  onMount(() => {
    dialog?.showModal()
    homeLink?.focus()
  })

  // Escape does not close the dialog: the browser's close request is refused.
  function refuseCancel(event: Event): void {
    event.preventDefault()
  }

  // Escape changes nothing, and Tab and Shift+Tab stay on the link, the one
  // control: the focus must not leave for the browser's own controls.
  function keepFocusOnLink(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault()
      return
    }
    if (event.key === 'Tab') {
      event.preventDefault()
      homeLink?.focus()
    }
  }

  // A press anywhere but on the link, the scrim included (it lands on the
  // dialog itself), leaves the focus on the link.
  function keepFocusOnPress(event: MouseEvent): void {
    const target = event.target
    if (target instanceof Node && homeLink?.contains(target)) {
      return
    }
    event.preventDefault()
  }
</script>

<dialog
  bind:this={dialog}
  class="room-sheet room-gone"
  class:bottom={layout === 'sheet'}
  data-testid="room-gone"
  role="alertdialog"
  aria-labelledby="room-gone-title"
  aria-describedby="room-gone-detail"
  oncancel={refuseCancel}
  onkeydown={keepFocusOnLink}
  onmousedown={keepFocusOnPress}
>
  <h2 class="room-sheet-title" id="room-gone-title">{t('room.gone.title')}</h2>
  <p class="nock-muted-line" id="room-gone-detail">{t('room.status.not_found_detail')}</p>
  <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
  <a
    class="nock-button nock-button-primary room-gone-home"
    data-testid="room-gone-home"
    href="/"
    tabindex="0"
    bind:this={homeLink}>{t('share.home')}</a
  >
</dialog>

<style>
  /* The recap's scrim: the darker dialog scrim, over the whole window, the top
     bar included. */
  dialog.room-gone::backdrop {
    top: 0;
    background: var(--nock-scrim-dialog);
  }

  /* « Voir les grilles », right-aligned. */
  .room-gone-home {
    align-self: flex-end;
  }
</style>
