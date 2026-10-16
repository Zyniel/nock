"""Spec 036 tests: the frames sent at a real socket (AC-7 and AC-9).

The close code and the size limit of the spec, the URL of a room socket, a frame
padded to a given size, and the page script that sends one frame and reports how
the socket was closed. Used by the tests of AC-7 and of AC-9; the tests of AC-10
check the size limit too.

The shared setup of the other themes is in `spec036_harness`.
"""

from __future__ import annotations

from nock.protocol import EditLetter

# ---- Values of the spec --------------------------------------------------------------

TOO_BIG_CODE = 1009
MAX_WS_FRAME_BYTES = 8192


# ---- Frames at the socket (AC-7, AC-9) -----------------------------------------------


def socket_url(base_url: str, code: str) -> str:
    return base_url.replace("http://", "ws://", 1) + f"/api/rooms/{code}/ws"


def padded_frame(size: int) -> str:
    """A valid edit_letter followed by spaces, `size` bytes long in UTF-8."""
    text = EditLetter(row=1, column=0, letter="T").model_dump_json()
    return text + " " * (size - len(text.encode("utf-8")))


# Opens a socket, sends one frame and reports how the socket was closed, and
# everything it received. Gives up after 5 seconds without a close.
OVERSIZED_FRAME_SCRIPT = """
async ({ url, frame, binary }) => {
  const socket = new WebSocket(url);
  const received = [];
  socket.addEventListener("message", (event) => {
    received.push(typeof event.data === "string" ? event.data : "(binary)");
  });
  const closed = new Promise((resolve) => {
    socket.addEventListener("close", (event) => resolve(event.code));
  });
  const opened = await Promise.race([
    new Promise((resolve) => socket.addEventListener("open", () => resolve(true))),
    closed.then(() => false),
  ]);
  if (!opened) {
    return { opened: false, closeCode: await closed, received };
  }
  socket.send(binary ? new TextEncoder().encode(frame) : frame);
  const giveUp = new Promise((resolve) => setTimeout(() => resolve(null), 5000));
  const closeCode = await Promise.race([closed, giveUp]);
  socket.close();
  return { opened: true, closeCode, received };
}
"""
