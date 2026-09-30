# PDF 1099 Overlay Generator

This program selects a page from each configured 1099 sample PDF, optionally
extracts one form segment, and places the sample values over the matching blank
form background.

## Running the program

Edit `config.json`, then run:

```powershell
python run.py
```

Generated PDFs are written to the `Output` folder.

## What changes: text, background, or both?

The text content itself is never edited. Names, addresses, amounts, tax IDs,
and all other values remain exactly as they appear in `Samples.pdf`.

The following geometric changes can occur:

| Situation | Values/text layer | Background layer |
|---|---|---|
| Form 1099-K with splitting disabled | Unchanged | Scaled and repositioned using the K calibration |
| Form 1099-MISC or NEC with splitting enabled | Cropped to the selected segment and repositioned; text content is unchanged | Scaled and repositioned using that form's calibration |
| Any form with splitting disabled | The complete selected sample page is unchanged | Scaled and repositioned using that form's calibration |

Therefore:

- The overlay merger changes **only the background**. It never scales,
  translates, or rewrites the values/text layer.
- The splitting stage can crop and reposition the values layer for MISC and
  NEC, but it does not alter the text itself.
- For a split MISC or NEC output, **both layers are geometrically processed**:
  the selected values segment is repositioned first, then the background is
  calibrated during the merge.
- For Form K with its normal configuration, **only the background is
  geometrically changed**.

## Configuration

`config.json` contains shared filenames and one entry for every form type:

```json
{
  "BackgroundName": "Background.pdf",
  "SamplesName": "Samples.pdf",
  "forms": [
    {
      "name": "Form1099MISC",
      "active": true,
      "formSplitting": true,
      "selectedPage": 10,
      "selectedSegment": 1
    }
  ]
}
```

- `active`: Generate this form when `true`. Inactive forms do not access or
  validate their PDF files.
- `formSplitting`: Extract one form segment when `true`. When `false`, the
  complete selected sample page is used.
- `selectedPage`: A one-based page number. Use `""` to select a random page.
- `selectedSegment`: A one-based segment number. Use `""` to select a random
  segment. This setting is used only when splitting is enabled.
- `BackgroundName`: Background filename expected inside each active form's
  example folder.
- `SamplesName`: Samples filename expected inside each active form's example
  folder.

Page and segment selections are validated before output generation. A number
outside the available range raises an exception.
