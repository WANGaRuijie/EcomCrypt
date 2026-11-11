import { registry } from './venue-registry.mjs?v=ecomcrypt-10';

export const PREPRINTS = 'Preprints & Working Papers';

// Lower is stronger: top venues, then other peer-reviewed venues, then preprints and unlisted records.
export function venueRank(venue) {
  return venue.top ? 0 : venue.group === PREPRINTS || venue.group === 'Unlisted' ? 2 : 1;
}

export function venueCaption(paper, venue) {
  if(venue.group!=='Interdisciplinary' || registry.some(v=>v.label===venue.label))return venue.display ?? venue.label;
  const shown = paper.venue?.replace(/\s*\((?:Workshops?\s*)?[AB]?\d+\)\s*$/i, '');
  const acronym = shown?.match(/\(([A-Z][A-Za-z0-9&/\-]{1,14})\)/)?.[1];
  return (acronym && !/^(?:Abstracts?|Posters?|Demos?|Workshops?|Supplements?|Companion)$/i.test(acronym) ? acronym : shown) ?? venue.label;
}

function normalize(value) {
  return (value ?? '').normalize('NFKD').replace(/\p{Mark}/gu, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

const groups = new Map();
for (const venue of registry) {
  if (!groups.has(venue.group)) groups.set(venue.group, []);
  groups.get(venue.group).push([venue.label]);
}
groups.set('Interdisciplinary', groups.get('Interdisciplinary') ?? []);
groups.set('Unlisted', [['Unlisted']]);
export const venueGroups = [...groups];

const names = registry.flatMap((venue) =>
  [venue.label, venue.name, ...venue.aliases].map((name) => ({
    name: normalize(name), group: venue.group, label: venue.label,
  })));

const dblpAliases = new Map([
  ['teac', 'TEAC'], ['sigecom', 'EC'], ['sp', 'IEEE S&P'], ['eurocrypt', 'EUROCRYPT'],
  ['crypto', 'CRYPTO'], ['fc', 'FC'], ['nsdi', 'NSDI'], ['jacm', 'JACM'],
]);

export function availableVenueGroups(venues) {
  const totals = new Map();
  const top = new Set(), display = new Map();
  for (const { label,group,top:isTop,display:shown } of venues.values()) {
    if(shown)display.set(label,shown);
    if(!totals.has(group))totals.set(group,new Map());
    const counts=totals.get(group);counts.set(label,(counts.get(label)??0)+1);
    if(isTop)top.add(label);
  }
  return venueGroups.map(([name]) => ({
    name,
    entries: [...(totals.get(name)??[])].map(([label,count])=>({label,count,top:top.has(label),display:display.get(label)}))
      .sort((a,b)=>Number(b.top)-Number(a.top)||(a.display??a.label).localeCompare(b.display??b.label)),
  })).filter((group) => group.entries.length);
}

export function venueFor(paper) {
  if (!paper.accepted_venue && (paper.kind === 'preprint' || /(?:arxiv|ssrn|eprint)/i.test(paper.venue ?? '')
      || /^10\.48550\/arxiv\./i.test(paper.doi ?? ''))) {
    if (paper.venue_tag?.group === PREPRINTS) return paper.venue_tag;
    const repository = /^10\.48550\/arxiv\./i.test(paper.doi ?? '') || /arxiv/i.test(paper.venue ?? '') ? 'arXiv'
      : /ssrn/i.test(paper.venue ?? '') ? 'SSRN' : /eprint/i.test(paper.venue ?? '') ? 'IACR ePrint' : 'Other preprints';
    return { group: PREPRINTS, label: repository };
  }
  if (paper.venue_tag) return paper.venue_tag;       // set by scripts/build.py from the screening matcher
  const text = normalize(paper.accepted_venue ?? paper.venue);
  if (!('venue_tag' in paper)) {
    const withoutYear = text.replace(/ \d{4}$/, '');
    const exact = names.find(({ name }) => name === text || name === withoutYear);
    if (exact) return { group: exact.group, label: exact.label };

    // A full journal name outranks a shorter phrase shared with a conference.
    const matching = names.filter(({ name }) =>
      name.includes(' ') && (' ' + text + ' ').includes(' ' + name + ' '));
    matching.sort((a, b) => b.name.length - a.name.length);
    if (matching.length) return { group: matching[0].group, label: matching[0].label };

    // Explicit parenthesized venue abbreviations survive publisher prefixes and
    // ordinal conference names; do not match short labels inside arbitrary words.
    const original = paper.accepted_venue ?? paper.venue ?? '';
    for (const match of original.matchAll(/\(([^()]+)\)/g)) {
      const abbreviation = normalize(match[1]).replace(/ \d{2,4}$/, '');
      const entry = names.find(({ name }) => name === abbreviation);
      if (entry) return { group: entry.group, label: entry.label };
    }
  }

  const key = paper.source_ids?.dblp?.split('/')[1];
  const label = dblpAliases.get(key);
  const fallback = registry.find((venue) => venue.label === label);
  if (fallback && (!text || text === 'lecture notes in computer science')) {
    return { group: fallback.group, label: fallback.label };
  }
  return { group: text ? 'Interdisciplinary' : 'Unlisted', label: text ? (paper.accepted_venue ?? paper.venue) : 'Unlisted' };
}
