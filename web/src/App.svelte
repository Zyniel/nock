<script lang="ts">
  import AccountPage from './lib/AccountPage.svelte'
  import CataloguePage from './lib/CataloguePage.svelte'
  import GridPage from './lib/GridPage.svelte'
  import NotFoundPage from './lib/NotFoundPage.svelte'
  import OpsPage from './lib/OpsPage.svelte'
  import RoomPage from './lib/RoomPage.svelte'
  import SharePage from './lib/SharePage.svelte'
  import { t } from './lib/i18n'

  const ROOM_PATH = /^\/r\/([A-Z0-9]{6})$/
  const GRID_PATH = /^\/g\/([1-9][0-9]{0,8})$/
  // The public recap of spec 028: the token is the share token of a room.
  const RECAP_PATH = /^\/recap\/([A-Za-z0-9_-]{16,64})$/

  document.title = t('app.title')

  const path = location.pathname
  const roomMatch = ROOM_PATH.exec(path)
  const gridMatch = GRID_PATH.exec(path)
  const recapMatch = RECAP_PATH.exec(path)
</script>

{#if path === '/'}
  <CataloguePage />
{:else if roomMatch !== null}
  <RoomPage code={roomMatch[1]} />
{:else if gridMatch !== null}
  <GridPage number={gridMatch[1]} />
{:else if recapMatch !== null}
  <SharePage token={recapMatch[1]} />
{:else if path === '/account'}
  <!-- The account page (spec 033); the server serves it only while accounts are on. -->
  <AccountPage />
{:else if path === '/ops'}
  <!-- The operator's page (spec 038); the server serves it only while it is on. -->
  <OpsPage />
{:else}
  <NotFoundPage />
{/if}
