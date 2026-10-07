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

        unknown_types = sorted(
            {
                sel.type
                for step in recording.steps
                if step.target
                for sel in list(step.target.selectors) + list(step.target.frame_path)
                if not sel.is_known
            }
        )
        if unknown_types:
            # Registered anyway: the other selectors in each list still work,
            # and refusing the whole recording over this would take the tool
            # offline entirely.
            errors.append(
                LoadError(
                    path,
                    f"selector types {unknown_types} are not supported and will be skipped; "
                    "steps relying only on them will fail",
                )
            )

        if len(recording.description.strip()) < 10:
            # Registered anyway — this is a quality warning, not a defect. The
            # description is the only thing an LLM reads when choosing between
            # tools, so a terse one makes it pick badly once there are several.
            errors.append(
                LoadError(
                    path,
                    f"description is very short ({recording.description!r}); an LLM picks "
                    "between tools by this text alone, so consider spelling out what it does",
                )
            )

        recordings[recording.id] = recording

    return recordings, errors
