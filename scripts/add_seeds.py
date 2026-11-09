"""Resolve supplemental user seeds without guessing absent bibliographic fields."""
from pathlib import Path
from directory import read_json, write_json
from metadata import MetadataClient
from metadata import normalize_title

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'data/additional_seeds_v1.json'

def main():
    data = read_json(PATH)
    client = MetadataClient(ROOT / '.cache/additional-seeds')
    graph = ROOT / '.out/expanded-scope/seed-preprints.json'
    observed = [source for node in read_json(graph)['nodes'] for source in node['sources']] if graph.exists() else []
    for row in data['records']:
        if row.get('verification', {}).get('metadata'):
            continue
        seed = row['raw_input']
        query = {**seed, 'title': row.get('query_title', seed['title'].replace('{', '').replace('}', ''))}
        matching = [record for record in observed if normalize_title(record['title']) == normalize_title(query['title'])]
        row['verification'] = client.verify(query, observed=matching)
        write_json(PATH, data)
        print(seed['title'], row['verification']['status'], flush=True)

if __name__ == '__main__':
    main()
