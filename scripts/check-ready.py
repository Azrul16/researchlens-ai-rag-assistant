"""Return readiness without relying on PowerShell's proxy/DNS behavior."""

import sys

import httpx

try:
    response = httpx.get(sys.argv[1], timeout=2, trust_env=False)
    sys.exit(0 if response.status_code == 200 else 1)
except httpx.HTTPError:
    sys.exit(1)
