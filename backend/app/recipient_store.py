"""Small local recipient store, kept outside version control."""

import os
import tempfile
from pathlib import Path

from .email_models import RecipientSettings


class RecipientStore:
    def __init__(self, directory: Path):
        self.path = directory / "recipients.json"

    def load(self) -> RecipientSettings:
        if not self.path.exists():
            return RecipientSettings()
        # Fail visibly if saved data is damaged rather than silently discarding it.
        return RecipientSettings.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, settings: RecipientSettings) -> RecipientSettings:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            # Write then replace so an interrupted write cannot leave half a JSON file.
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix="recipients-", suffix=".tmp", delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(settings.model_dump_json(indent=2))
            os.replace(temporary_path, self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        return settings


# Tests can select a temporary directory without modifying the user's settings.
state_directory = Path(os.environ.get(
    "DASHBOARD_STATE_DIR", str(Path(__file__).resolve().parents[1] / "local-state")
))
recipient_store = RecipientStore(state_directory)
