"""check_sources.py - Checks which source websites can be opened from THIS computer.

Run on your laptop:        python scripts/check_sources.py
Run in GitHub (cloud):     Actions tab -> "Check sources" -> Run workflow
Compare both. Some government sites block cloud computers or have certificate problems.
(Nothing is saved, and certificate checks are never switched off.)
"""
import time

import requests

SOURCES = [
    ("CERT-In", "https://www.cert-in.org.in/"),
    ("CERT-In awareness booklets", "https://www.cert-in.org.in/AwarenessBooklets.jsp"),
    ("Cyber Crime Portal", "https://cybercrime.gov.in/"),
    ("RBI", "https://www.rbi.org.in/"),
    ("NPCI", "https://www.npci.org.in/"),
    ("UIDAI", "https://uidai.gov.in/"),
    ("TRAI", "https://www.trai.gov.in/"),
    ("PIB", "https://www.pib.gov.in/"),
    ("Google Security blog", "https://security.googleblog.com/"),
    ("Google Security blog feed", "https://security.googleblog.com/feeds/posts/default"),
    ("Microsoft Security blog", "https://www.microsoft.com/en-us/security/blog/"),
    ("Microsoft Security blog feed", "https://www.microsoft.com/en-us/security/blog/feed/"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; digital-samajh-source-check/0.1)"}


def check(name: str, url: str) -> bool:
    start = time.time()
    try:
        response = requests.get(url, headers=HEADERS, timeout=(10, 25), allow_redirects=True)
    except requests.RequestException as exc:
        print(f"FAIL  {name:<30} {type(exc).__name__}: {str(exc)[:110]}")
        return False
    seconds = time.time() - start
    kind = response.headers.get("Content-Type", "?").split(";")[0]
    ok = response.status_code == 200
    note = "" if response.url.rstrip("/") == url.rstrip("/") else f" -> redirected to {response.url}"
    status = "OK  " if ok else "FAIL"
    print(f"{status}  {name:<30} HTTP {response.status_code}, {seconds:.1f}s, "
          f"{len(response.content) // 1024} KB, {kind}{note}")
    return ok


def main() -> None:
    results = [check(name, url) for name, url in SOURCES]
    print(f"\n{sum(results)} of {len(results)} sources opened successfully.")


if __name__ == "__main__":
    main()