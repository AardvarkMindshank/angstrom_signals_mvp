"""Remove the training videos from angstromsignals.com after the move to marketnavi.ai (22 Nov 2026): every file and
folder under the old videos login's home (its home is that site's videos/ folder). The login comes from the
HOSTGATOR_FTP_* secrets, as for upload.py."""
import ftplib
import os
import ssl
import sys


def wipe(ftp, path: str) -> int:
    n = 0
    for name, facts in list(ftp.mlsd(path)):
        if name in (".", ".."):
            continue
        full = f"{path}/{name}" if path else name
        if facts.get("type") == "dir":
            n += wipe(ftp, full)
            ftp.rmd(full)
            print(f"removed folder {full}")
        else:
            ftp.delete(full)
            n += 1
    return n


def main() -> int:
    host, user, password = (os.environ.get(f"HOSTGATOR_FTP_{k}", "").strip() for k in ("HOST", "USER", "PASSWORD"))
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE             # shared hosting names its own server; still encrypted
    ftp = ftplib.FTP_TLS(host, timeout=60, context=context)
    ftp.login(user, password)
    ftp.prot_p()
    print(f"removed {wipe(ftp, '')} file(s)")
    ftp.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
