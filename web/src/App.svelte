<script lang="ts">
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

<!-- A page whose code cannot be fetched shows the error line of a page that
     cannot load, instead of a blank page. -->
{#snippet loadError()}
  <main>
    <p class="nock-error-line" data-testid="page-load-error" role="alert">
      {t('account.error.generic')}
    </p>
  </main>
{/snippet}

<!-- Each page is fetched only on its route, so a page does not carry the code
     of the others (client/shell.md rule 20). -->
{#if path === '/'}
  {#await import('./lib/CataloguePage.svelte') then { default: CataloguePage }}
    <CataloguePage />
  {:catch}
    {@render loadError()}
  {/await}
{:else if roomMatch !== null}
  {#await import('./lib/RoomPage.svelte') then { default: RoomPage }}
    <RoomPage code={roomMatch[1]} />
  {:catch}
    {@render loadError()}
  {/await}
{:else if gridMatch !== null}
  {#await import('./lib/GridPage.svelte') then { default: GridPage }}
    <GridPage number={gridMatch[1]} />
  {:catch}
    {@render loadError()}
  {/await}
{:else if recapMatch !== null}
  {#await import('./lib/SharePage.svelte') then { default: SharePage }}
    <SharePage token={recapMatch[1]} />
  {:catch}
    {@render loadError()}
  {/await}
{:else if path === '/account'}
  <!-- The account page (spec 033); the server serves it only while accounts are on. -->
  {#await import('./lib/AccountPage.svelte') then { default: AccountPage }}
    <AccountPage />
  {:catch}
    {@render loadError()}
  {/await}
{:else if path === '/ops'}
  <!-- The operator's page (spec 038); the server serves it only while it is on. -->
  {#await import('./lib/OpsPage.svelte') then { default: OpsPage }}
    <OpsPage />
  {:catch}
    {@render loadError()}
  {/await}
{:else}
  {#await import('./lib/NotFoundPage.svelte') then { default: NotFoundPage }}
    <NotFoundPage />
  {:catch}
    {@render loadError()}
  {/await}
{/if}
