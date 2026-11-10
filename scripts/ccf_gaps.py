"""List CCF-recommended venues that are not registered, with how many on-topic papers wait at each.

CCF is a reference, not a rule: read the report and judge each venue. A CCF entry carries a DBLP
address, so it is matched against the local store by DBLP key instead of by name.

    python scripts/ccf_gaps.py "path/to/The List Recommended by CCF.pdf"
"""
import argparse
import re
import sqlite3
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / '.cache/pipeline/store.sqlite'
REPORT = ROOT / '.out/ccf-gaps.md'
ADDRESS = re.compile(r'dblp\.(?:uni-trier\.de|org)/db/(journals|conf)/([\w-]+)')
ECONOMIC = re.compile(r'\b(incentiv|game[- ]theor|mechanism design|auction|equilibri|nash|stackelberg|rational (?:adversar|agent|player|miner)|selfish|strategic|collusion|brib|tokenomics|economic|market|pricing|fee mechanism|reward)', re.I)
TECHNICAL = re.compile(r'\b(blockchain|bitcoin|ethereum|cryptocurrenc|crypto[- ]?asset|smart contract|defi\b|decentrali[sz]ed finance|staking|proof[- ]of[- ](?:stake|work)|consensus|mining pool|miner|mev\b|stablecoin|automated market maker|rollup|attacker|attack|adversar|security game|cyber|multiparty computation)', re.I)


def parse(pdf):
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder) / 'ccf.txt'
        subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(pdf), str(out)], check=True)
        lines = out.read_text(encoding='utf-8').splitlines()
    entries, rank = {}, None
    for line in lines:
        found = re.search(r'Class ([ABC])', line)
        if found:
            rank = found.group(1)
        found = ADDRESS.search(line)
        if found:
            columns = [c for c in re.split(r'\s{2,}', line[:found.start()].rsplit('http', 1)[0].strip()) if c and not c.isdigit()]
            entries.setdefault(f'{found.group(1)}/{found.group(2)}', {'rank': rank, 'abbr': columns[0] if columns else ''})
    return entries


def local_counts():
    db = sqlite3.connect(f'file:{STORE.as_posix()}?mode=ro', uri=True, timeout=60)
    counts, examples, names = defaultdict(Counter), defaultdict(list), defaultdict(Counter)
    for alias, status, title, venue in db.execute("SELECT a.alias, w.status, w.title, w.venue FROM aliases a JOIN works w ON w.key = a.key WHERE a.alias LIKE 'dblp:%'"):
        parts = alias[5:].split('/')
        if len(parts) < 2:
            continue
        key = f'{parts[0]}/{parts[1]}'
        waiting = status == 'venue_unknown'
        counts[key]['waiting' if waiting else 'past_gate'] += 1
        if waiting:
            names[key][venue] += 1
            if ECONOMIC.search(title) and TECHNICAL.search(title):
                counts[key]['crossing'] += 1
                if len(examples[key]) < 2:
                    examples[key].append(title[:80])
    return counts, examples, names


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pdf')
    args = parser.parse_args()
    entries = parse(args.pdf)
    counts, examples, names = local_counts()
    rows = [(key, entry, counts[key]) for key, entry in entries.items() if counts[key]['waiting'] > counts[key]['past_gate']]
    rows.sort(key=lambda row: (row[1]['rank'], -row[2]['crossing'], row[0]))
    lines = ['# CCF venues not registered', '', f'{len(entries)} CCF entries; {len(rows)} have local records still parked as unknown venues.', '',
             '| CCF | DBLP key | Name in DBLP | Crossing titles | Records waiting | Examples |', '| --- | --- | --- | ---: | ---: | --- |']
    for key, entry, count in rows:
        name = names[key].most_common(1)[0][0] if names[key] else entry['abbr']
        sample = ' / '.join(examples[key]).replace('|', ' ')
        lines.append(f"| {entry['rank']} | {key} | {name} | {count['crossing']} | {count['waiting']} | {sample} |")
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(rows)} unregistered CCF venues with local records -> {REPORT}')


if __name__ == '__main__':
    main()
