#!/usr/bin/env python3
"""Summarize actual upstream traffic and local-cache reuse."""

import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".local/mirror/events.jsonl"
events = [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []
downloads = [e for e in events if e["kind"] == "upstream_download"]
hits = [e for e in events if e["kind"] == "served" and e.get("cache_hit")]
assets = [e for e in events if e['kind'] == 'asset_served']
print(json.dumps({"upstream_downloads": len(downloads), "upstream_bytes": sum(e["bytes"] for e in downloads),
                  "cache_hits": len(hits), "bytes_served_from_cache": sum(e["bytes"] for e in hits),
                  "asset_requests": len(assets), "asset_bytes_served_locally": sum(e['bytes'] for e in assets),
                  "errors": [e for e in events if e["kind"] in ("error", "upstream_error")]}, indent=2))
