<script lang="ts">
  import { onMount } from 'svelte'
  import { t } from './i18n'
  import RoomSheet from './RoomSheet.svelte'

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

  let sheet: RoomSheet | undefined = $state()
  let homeLink: HTMLAnchorElement | null = $state(null)

  onMount(() => {
    showOverRoom()
  })

  // Opens the dialog as a modal over the room, the focus on the link.
  function showOverRoom(): void {
    sheet?.open()
    homeLink?.focus()
  }

  // A close request the browser does not let the page refuse (a second Android
  // back gesture with no press in between) still closes the dialog: it opens
  // again at once, so the room never shows without it. A dialog no longer in
  // the page (the player left) stays closed.
  function reopenAfterClose(): void {
    showOverRoom()
  }
</script>

<!-- Escape and a press outside close nothing, and a press anywhere but on the
     link leaves the focus on it. Tab and Shift+Tab stay on the link, the one
     control. -->
<RoomSheet
  bind:this={sheet}
  {layout}
  title={t('room.gone.title')}
  titleId="room-gone-title"
  testId="room-gone"
  extraClass="over-all room-gone"
  role="alertdialog"
  describedBy="room-gone-detail"
  canCancel={false}
  closesOnBackdrop={false}
  keepsFocusOnPress={true}
  onClosed={reopenAfterClose}
>
  <p class="nock-muted-line" id="room-gone-detail">{t('room.status.not_found_detail')}</p>
  <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
  <a
    class="nock-button nock-button-primary room-gone-home"
    data-testid="room-gone-home"
    href="/"
    tabindex="0"
    bind:this={homeLink}>{t('share.home')}</a
  >
</RoomSheet>

<style>
  /* « Voir les grilles », right-aligned. */
  .room-gone-home {
    align-self: flex-end;
  }
</style>
