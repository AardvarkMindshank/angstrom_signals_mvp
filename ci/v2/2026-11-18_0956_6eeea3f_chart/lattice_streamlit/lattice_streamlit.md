# Lattice editor inside Streamlit

| Check | Result | Detail |
|---|---|---|
| the editor appears | pass |  |
| the editor's styles are applied | pass | flex |
| an empty Group cannot be saved | pass |  |
| ran to the end | FAIL | TimeoutError: page.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('button[aria-label="Add RSI (14) to the Group"]')
 |
