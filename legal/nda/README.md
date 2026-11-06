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
