<script lang="ts">
  // The page not found (spec 040), in the entry frame (spec 046): one card,
  // its heading and "Voir les grilles", with no room code line.
  import EntryFrame from './EntryFrame.svelte'
  import { t } from './i18n'
</script>

<main class="nock-plain-page" data-testid="not-found-page">
  <EntryFrame>
    <div class="nock-card">
      <h1 class="nock-card-title">{t('not_found.heading')}</h1>
      <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
      <a class="nock-button nock-button-primary" data-testid="entry-home" href="/" tabindex="0"
        >{t('share.home')}</a
      >
    </div>
  </EntryFrame>
</main>
