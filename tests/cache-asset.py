#!/usr/bin/env python3
"""Fetch a pinned provisioning artifact once into the local mirror."""

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen

url, expected, filename = sys.argv[1:]
if urlsplit(url).scheme != "https" or Path(filename).name != filename or filename in (".", ".."):
    raise ValueError("Use an HTTPS URL and a plain artifact filename")
if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
    raise ValueError("A pinned SHA-256 digest is required")
root = Path(__file__).resolve().parents[1] / ".local/mirror/assets"
root.mkdir(parents=True, exist_ok=True)
destination = root / filename
if destination.exists():
    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
        raise ValueError("Existing cached artifact does not match the pinned digest")
    print(f"Cached artifact verified: {filename}")
else:
    temporary = None
    try:
        digest = hashlib.sha256()
        with urlopen(url, timeout=120) as response, tempfile.NamedTemporaryFile(dir=root, delete=False) as file:
            temporary = Path(file.name)
            while chunk := response.read(1024**2):
                digest.update(chunk)
                file.write(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Downloaded artifact does not match the pinned digest")
        os.replace(temporary, destination)
        (root / (filename + ".source.json")).write_text(json.dumps({"url": url, "sha256": expected}, indent=2) + "\n")
        print(f"Downloaded and verified: {filename}")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
