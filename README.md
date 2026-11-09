# EcomCrypt

A curated directory of research at the intersection of **economics** (game theory, mechanism design, incentives, finance, OR/MS) and **computing systems that have to withstand strategic behavior** (blockchains, cryptography, security, distributed systems).

**Browse it: <https://wangaruijie.github.io/EcomCrypt/>**

The directory is a static site with no backend. You can filter by topic, venue and year, browse by author or by paper, and download the whole dataset as [`site/data/directory.json`](site/data/directory.json).

> This is neither precise, nor comprehensive, and indeed suspicious. Corrections and missing papers are welcome through [issues](https://github.com/WANGaRuijie/EcomCrypt/issues).

## What is included

A paper belongs here when it has a genuine crossing of the two sides:

| Economic side | Technical side |
| --- | --- |
| Game theory, mechanism design, auctions, contracts | Blockchains, DeFi, smart contracts, consensus, MEV |
| Incentives, fees, pricing, collusion, governance | Cryptographic protocols, rational cryptography |
| Market microstructure, asset pricing, banking, monetary economics | Computer and network security, privacy, security games |
| OR/MS with strategic agents, information-systems economics | Distributed, parallel and database systems, formal methods, when the system itself is studied |

Papers on only one side are out, and so are papers that apply the crossing to an unrelated domain (for example, blockchain incentives for vehicular networks). Empirical work on the economic effects of these systems is in.

Papers come from a [registry of accepted venues](data/venue_registry_v1.json), plus the preprint and working-paper archives. Low-threshold and predatory outlets are denied in [`data/venue_policy_v2.json`](data/venue_policy_v2.json). The machine-readable criteria are in [`data/screening_rubric_v2.json`](data/screening_rubric_v2.json).

**Top venues only** limits the view to venues at or above the backbone of their field, as listed in [`data/venue_tiers_v1.json`](data/venue_tiers_v1.json). That list is a judgment call, not an official ranking.

## How it is built

```
sources ──> local memory ──> keyword gate ──> LLM on title ──> abstract recovery ──> LLM on abstract ──> bibliographic check ──> ledger ──> site
```

| Step | What happens |
| --- | --- |
| Sources | DBLP monthly snapshot, OpenAlex, arXiv, IACR ePrint |
| Memory | A local SQLite store merges records by DOI, arXiv ID, DBLP key, OpenAlex ID and normalized title, so a work is screened once per rubric version |
| Venue gate | Each venue is decided once: allowed, denied, preprint or unknown |
| Abstract recovery | OpenAlex, Semantic Scholar, arXiv, Crossref |
| Screening | A low-cost LLM applies the rubric, with a hard budget for each run |
| Verification | Authors, year and venue are checked against independent bibliographic sources before a paper is written |
| Ledger | [`data/accepted_updates_v1.json`](data/accepted_updates_v1.json) is append-only; removals and corrections apply at build time through policy files |

Waiting papers are processed best venues first, and SSRN is deferred for now.

## Repository layout

| Path | Contents |
| --- | --- |
| `site/` | The static website (plain HTML and ES modules) and the generated dataset |
| `scripts/` | Harvesting, screening, verification and build scripts (Python standard library) |
| `data/` | Venue registry and tiers, policies, rubric, taxonomy, ledger, editorial decisions |
| `tests/` | Unit tests for the pipeline and the catalog |

## Running it

Build and check the site:

```bash
python scripts/build.py build
python scripts/build.py check
python -m unittest discover -s tests
```

Preview it locally:

```bash
python -m http.server 8765 --directory site
```

The monthly pipeline runs on the maintainer's Windows machine through `scripts/monthly.ps1`, which loads locally encrypted API keys. Its screening memory is not part of this repository, so a fresh clone can rebuild the site but cannot resume the pipeline as it stands.

Changing a venue means editing `data/venue_registry_v1.json` and then running `python scripts/venues.py build`.

## Publishing

`.github/workflows/pages.yml` publishes `site/` to GitHub Pages when it is started by hand. No workflow runs on a schedule.

## License

See [LICENSE](LICENSE). Bibliographic records come from the sources above and remain subject to their terms.
