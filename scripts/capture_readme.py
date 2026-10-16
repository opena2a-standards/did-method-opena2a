#!/usr/bin/env python3
"""Re-take the sample output the README shows under its commands.

Each capture runs one command the README shows, from the repository root
through /bin/sh, and writes what it prints (standard output and standard error
together, as a terminal shows them) to docs/captures/<name>.txt, with a
sidecar docs/captures/<name>.json that records the command, its exit code,
the UTC time it ran and the SHA-256 of the .txt. The README shows each capture
under a label naming its command, trimmed to whole lines;
scripts/test_readme.py checks that every excerpt is cut from its capture
without changing a line. The resolution captures need curl, jq and network
access to the reference deployment. python3 standard library only.

Usage: python3 scripts/capture_readme.py [<name> ...]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CAPTURES_DIR = ROOT / "docs" / "captures"

# name -> the command exactly as the README shows it.
CAPTURES = {
    "resolve-registry":
        "curl -s https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org | jq .",
    "resolve-mcp-server":
        "curl -s 'https://api.oa2a.org/api/v1/did/did:opena2a:mcp_server:@modelcontextprotocol/server-filesystem' | jq .",
    "resolve-registry-headers":
        "curl -si https://api.oa2a.org/api/v1/did/did:opena2a:registry:opena2a.org",
    "check-examples-live": "python3 scripts/check_examples.py --live",
    "check-vectors": "python3 scripts/check_vectors.py",
}
TIMEOUT_SECONDS = 60


def capture(name: str) -> int:
    command = CAPTURES[name]
    ran_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = subprocess.run(command, shell=True, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=TIMEOUT_SECONDS)
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    (CAPTURES_DIR / f"{name}.txt").write_bytes(result.stdout)
    sidecar = {
        "command": command,
        "exitCode": result.returncode,
        "capturedAt": ran_at,
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
    }
    (CAPTURES_DIR / f"{name}.json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(f"docs/captures/{name}.txt: exit {result.returncode}, {len(result.stdout)} bytes")
    return result.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", metavar="name", help=f"captures to re-take (default: all): {', '.join(CAPTURES)}")
    args = ap.parse_args()
    unknown = [n for n in args.names if n not in CAPTURES]
    if unknown:
        ap.error(f"unknown capture: {', '.join(unknown)}")
    failed = [n for n in (args.names or CAPTURES) if capture(n) != 0]
    if failed:
        print(f"exited non-zero: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
