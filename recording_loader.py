import glob
import json
import os
from dataclasses import dataclass

from pydantic import ValidationError

from schema import Recording


@dataclass
class LoadError:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def load_all_recordings(recordings_dir: str) -> tuple[dict[str, Recording], list[LoadError]]:
    recordings: dict[str, Recording] = {}
    errors: list[LoadError] = []

    paths = sorted(glob.glob(os.path.join(recordings_dir, "*.json")))
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(LoadError(path, f"invalid JSON: {e}"))
            continue
        except OSError as e:
            errors.append(LoadError(path, f"could not read file: {e}"))
            continue

        try:
            recording = Recording.model_validate(raw)
        except ValidationError as e:
            errors.append(LoadError(path, f"schema validation failed: {e}"))
            continue

        if recording.id in recordings:
            errors.append(
                LoadError(path, f"duplicate recording id '{recording.id}' — keeping first-loaded")
            )
            continue

        recordings[recording.id] = recording

    return recordings, errors
