"""One id per running server, so an open page can tell when the app has been restarted or updated.

Imported modules are kept between script runs, so this is worked out once per server start.
The id is also written to static/boot.txt, which the page checks now and then.
"""

from __future__ import annotations

import os
import time

BOOT_ID = f"{(os.environ.get('RENDER_GIT_COMMIT') or 'local')[:8]}-{int(time.time())}"


def _write_boot_file() -> None:
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "boot.txt"), "w", encoding="utf-8") as handle:
            handle.write(BOOT_ID)
    except OSError:
        pass


_write_boot_file()
