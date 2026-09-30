"""Form-specific routines for extracting one print-ready 1099 form page."""

from __future__ import annotations

from copy import deepcopy

from pypdf import Transformation

LETTER_WIDTH = 612.0
LETTER_HEIGHT = 792.0

# Distance between the same field on consecutive forms in the supplied sample
# PDFs.  These are deliberately not LETTER_HEIGHT / number_of_forms: the forms
# overlap the nominal equal-size strips and therefore require their own stride.
MISC_VERTICAL_STRIDE = 415.45
NEC_VERTICAL_STRIDE = 275.25


def split_form_k(source_page):
    """Return the sole form on a Form K page; it needs no physical split."""
    return [deepcopy(source_page)]


def split_form_misc(source_page):
    """Split the two vertically stacked Form MISC entries into Letter pages."""
    return _split_vertical_entries(
        source_page,
        parts=2,
        vertical_stride=MISC_VERTICAL_STRIDE,
    )


def split_form_nec(source_page):
    """Split the three vertically stacked Form NEC entries into Letter pages."""
    return _split_vertical_entries(
        source_page,
        parts=3,
        vertical_stride=NEC_VERTICAL_STRIDE,
    )


def split_form(form_type: str, source_page):
    """Dispatch to the splitting logic specific to a supported form type."""
    splitters = {
        "FormK": split_form_k,
        "FormMISC": split_form_misc,
        "FormNEC": split_form_nec,
    }
    try:
        return splitters[form_type](source_page)
    except KeyError as error:
        raise ValueError(f"Unsupported form type: {form_type}") from error


def _split_vertical_entries(source_page, parts: int, vertical_stride: float):
    """Clip each source region and align its fields with the first entry."""
    left = float(source_page.mediabox.left)
    bottom = float(source_page.mediabox.bottom)
    right = float(source_page.mediabox.right)
    top = float(source_page.mediabox.top)
    width = right - left
    clip_height = (top - bottom) / parts
    pages = []

    for index in range(parts):
        crop_bottom = top - (index + 1) * clip_height
        crop_top = top - index * clip_height
        cropped_page = deepcopy(source_page)
        cropped_page.mediabox.lower_left = (left, crop_bottom)
        cropped_page.mediabox.upper_right = (right, crop_top)
        cropped_page.cropbox.lower_left = (left, crop_bottom)
        cropped_page.cropbox.upper_right = (right, crop_top)

        # The samples are already Letter-width and must not be resized. Move
        # each later form by its measured form-to-form stride so its fields
        # occupy exactly the same coordinates as the first form.
        scale = LETTER_WIDTH / width
        offset_x = (LETTER_WIDTH - width * scale) / 2
        offset_y = index * vertical_stride
        letter_page = source_page.create_blank_page(
            width=LETTER_WIDTH, height=LETTER_HEIGHT
        )
        transform = (
            Transformation()
            .translate(-left, 0)
            .scale(scale)
            .translate(offset_x, offset_y)
        )
        letter_page.merge_transformed_page(cropped_page, transform)
        pages.append(letter_page)

    return pages
