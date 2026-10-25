<script lang="ts">
  // The brand of a top bar (client/shell.md rule 17): the Nock mark, 12 by 18
  // px, and the app's name, both navy. The room's computer top bar and the page
  // top bar of the plain pages start with it. On `/`, the catalogue, it is plain
  // text read « Nock »: no link, no Tab stop and no hover look. Everywhere else
  // it is a link to `/` named « Accueil »; following it loads the catalogue as
  // any link does. Its look is « Brand link » (_design/foundation.md,
  // « Components »): plain text at rest, a word-blue background on hover for
  // the link only. Both forms have the same box, so the bar does not move.
  import { t } from './i18n'
  import { NOCK_MARK_POINTS } from './icons'

  const isHome = location.pathname === '/'
</script>

{#snippet content()}
  <svg viewBox="0 0 10 14" aria-hidden="true"><polygon points={NOCK_MARK_POINTS} /></svg
  >{t('app.title')}
{/snippet}

{#if isHome}
  <span class="topbar-brand" data-testid="topbar-brand">{@render content()}</span>
{:else}
  <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
  <a
    class="topbar-brand"
    data-testid="topbar-brand"
    href="/"
    tabindex="0"
    aria-label={t('topbar.home')}>{@render content()}</a
  >
{/if}

<style>
  /* The padding sits inside a negative margin of the same size, so the box is
     larger than its content and nothing moves. */
  .topbar-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    margin: -8px -10px;
    border-radius: 6px;
    font: 700 1.3rem/1 var(--nock-font-ui);
    letter-spacing: 0.01em;
    color: var(--nock-navy);
    text-decoration: none;
  }

  /* Only the link has a hover look; the plain brand of `/` has none. */
  a.topbar-brand:hover {
    background: var(--nock-word);
  }

  .topbar-brand svg {
    width: 12px;
    height: 18px;
    fill: var(--nock-navy);
  }
</style>
