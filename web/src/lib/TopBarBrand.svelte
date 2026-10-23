<script lang="ts">
  // The brand of a top bar (spec 043, spec 046): the Nock mark, 12 by 18 px,
  // and the app's name, both navy. The room's computer top bar and the page top
  // bar of the plain pages start with it. It is not a link.
  import { t } from './i18n'
  import { NOCK_MARK_POINTS } from './icons'
</script>

<span class="topbar-brand" data-testid="topbar-brand"
  ><svg viewBox="0 0 10 14" aria-hidden="true"><polygon points={NOCK_MARK_POINTS} /></svg
  >{t('app.title')}</span
>

<style>
  .topbar-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    font: 700 1.3rem/1 var(--nock-font-ui);
    letter-spacing: 0.01em;
    color: var(--nock-navy);
  }

  .topbar-brand svg {
    width: 12px;
    height: 18px;
    fill: var(--nock-navy);
  }
</style>
