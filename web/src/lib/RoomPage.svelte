<script lang="ts">
  import GridViewport from './GridViewport.svelte'
  import { t } from './i18n'
  import { gridLabel, newSession, receiveFrame, statusAfterClose } from './roomSession'

  let { code }: { code: string } = $props()

  let session = $state(newSession())

  function roomSocketUrl(roomCode: string): string {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${scheme}://${location.host}/api/rooms/${roomCode}/ws`
  }

  $effect(() => {
    const socket = new WebSocket(roomSocketUrl(code))

    socket.onopen = () => {
      const join = { type: 'join', nickname: t('room.default_nickname'), resume_token: null }
      socket.send(JSON.stringify(join))
    }
    socket.onmessage = (event: MessageEvent) => {
      if (typeof event.data === 'string') {
        receiveFrame(session, event.data)
      }
    }
    socket.onclose = (event: CloseEvent) => {
      session.status = statusAfterClose(event.code)
    }
    socket.onerror = () => {
      if (session.status !== 'not_found') {
        session.status = 'closed'
      }
    }

    // Leaving the page closes the socket; the handlers must not react to it.
    return () => {
      socket.onclose = null
      socket.onerror = null
      socket.close()
    }
  })
</script>

<main
  data-testid="room-page"
  data-room-code={code}
  data-status={session.status}
  data-seq={session.seq === null ? '' : String(session.seq)}
  data-pending={String(session.pending.length)}
  data-grid={gridLabel(session)}
>
  <h1>{t('room.heading', { code })}</h1>
  <p data-testid="room-status">{t(`room.status.${session.status}`)}</p>
  {#if session.snapshot !== null}
    <GridViewport grid={session.snapshot.grid} />
  {/if}
</main>
