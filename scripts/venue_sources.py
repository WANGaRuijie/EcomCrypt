"""Resolve planned venues to exact OpenAlex sources, keeping ambiguity explicit."""

import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request

from directory import read_json, write_json
from metadata import MetadataError, cache_path, normalize_title


def source_name(value):
    return normalize_title(re.sub(r"\s*\([A-Za-z& -]+\)\s*$", "", value))


def resolve_sources(client, venue):
    params = {"search": venue["name"], "per_page": 10}
    public_url = "https://api.openalex.org/sources?" + urlencode(params)
    path = cache_path(client.cache_dir / "sources", public_url)
    if path.exists() and not client.refresh:
        envelope = read_json(path)
    elif client.offline:
        raise MetadataError("offline_cache_miss")
    else:
        url = public_url
        if client.openalex_key:
            url += "&" + urlencode({"api_key": client.openalex_key})
        payload = client._download("openalex", Request(url, headers={
            "Accept": "application/json", "User-Agent": "EconCS-Scholar-Directory/1.0",
        }))
        if not isinstance(payload.get("results"), list):
            raise MetadataError("unexpected_source_response")
        envelope = {"url": public_url, "retrieved_at": datetime.now(timezone.utc).date().isoformat(), "payload": payload}
        write_json(path, envelope)
    names = {source_name(name) for name in [venue["name"], *venue["aliases"]]}
    matches = [
        row for row in envelope["payload"]["results"]
        if source_name(row.get("display_name", "")) in names
        and row.get("type") == ("journal" if venue["kind"] == "journal" else "conference")
        and re.fullmatch(r"https://openalex.org/S\d+", row.get("id", ""))
        and (not venue.get("issns") or set(venue["issns"]) & set(row.get("issn") or []))
    ]
    return {
        "lane": f"venue-resolution:{venue['id']}",
        "status": "ok" if len(matches) == 1 else "unresolved",
        "complete": len(matches) == 1,
        "records": len(matches),
        "query_url": envelope["url"],
        "retrieved_at": envelope["retrieved_at"],
        "matches": [{key: row.get(key) for key in ("id", "display_name", "type", "issn", "issn_l")} for row in matches],
    }
