# Beta NDA

The NDA that beta testers sign before they can use the dashboard (nda.py, docs/design/beta_nda.md).

To set it up, put the PDF here and add `current.json`:

```json
{"version": "2026-11-draft", "file": "angstrom-beta-nda-draft.pdf", "title": "Angstrom Signals Beta NDA", "enforce": false}
```

- `enforce: false`: nobody is asked to sign; admins can open **Preview the NDA page** in the Beta requests panel.
- `enforce: true`: every account except admins must sign this version at its next sign-in.
- A new PDF needs a new `version`: everyone signs again. Never replace a PDF under a version people have signed;
  the fingerprint on their signed copies would no longer match.

Optional keys (19 Nov 2026):

- `applies_from: "YYYY-MM-DD"`: only accounts made on or after that day are asked; older accounts keep working.
- `exempt: ["address", …]`: accounts never asked (the demo account used to record the videos).

The PDF is built from its Markdown source: `python legal/nda/build_pdf.py legal/nda/nda_v3.md
legal/nda/Angstrom_Signals_Private_Beta_NDA_v3.pdf "V3.0"`. For a change, write a new source and a new version.
