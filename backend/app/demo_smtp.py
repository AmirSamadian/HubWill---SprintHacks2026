"""Account-free SMTP capture server. Run with: python -m app.demo_smtp."""

import threading
from pathlib import Path
from uuid import uuid4

from aiosmtpd.controller import Controller

from .recipient_store import state_directory


class CaptureHandler:
    def __init__(self, directory: Path):
        self.directory = directory

    async def handle_DATA(self, server, session, envelope):
        # Store the complete email locally. This handler never forwards mail.
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{uuid4().hex}.eml"
        path.write_bytes(envelope.original_content)
        print(f"Captured locally: {path}", flush=True)
        return "250 Message captured locally; not delivered to external inboxes"


def main() -> None:
    controller = Controller(
        CaptureHandler(state_directory / "demo-mail"), hostname="127.0.0.1", port=8025,
    )
    controller.start()
    print("Demo SMTP listening on 127.0.0.1:8025. Press Ctrl+C to stop.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
