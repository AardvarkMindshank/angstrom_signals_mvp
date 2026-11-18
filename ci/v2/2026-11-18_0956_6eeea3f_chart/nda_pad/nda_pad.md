# NDA signature pad in a browser

| Check | Result | Detail |
|---|---|---|
| a single tap is not a signature | pass |  |
| drawing sends a PNG | pass | [["png",9932]] |
| it is a real PNG | pass | iVBORw0KGgoA |
| a redraw keeps the drawing | pass | 1172 dark pixels |
| Clear empties the signature | pass |  |
| no browser errors | pass |  |
| iPhone: the pad fits the screen | pass | 360px |
| iPhone: drawing with a finger sends a PNG | pass | [["png",42144]] |
