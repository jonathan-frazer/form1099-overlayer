"""Generate configured 1099 overlay samples using config.json."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from typing import Any

from pypdf import PdfReader, PdfWriter

from form_splitters import split_form
from print_overlay_merger import merge_form


FORM_DEFINITIONS = {
    "Form1099K": ("FormK", "FormK-Examples"),
    "Form1099MISC": ("FormMISC", "FormMISC-Examples"),
    "Form1099NEC": ("FormNEC", "FormNEC-Examples"),
}
OUTPUT_DIRECTORY_NAME = "Output"


@dataclass(frozen=True)
class FormSettings:
    config_name: str
    form_type: str
    folder_name: str
    active: bool
    form_splitting: bool
    selected_page: int | None
    selected_segment: int | None
    page_count: int


def _integer_or_random(value: Any, field: str, form_name: str) -> int | None:
    """Return None for a random choice, otherwise a positive integer."""
    if value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{form_name}.{field} must be a positive integer or an empty string")
    return value


def load_and_validate_config(
    project_directory: Path, config_path: Path
) -> tuple[str, str, list[FormSettings]]:
    """Load and fully validate configuration before creating any output."""
    try:
        with config_path.open("r", encoding="utf-8") as stream:
            config = json.load(stream)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {config_path}: {error}") from error

    if not isinstance(config, dict):
        raise ValueError("The config root must be a JSON object")
    background_name = config.get("BackgroundName")
    samples_name = config.get("SamplesName")
    forms = config.get("forms")
    if not isinstance(background_name, str) or not background_name.strip():
        raise ValueError("BackgroundName must be a non-empty filename")
    if not isinstance(samples_name, str) or not samples_name.strip():
        raise ValueError("SamplesName must be a non-empty filename")
    if not isinstance(forms, list):
        raise ValueError("forms must be a JSON array")

    expected_names = set(FORM_DEFINITIONS)
    configured_names: set[str] = set()
    settings: list[FormSettings] = []
    for index, item in enumerate(forms, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"forms[{index}] must be a JSON object")
        name = item.get("name")
        if name not in FORM_DEFINITIONS:
            raise ValueError(f"forms[{index}].name must be one of {sorted(expected_names)}")
        if name in configured_names:
            raise ValueError(f"Duplicate form configuration: {name}")
        configured_names.add(name)

        active = item.get("active")
        form_splitting = item.get("formSplitting")
        if not isinstance(active, bool):
            raise ValueError(f"{name}.active must be true or false (without quotes)")
        if not isinstance(form_splitting, bool):
            raise ValueError(f"{name}.formSplitting must be true or false (without quotes)")

        selected_page = _integer_or_random(item.get("selectedPage", ""), "selectedPage", name)
        selected_segment = _integer_or_random(
            item.get("selectedSegment", ""), "selectedSegment", name
        )
        form_type, folder_name = FORM_DEFINITIONS[name]

        # Inactive forms are configuration placeholders only. Avoid touching
        # their files or parsing their PDFs until the form is enabled.
        if not active:
            settings.append(
                FormSettings(
                    config_name=name,
                    form_type=form_type,
                    folder_name=folder_name,
                    active=False,
                    form_splitting=form_splitting,
                    selected_page=selected_page,
                    selected_segment=selected_segment,
                    page_count=0,
                )
            )
            continue

        samples_path = project_directory / folder_name / samples_name
        background_path = project_directory / folder_name / background_name
        if not samples_path.is_file():
            raise FileNotFoundError(f"Samples PDF not found for {name}: {samples_path}")
        if not background_path.is_file():
            raise FileNotFoundError(f"Background PDF not found for {name}: {background_path}")

        samples_reader = PdfReader(samples_path)
        page_count = len(samples_reader.pages)
        if page_count == 0:
            raise ValueError(f"Samples PDF has no pages: {samples_path}")
        if selected_page is not None and selected_page > page_count:
            raise ValueError(
                f"{name}.selectedPage is {selected_page}, but {samples_name} has only "
                f"{page_count} pages"
            )

        segment_count = len(split_form(form_type, samples_reader.pages[0]))
        if form_splitting and selected_segment is not None and selected_segment > segment_count:
            raise ValueError(
                f"{name}.selectedSegment is {selected_segment}, but {name} has only "
                f"{segment_count} segment(s)"
            )

        settings.append(
            FormSettings(
                config_name=name,
                form_type=form_type,
                folder_name=folder_name,
                active=active,
                form_splitting=form_splitting,
                selected_page=selected_page,
                selected_segment=selected_segment,
                page_count=page_count,
            )
        )

    missing = expected_names - configured_names
    if missing:
        raise ValueError(f"Missing form configuration(s): {', '.join(sorted(missing))}")
    return background_name, samples_name, settings


def write_single_page(page, path: Path) -> None:
    writer = PdfWriter()
    writer.add_page(page)
    with path.open("wb") as stream:
        writer.write(stream)


def generate_samples(project_directory: Path, config_path: Path) -> list[Path]:
    """Generate active forms according to the validated JSON configuration."""
    background_name, samples_name, settings = load_and_validate_config(
        project_directory, config_path
    )
    active_settings = [item for item in settings if item.active]
    if not active_settings:
        return []

    rng = Random()
    output_directory = project_directory / OUTPUT_DIRECTORY_NAME
    output_directory.mkdir(exist_ok=True)
    outputs: list[Path] = []
    with TemporaryDirectory(prefix="1099-overlay-") as temporary_directory:
        temporary_directory_path = Path(temporary_directory)
        for item in active_settings:
            form_directory = project_directory / item.folder_name
            samples_reader = PdfReader(form_directory / samples_name)
            page_number = item.selected_page or rng.randrange(item.page_count) + 1
            source_page = samples_reader.pages[page_number - 1]

            segment_number: int | None = None
            if item.form_splitting:
                segments = split_form(item.form_type, source_page)
                segment_number = item.selected_segment or rng.randrange(len(segments)) + 1
                values_page = segments[segment_number - 1]
            else:
                values_page = deepcopy(source_page)

            values_path = temporary_directory_path / f"{item.form_type}-values.pdf"
            write_single_page(values_page, values_path)
            filename = f"1099{item.form_type}-Pg{page_number}"
            if segment_number is not None:
                filename += f"-Segment{segment_number}"
            output_path = output_directory / f"{filename}-FullPrinted.pdf"
            merge_form(
                item.form_type,
                form_directory / background_name,
                values_path,
                output_path,
            )
            outputs.append(output_path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, help="Config path (default: config.json beside run.py)"
    )
    args = parser.parse_args()
    project_directory = Path(__file__).resolve().parent
    config_path = args.config or project_directory / "config.json"
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    outputs = generate_samples(project_directory, config_path)
    if not outputs:
        print("No PDFs generated: every form is inactive.")
        return
    for output in outputs:
        print(f"Created: {output.relative_to(project_directory)}")


if __name__ == "__main__":
    main()
