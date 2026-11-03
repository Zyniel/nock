<script lang="ts">
  // The page not found (spec 040), in the entry frame (spec 046): one card,
  // its heading and "Voir les grilles", with no room code line.
  import EntryFrame from './EntryFrame.svelte'
  import FocusableLink from './FocusableLink.svelte'
  import { t } from './i18n'
</script>

<div class="nock-plain-page" data-testid="not-found-page">
  <EntryFrame>
    <div class="nock-card">
      <h1 class="nock-card-title">{t('not_found.heading')}</h1>
      <FocusableLink class="nock-button nock-button-primary" data-testid="entry-home" href="/"
        >{t('share.home')}</FocusableLink
      >
    </div>
  </EntryFrame>
</div>
