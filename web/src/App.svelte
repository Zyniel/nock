<script lang="ts">
  import CataloguePage from './lib/CataloguePage.svelte'
  import NotFoundPage from './lib/NotFoundPage.svelte'
  import RoomPage from './lib/RoomPage.svelte'
  import { t } from './lib/i18n'

  const ROOM_PATH = /^\/r\/([A-Z0-9]{6})$/

  document.title = t('app.title')

  const path = location.pathname
  const roomMatch = ROOM_PATH.exec(path)
</script>

{#if path === '/'}
  <CataloguePage />
{:else if roomMatch !== null}
  <RoomPage code={roomMatch[1]} />
{:else}
  <NotFoundPage />
{/if}
