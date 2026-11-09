"""Harvest AFT proceedings from Dagstuhl XML and corroborate them with DataCite."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree as ET

from directory import read_json, write_json
from metadata import _orcid, normalize_doi, normalize_title
from update import title_topics


ROOT = Path(__file__).resolve().parents[1]
VOLUMES = {2023: 282, 2024: 316, 2025: 354}
NS = {"d": "https://drops.dagstuhl.de/storage/schema/dagstuhl/dagpub.xsd"}


def text(node, name):
    child = node.find(f"d:{name}", NS)
    return " ".join("".join(child.itertext()).split()) if child is not None else ""


def papers_from_volume(xml, registry, xml_url, registry_url):
    root = ET.fromstring(xml)
    volume = root.find("d:volume", NS)
    venue = text(volume.find("d:event", NS), "title")
    year = int(text(volume, "year"))
    by_doi = {row["id"].lower(): row["attributes"] for row in registry["data"]}
    for article in root.findall("d:article", NS):
        doi = normalize_doi(text(article, "doi"))
        if not doi or not doi.rsplit(".", 1)[-1].isdigit() or doi.endswith(".0"):
            continue
        title = text(article, "title")
        byline = article.findall("d:author", NS)
        authors = [text(author, "name") for author in byline]
        registry_entry = by_doi.get(doi, {})
        registry_titles = [item["title"] for item in registry_entry.get("titles", [])]
        registry_authors = [
            " ".join(filter(None, (person.get("givenName"), person.get("familyName"))))
            or person.get("name", "")
            for person in registry_entry.get("creators", [])
        ]
        corroborated = (
            any(normalize_title(t) == normalize_title(title) for t in registry_titles)
            and [normalize_title(n) for n in authors] == [normalize_title(n) for n in registry_authors]
            and bool(authors) and registry_entry.get("publicationYear") == year
        )
        yield {
            "doi": doi, "title": title, "authors": authors, "year": year, "venue": venue,
            "authorships": [
                {"name": name, "ids": {"orcid": orcid} if (orcid := _orcid(text(author, "orcid"))) else {}}
                for name, author in zip(authors, byline)
            ],
            "category": text(article, "category"),
            "abstract": text(article, "abstract"),
            "topic_hints": title_topics(title),
            "cites_dois": sorted({
                doi for reference in article.findall("d:reference", NS)
                for value in (text(reference, "doi"), text(reference, "url"))
                if (doi := normalize_doi(value))
            }),
            "status": "verified" if corroborated else "review_metadata",
            "sources": {"publisher_xml": xml_url, "doi_index_query": registry_url,
                        "doi_index": f"https://api.datacite.org/dois/{doi}"},
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, choices=sorted(VOLUMES), default=sorted(VOLUMES))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cache = ROOT / ".cache/drops"
    cache.mkdir(parents=True, exist_ok=True)
    rows = []
    coverage = []
    for year in sorted(set(args.years)):
        xml_url = f"https://drops.dagstuhl.de/entities/volume/LIPIcs-volume-{VOLUMES[year]}/metadata/xml"
        registry_url = "https://api.datacite.org/dois?" + urlencode({
            "query": f"doi:10.4230/lipics.aft.{year}.*", "page[size]": 100,
        })
        xml_path = cache / f"aft-{year}.xml"
        registry_path = cache / f"aft-{year}-datacite.json"
        if not args.offline:
            with urlopen(xml_url, timeout=15) as response:
                xml = response.read(8_000_000)
            with urlopen(registry_url, timeout=15) as response:
                registry = json.loads(response.read(8_000_000))
            batch = list(papers_from_volume(xml, registry, xml_url, registry_url))
            xml_path.write_bytes(xml)
            write_json(registry_path, registry)
        else:
            registry = read_json(registry_path)
            batch = list(papers_from_volume(xml_path.read_bytes(), registry, xml_url, registry_url))
        rows.extend(batch)
        coverage.append({"venue": f"AFT {year}", "papers": len(batch),
                         "corroborated": sum(row["status"] == "verified" for row in batch),
                         "registry_truncated": registry["meta"]["total"] > len(registry["data"])})
    write_json(args.output, {"schema_version": 1, "coverage": coverage, "papers": rows})
    print(coverage)


if __name__ == "__main__":
    main()
