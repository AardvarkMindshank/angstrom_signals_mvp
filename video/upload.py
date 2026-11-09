"""Upload finished training videos to the website over encrypted FTP (FTPS).

The FTP account's home is the site's videos/ folder. Videos go to videos/<section>/ (training now, marketing later);
the folder is created if missing. The login comes from GitHub secrets (HOSTGATOR_FTP_HOST, _USER, _PASSWORD) and is
never printed. Without them, nothing is uploaded and the job says so.

    python video/upload.py out/video training your-first-prism-scan
"""

import ftplib
import os
import ssl
import sys
from pathlib import Path


def main(out: Path, section: str, slug: str) -> int:
    """slug "--page": every file in `out` (the training page and its logos), as they are named."""
    host, user, password = (os.environ.get(f"HOSTGATOR_FTP_{k}", "").strip() for k in ("HOST", "USER", "PASSWORD"))
    if not (host and user and password):
        print("Upload skipped: the HOSTGATOR_FTP_* secrets are not set.")
        return 0
    if slug == "--page":
        files = {p.name: p for p in sorted(out.iterdir()) if p.is_file()}
    else:
        files = {f"{slug}.mp4": out / "video.mp4", f"{slug}.srt": out / "captions.srt"}
    def connect(verify: bool):
        context = ssl.create_default_context()
        if not verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        ftp = ftplib.FTP_TLS(host, timeout=60, context=context)
        ftp.login(user, password)
        return ftp

    try:
        try:
            ftp = connect(verify=True)
        except ssl.SSLCertVerificationError:
            # Shared hosting often shows the server's own certificate name, not the domain's: still encrypted.
            print("Note: the FTP server's certificate does not name this host; the connection is still encrypted.")
            ftp = connect(verify=False)
    except ftplib.error_perm as exc:
        print(f"Upload failed: HostGator refused the login ({str(exc)[:60]}). The server was reached, so check "
              "HOSTGATOR_FTP_USER (the full name, e.g. videos@yourdomain) and HOSTGATOR_FTP_PASSWORD.")
        print(f"(The username has {len(user)} characters and {'contains' if '@' in user else 'does not contain'} '@'.)")
        return 1
    ftp.prot_p()                                   # encrypt the file transfers too
    try:
        ftp.mkd(section)
    except ftplib.error_perm:
        pass                                       # already there
    ftp.cwd(section)
    for name, path in files.items():
        if not path.exists():
            continue
        with path.open("rb") as fh:
            ftp.storbinary(f"STOR {name}", fh)
        print(f"Uploaded {section}/{name} ({path.stat().st_size // 1024} KB)")
    ftp.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3]))
