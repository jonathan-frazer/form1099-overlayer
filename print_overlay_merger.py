"""Overlay filled 1099 values onto a scaled blank-background PDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation

# Form K calibration from the original overlay script.  The values layer is
# never transformed.  Each form has an independent calibration block so it can
# be adjusted during alignment testing without affecting the other forms.
FORM_K_BACKGROUND_SCALE = 1.046025105
FORM_K_BACKGROUND_OFFSET_X = -32.165272
FORM_K_BACKGROUND_OFFSET_Y = -12.521065

# The MISC and NEC samples use the same Letter-page coordinate system as their
# matching templates.  These values are intentionally separate from Form K.
FORM_MISC_BACKGROUND_SCALE = 1.046025105
FORM_MISC_BACKGROUND_OFFSET_X = -32.165272
FORM_MISC_BACKGROUND_OFFSET_Y = -12.521065

# NEC has independent settings, but its official template needs the same
# calibrated enlargement/translation to meet the values coordinate system.
FORM_NEC_BACKGROUND_SCALE = 1.046025105
FORM_NEC_BACKGROUND_OFFSET_X = -32.165272
FORM_NEC_BACKGROUND_OFFSET_Y = -12.521065


def merge_form_k(background_path: str | Path, values_path: str | Path, output_path: str | Path) -> None:
    """Merge a Form 1099-K using the existing, verified K calibration."""
    _combine_with_calibration(
        background_path, values_path, output_path,
        FORM_K_BACKGROUND_SCALE, FORM_K_BACKGROUND_OFFSET_X, FORM_K_BACKGROUND_OFFSET_Y,
    )


def merge_form_misc(background_path: str | Path, values_path: str | Path, output_path: str | Path) -> None:
    """Merge a Form 1099-MISC with its own calibration settings."""
    _combine_with_calibration(
        background_path, values_path, output_path,
        FORM_MISC_BACKGROUND_SCALE, FORM_MISC_BACKGROUND_OFFSET_X, FORM_MISC_BACKGROUND_OFFSET_Y,
    )


def merge_form_nec(background_path: str | Path, values_path: str | Path, output_path: str | Path) -> None:
    """Merge a Form 1099-NEC with its own calibration settings."""
    _combine_with_calibration(
        background_path, values_path, output_path,
        FORM_NEC_BACKGROUND_SCALE, FORM_NEC_BACKGROUND_OFFSET_X, FORM_NEC_BACKGROUND_OFFSET_Y,
    )


def merge_form(form_type: str, background_path: str | Path, values_path: str | Path, output_path: str | Path) -> None:
    """Use the overlay routine calibrated for ``FormK``, ``FormMISC``, or ``FormNEC``."""
    mergers = {
        "FormK": merge_form_k,
        "FormMISC": merge_form_misc,
        "FormNEC": merge_form_nec,
    }
    try:
        mergers[form_type](background_path, values_path, output_path)
    except KeyError as error:
        raise ValueError(f"Unsupported form type: {form_type}") from error


def combine_with_scaled_background(
    background_path: str | Path,
    values_path: str | Path,
    output_path: str | Path,
    *,
    background_scale: float = FORM_K_BACKGROUND_SCALE,
    background_offset_x: float = FORM_K_BACKGROUND_OFFSET_X,
    background_offset_y: float = FORM_K_BACKGROUND_OFFSET_Y,
) -> None:
    """Backward-compatible generic overlay helper using supplied calibration."""
    _combine_with_calibration(
        background_path, values_path, output_path,
        background_scale, background_offset_x, background_offset_y,
    )


def _combine_with_calibration(
    background_path: str | Path,
    values_path: str | Path,
    output_path: str | Path,
    background_scale: float,
    background_offset_x: float,
    background_offset_y: float,
) -> None:
    """Write values over a background page for every page in ``values_path``.

    A one-page background is reused for every values page; otherwise its page
    count must equal the values page count.
    """
    background_path = Path(background_path)
    values_path = Path(values_path)
    output_path = Path(output_path)
    if not background_path.is_file():
        raise FileNotFoundError(f"Background PDF not found: {background_path}")
    if not values_path.is_file():
        raise FileNotFoundError(f"Values PDF not found: {values_path}")

    background_reader = PdfReader(background_path)
    values_reader = PdfReader(values_path)
    if not background_reader.pages:
        raise ValueError(f"Background PDF has no pages: {background_path}")
    if len(background_reader.pages) not in (1, len(values_reader.pages)):
        raise ValueError("Background PDF must have one page or match the values page count.")

    writer = PdfWriter()
    transform = Transformation().scale(background_scale).translate(
        tx=background_offset_x, ty=background_offset_y
    )
    for page_index, values_page in enumerate(values_reader.pages):
        background_page = background_reader.pages[0 if len(background_reader.pages) == 1 else page_index]
        values_width = float(values_page.mediabox.width)
        values_height = float(values_page.mediabox.height)
        background_width = float(background_page.mediabox.width)
        background_height = float(background_page.mediabox.height)
        if abs(values_width - background_width) > 0.01 or abs(values_height - background_height) > 0.01:
            raise ValueError(
                f"Page {page_index + 1} sizes do not match: background "
                f"{background_width} x {background_height}, values {values_width} x {values_height}."
            )
        output_page = writer.add_blank_page(width=values_width, height=values_height)
        output_page.merge_transformed_page(background_page, transform)
        output_page.merge_page(values_page)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_file:
        writer.write(output_file)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("background_pdf", type=Path)
    parser.add_argument("values_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    args = parser.parse_args()
    combine_with_scaled_background(args.background_pdf, args.values_pdf, args.output_pdf)
    print(f"Created: {args.output_pdf}")


if __name__ == "__main__":
    main()
