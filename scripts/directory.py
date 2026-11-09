"""Build the directory projection without inferring identities from names."""

import hashlib
import json
import os
import tempfile
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    """Replace one JSON document atomically, leaving any old file on failure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def new_directory(topics):
    return {
        "schema_version": 1,
        "topics": [{"id": topic["id"], "name": topic["name"]} for topic in topics],
        "institutions": [],
        "researchers": [],
        "papers": [],
    }


def _entity(rows, record, prefix, identifiers):
    identity_ids = {
        key: value for key, value in (record.get("ids") or {}).items()
        if key in identifiers and isinstance(value, str) and value.strip()
    }
    if not identity_ids or not record.get("name"):
        return None

    matching = [
        row for row in rows
        if any(row["identity_ids"].get(key) == value for key, value in identity_ids.items())
    ]
    if matching:
        if len(matching) != 1:
            return None
        row = matching[0]
        if any(
            row["identity_ids"].get(key, value) != value
            for key, value in identity_ids.items()
        ):
            return None
        row["identity_ids"].update(identity_ids)
        return row

    key = next(key for key in identifiers if key in identity_ids)
    digest = hashlib.sha256(f"{key}:{identity_ids[key]}".encode()).hexdigest()[:20]
    row = {"id": f"{prefix}-{digest}", "name": record["name"], "identity_ids": identity_ids}
    rows.append(row)
    return row


def _link_authors(directory, work_id, metadata, edition_id=None):
    researchers = []
    names = []
    credits = []
    for author in metadata.get("authors") or []:
        if isinstance(author, str):
            names.append(author)
            credits.append({"name": author})
            continue
        names.append(author["name"])
        researcher = _entity(
            directory["researchers"], author, "r", ("openalex", "orcid", "dblp")
        )
        credit = {"name": author["name"]}
        credits.append(credit)
        if researcher is None:
            continue
        credit["researcher_id"] = researcher["id"]
        if researcher["id"] not in researchers:
            researchers.append(researcher["id"])
        affiliations = researcher.setdefault("affiliation_ids", [])
        observations = researcher.setdefault("affiliation_evidence", [])
        for institution in author.get("institutions") or []:
            organization = _entity(
                directory["institutions"], institution, "i", ("openalex", "ror")
            )
            if organization is None:
                continue
            if organization["id"] not in affiliations:
                affiliations.append(organization["id"])
            observation = {
                "institution_id": organization["id"],
                "paper_id": work_id,
                "year": institution.get("year", metadata.get("year")),
                "source_id": institution.get("source_id") or
                (metadata.get("source_ids") or {}).get("openalex"),
            }
            if edition_id is not None:
                observation["edition_id"] = edition_id
            if observation not in observations:
                observations.append(observation)
    return names, researchers, credits


def append_work(directory, *, work_id, topic_ids, verification, raw_input):
    """Add one work. A seed's hints never fill gaps in verified metadata."""
    status = verification["status"]
    metadata = (verification.get("metadata") or {}) if status in {"verified", "partial"} else {}
    authors, researcher_ids, credits = _link_authors(directory, work_id, metadata)
    versions = (verification.get("versions") or metadata.get("versions") or []) if metadata else []
    raw = {
        key: raw_input[key]
        for key in ("title", "authors", "year", "venue", "annotation", "source")
        if key in raw_input
    }
    if raw.get("authors"):
        raw["authors"] = [
            author if isinstance(author, str) else author["name"] for author in raw["authors"]
        ]
    paper = {
        "id": work_id,
        "title": metadata.get("title") or raw_input["title"],
        "year": metadata.get("year"),
        "venue": metadata.get("venue"),
        "venue_source": metadata.get("venue_source"),
        "doi": metadata.get("doi"),
        "url": metadata.get("url"),
        "authors": authors,
        "author_credits": credits,
        "researcher_ids": researcher_ids,
        "topic_ids": list(topic_ids),
        "status": status,
        "kind": metadata.get("kind"),
        "formal_publication": is_formal_publication(metadata),
        "source_ids": metadata.get("source_ids") or {},
        "versions": [
            {key: version.get(key) for key in ("title", "year", "venue", "doi", "url", "kind", "source_ids")}
            for version in versions
        ],
        "raw_input": raw,
    }
    for version in versions:
        if not is_formal_publication(version) or not version.get("doi") or version["doi"] == paper["doi"]:
            continue
        edition_id = f"{work_id}@{version['doi']}"
        publications = paper.setdefault("publications", [])
        if any(edition["id"] == edition_id for edition in publications):
            continue
        names, linked, version_credits = _link_authors(directory, work_id, version, edition_id)
        publications.append({
            **{key: version.get(key) for key in ("title", "year", "venue", "venue_source", "relation_source", "earlier_version_evidence", "doi", "url", "kind", "source_ids")},
            "id": edition_id, "authors": names, "researcher_ids": linked, "author_credits": version_credits,
        })
    if metadata and "index_result" in verification:
        paper["primary_sources"] = [
            {"source": row["source"], "url": row["source_url"], "locator": row["locator"]}
            for row in verification["evidence"]
        ]
    directory["papers"].append(paper)
    return paper


def is_formal_publication(record):
    venue = (record.get("venue") or "").lower()
    doi = record.get("doi") or ""
    return (
        record.get("kind") in {"article", "journal-article", "conference-paper", "proceedings-article",
                               "conference-abstract", "book-chapter"}
        and not doi.startswith(("10.48550/arxiv.", "10.2139/ssrn."))
        and not any(label in venue for label in ("arxiv", "ssrn", "eprint", "sigecom exchanges"))
    )


def work_keys(paper):
    """Identifiers shared with the updater. A similar title is not an ID."""
    keys = set()
    for version in (paper, *paper.get("versions", [])):
        doi = version.get("doi")
        if doi:
            keys.add(("doi", doi.lower().removeprefix("https://doi.org/")))
        for source, source_id in (version.get("source_ids") or {}).items():
            if source_id:
                keys.add((source, source_id))
    return keys


def validate_directory(directory):
    if directory.get("schema_version") != 1:
        raise ValueError("unsupported directory schema")
    entities = {}
    for collection in ("topics", "institutions", "researchers", "papers"):
        rows = directory[collection]
        entities[collection] = {row["id"] for row in rows}
        if len(entities[collection]) != len(rows):
            raise ValueError(f"duplicate {collection} ID")
    owners = {}
    for paper in directory["papers"]:
        if not paper["title"] or not paper["topic_ids"]:
            raise ValueError(f"missing title or topic for {paper['id']}")
        if paper["status"] not in {"verified", "partial", "ambiguous", "unverified"}:
            raise ValueError(f"unknown verification status for {paper['id']}")
        if not set(paper["topic_ids"]) <= entities["topics"]:
            raise ValueError(f"unknown topic for {paper['id']}")
        if not set(paper["researcher_ids"]) <= entities["researchers"]:
            raise ValueError(f"unknown researcher for {paper['id']}")
        if paper["status"] in {"ambiguous", "unverified"} and any(
            paper[key] for key in ("year", "venue", "doi", "url", "authors", "researcher_ids", "source_ids", "versions")
        ):
            raise ValueError(f"uncorroborated metadata for {paper['id']}")
        for key in work_keys(paper):
            owner = owners.setdefault(key, paper["id"])
            if owner != paper["id"]:
                raise ValueError(f"shared work identifier {key} for {owner} and {paper['id']}")
    for researcher in directory["researchers"]:
        if not set(researcher["affiliation_ids"]) <= entities["institutions"]:
            raise ValueError(f"unknown institution for {researcher['id']}")
        for observation in researcher.get("affiliation_evidence", []):
            if observation["institution_id"] not in researcher["affiliation_ids"]:
                raise ValueError(f"unlinked affiliation for {researcher['id']}")
            if observation["paper_id"] not in entities["papers"]:
                raise ValueError(f"unknown affiliation paper for {researcher['id']}")
