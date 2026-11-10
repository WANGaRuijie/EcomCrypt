"""Find works listed twice in the built directory. Run before every push.

A retitled preprint shares neither DOI nor title with its published version, so authors are
compared together with the title and the abstract. Each candidate needs a decision in
data/work_merges_v1.json: "merges" folds two works into one at build time, "distinct" records
that a person looked and they are different papers. `check` fails while a candidate is undecided.
"""
import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'site/data/directory.json'
DECISIONS = ROOT / 'data/work_merges_v1.json'
STORE = ROOT / '.cache/pipeline/store.sqlite'
TITLE_STOP = {'a', 'an', 'the', 'of', 'on', 'in', 'for', 'and', 'to', 'with', 'via', 'at', 'by', 'from', 'is', 'are', 'towards', 'toward'}
TEXT_STOP = TITLE_STOP | {'we', 'that', 'this', 'as', 'be', 'can', 'it', 'which', 'these', 'our', 'their', 'show', 'paper'}
SAME_AUTHORS, SAME_TITLE, CONTAINED_TITLE, SAME_ABSTRACT = 0.6, 0.6, 0.85, 0.42


def normal(text):
    return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', text or '').lower()).strip()


def title_words(title):
    return {word.rstrip('s') for word in normal(title).split() if word not in TITLE_STOP}


def text_words(text):
    return {word for word in normal(text).split() if word not in TEXT_STOP and len(word) > 2}


def families(names):
    return {name.split()[-1].lower() for name in names or [] if name.split()}


def overlap(a, b):
    return len(a & b) / min(len(a), len(b)) if a and b else 0


def similarity(a, b):
    return len(a & b) / len(a | b) if a and b else 0


def abstracts():
    if not STORE.exists():
        return {}
    db = sqlite3.connect(f'file:{STORE.as_posix()}?mode=ro', uri=True, timeout=60)
    found = {}
    for title, text in db.execute('SELECT title, abstract FROM works WHERE length(abstract) > 200'):
        found.setdefault(normal(title), text)
    return found


def candidates(papers, abstract_of):
    """Return {(id, id): reason} for pairs that look like one paper."""
    pairs, rows, by_identifier = {}, [], defaultdict(set)
    for paper in papers:
        text = abstract_of.get(normal(paper.get('title')))
        rows.append((paper['id'], title_words(paper.get('title')), families(paper.get('authors')), text_words(text)))
        for edition in [paper, *paper.get('versions', []), *paper.get('publications', [])]:
            if edition.get('doi'):
                by_identifier[edition['doi'].lower()].add(paper['id'])
            if len(normal(edition.get('title'))) > 25:
                by_identifier[normal(edition['title'])].add(paper['id'])
    for identifier, ids in by_identifier.items():
        for a, b in combinations(sorted(ids), 2):
            pairs[(a, b)] = f'shared identifier or title: {identifier[:60]}'
    by_family = defaultdict(set)
    for index, (_, _, names, _) in enumerate(rows):
        for family in names:
            by_family[family].add(index)
    compared = set()
    for indices in by_family.values():
        for i, j in combinations(sorted(indices), 2):
            if (i, j) in compared:
                continue
            compared.add((i, j))
            (a, words_a, names_a, text_a), (b, words_b, names_b, text_b) = rows[i], rows[j]
            if overlap(names_a, names_b) < SAME_AUTHORS:
                continue
            short = min(len(words_a), len(words_b))
            titled = short >= 3 and (similarity(words_a, words_b) >= SAME_TITLE or overlap(words_a, words_b) >= CONTAINED_TITLE)
            worded = similarity(text_a, text_b)
            if titled or worded >= SAME_ABSTRACT:
                pairs.setdefault(tuple(sorted((a, b))), f'same authors; title {similarity(words_a, words_b):.2f}, abstract {worded:.2f}')
    return pairs


def undecided(pairs, decisions):
    known = {tuple(sorted(row['ids'])) for row in decisions.get('distinct', [])}
    return {pair: why for pair, why in pairs.items() if pair not in known}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('report', 'check'))
    args = parser.parse_args()
    papers = json.loads(DIRECTORY.read_text(encoding='utf-8'))['papers']
    decisions = json.loads(DECISIONS.read_text(encoding='utf-8'))
    open_pairs = undecided(candidates(papers, abstracts()), decisions)
    titles = {paper['id']: f"{paper.get('year')} {(paper.get('venue_tag') or {}).get('label')} | {(paper.get('title') or '')[:80]}" for paper in papers}
    for (a, b), why in sorted(open_pairs.items()):
        print(f'{a}\n  {titles[a]}\n{b}\n  {titles[b]}\n  -> {why}\n')
    print(f'{len(open_pairs)} undecided duplicate candidates among {len(papers)} works')
    if args.mode == 'check' and open_pairs:
        print('Decide each pair in data/work_merges_v1.json, then run python scripts/build.py build.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
