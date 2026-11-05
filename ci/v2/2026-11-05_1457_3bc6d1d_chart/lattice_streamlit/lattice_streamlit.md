# Lattice editor inside Streamlit

| Check | Result | Detail |
|---|---|---|
| the editor appears | pass |  |
| an empty Group cannot be saved | pass |  |
| tap + reaches Python and comes back | pass |  |
| the description is rewritten | pass | Skip to main content
Deploy

📁 Group editor

🗂️ Set editor

🧩 Lattice · Group editor (admin preview). Build a Group by dragging signals in, or tap + on a tablet. Rules give it labels such as Bullis |
| saving is allowed once valid | pass |  |
| a rule can be added | pass |  |
| an out-of-scale threshold blocks saving | pass | Can't save: Rule 1: a score threshold is outside the Group score scale, −100 to +100 |
| Set editor: a signal and a line go to Python and come back | pass | says Yes when RSI (14) (1D) rsi is at least +30. If any line fails it says No, even with missing data; if nothing fails but something needed is missing, it says Unknown and names it. |
| no browser errors | pass |  |
