import { buildAuthorIndex, nameKey } from './authors.mjs';
import { venueFor, venueRank } from './venues.mjs?v=ecomcrypt-10';

export function sortPapers(papers) {
  const rank = new Map(papers.map((paper) => [paper, venueRank(venueFor(paper))]));
  return [...papers].sort((a, b) => (b.year ?? 0) - (a.year ?? 0)
    || rank.get(a) - rank.get(b)
    || a.title.localeCompare(b.title, 'en', { sensitivity: 'base' })
    || a.id.localeCompare(b.id));
}

export const editionsOf = (paper) => [paper, ...(paper.also ?? [])];
export const UNKNOWN_AFFILIATION = 'Affiliation unknown';

export function makeCatalog(dataset) {
  const groups = ['topics', 'institutions', 'researchers', 'papers'];
  if (dataset?.schema_version !== 1 || groups.some((group) => !Array.isArray(dataset[group]))) {
    throw new Error('Unexpected directory format');
  }
  const researchers = new Map(dataset.researchers.map((researcher) => [researcher.id, researcher]));
  for (const group of dataset.author_display_aliases ?? []) {
    const canonical=researchers.get(group.canonical_id);
    if(canonical) for(const id of group.ids) if(researchers.has(id)) researchers.set(id,canonical);
  }
  const topics = new Map(dataset.topics.map((topic) => [topic.id, topic]));
  // One row per work: the strongest edition leads and the others stay attached to it.
  const editionOrder = (a, b) => venueRank(venueFor(a)) - venueRank(venueFor(b))
    || Number(/abstract/i.test(a.kind ?? '')) - Number(/abstract/i.test(b.kind ?? ''))
    || (b.year ?? 0) - (a.year ?? 0);
  const papers = sortPapers(dataset.papers.map((work) => {
    const editions = (work.publications ?? []).map((publication) => ({
      ...publication, work_id: work.id, topic_ids: work.topic_ids, raw_input: work.raw_input,
      versions: [work, ...(work.versions ?? [])].filter((version) => version.doi !== publication.doi),
    }));
    const [lead, ...also] = (work.formal_publication || !editions.length ? [work, ...editions] : editions).sort(editionOrder);
    return also.length ? { ...lead, also } : lead;
  }));
  const searchable = new Map(papers.map((paper) => {
    const authors = (paper.researcher_ids ?? []).map((id) => researchers.get(id)).filter(Boolean);
    const fields = [paper.title, paper.raw_input?.title, ...(paper.versions ?? []).map(v=>v.title),
      ...(paper.also ?? []).flatMap(e=>[e.title,e.venue,e.accepted_venue,e.year,e.doi,e.venue_tag?.display]), paper.venue_tag?.display,
      ...(paper.supplemental_seed_inputs ?? []).map(s=>s.title), paper.year, paper.accepted_venue, paper.venue, paper.doi, ...(paper.authors ?? []),
      ...authors.map((author) => author.name),
      ...(paper.topic_ids ?? []).map((id) => topics.get(id)?.name)];
    return [paper.id, fold(fields.join(' '))];
  }));

  const venues = new Map(papers.map((paper) => [paper.id, venueFor(paper)]));
  const editionVenues = new Map(papers.flatMap(editionsOf).map((paper) => [paper.id, venueFor(paper)]));
  const words = new Set([...searchable.values()].flatMap((text) => text.split(' ')).filter((word) => word.length > 2 && !/\d/.test(word)));
  const joined = new Map([...searchable].map(([id, text]) => [id, text.replaceAll(' ', '')]));
  const catalog = { researchers, topics, papers, searchable, joined, words, spelling: new Map(), venues, editionVenues };
  catalog.authorIndex=buildAuthorIndex(catalog);
  return catalog;
}

export function groupAuthorPapers(catalog, papers) {
  const groups = new Map();
  const index=catalog.authorIndex ?? buildAuthorIndex({...catalog,papers:catalog.papers ?? papers});
  for(const paper of papers) {
    const credits=paper.author_credits?.length ? paper.author_credits : [{name:'Author unavailable'}];
    const seen=new Set();
    for(const credit of credits) {
      const key=paper.author_credits?.length ? index.byName.get(nameKey(credit.name)) : 'uncredited';
      if(!key || seen.has(key))continue;
      seen.add(key);
      const person=index.people.get(key);
      if(!groups.has(key))groups.set(key,{key,name:person?.name ?? credit.name,papers:[],aliases:person?.aliases ?? [],sourceIds:person?.sourceIds ?? []});
      groups.get(key).papers.push(paper);   // `seen` already keeps one entry per paper and author
    }
  }
  const atRank = (group, rank) => group.papers.filter((paper) => venueRank(catalog.venues.get(paper.id)) <= rank).length;
  return [...groups.values()].sort((a, b) =>
    Number(a.key === 'uncredited') - Number(b.key === 'uncredited')
    || atRank(b, 0) - atRank(a, 0)
    || atRank(b, 1) - atRank(a, 1)
    || b.papers.length - a.papers.length
    || a.name.localeCompare(b.name)
    || a.key.localeCompare(b.key));
}

// Affiliation -> author -> paper, ranked by distinct papers (a paper counts once per affiliation).
export function groupAffiliationPapers(catalog, papers, affiliationOf) {
  const groups = new Map();
  for (const author of groupAuthorPapers(catalog, papers)) {
    if (author.key === 'uncredited') continue;
    const name = affiliationOf.get(author.key) ?? UNKNOWN_AFFILIATION;
    if (!groups.has(name)) groups.set(name, { name, ids: new Set(), authors: [] });
    const group = groups.get(name);
    group.authors.push(author);
    for (const paper of author.papers) group.ids.add(paper.id);
  }
  return [...groups.values()].sort((a, b) =>
    Number(a.name === UNKNOWN_AFFILIATION) - Number(b.name === UNKNOWN_AFFILIATION)
    || b.ids.size - a.ids.size || a.name.localeCompare(b.name));
}

// Each facet ignores its own selection, so a number says what ticking that box would show.
// years feeds the histogram above the year slider: every filter except the years themselves.
export function facetCounts(catalog, filters) {
  const counts = { top: 0, years: new Map(), topics: new Map(), topicGroups: new Map(), venues: new Map(), venueGroups: new Map() };
  const bump = (map, key) => map.set(key, (map.get(key) ?? 0) + 1);
  const venuesOf = (editions) => editions.map((edition) => catalog.editionVenues.get(edition.id));
  const chosen = (editions) => filters.venues == null || venuesOf(editions).some((venue) => filters.venues.has(venue.label));
  for (const paper of filterPapers(catalog, { ...filters, topics: null, venues: null, topOnly: false, from: null, to: null })) {
    const topEditions = shownEditions(catalog, paper, true);
    const editions = filters.topOnly ? topEditions : editionsOf(paper);
    const inTopics = filters.topics == null || paper.topic_ids.some((id) => filters.topics.has(id));
    if (topEditions.length && inTopics && chosen(topEditions) && inYears(topEditions, filters.from, filters.to)) counts.top += 1;
    if (!editions.length) continue;
    const inVenues = chosen(editions);
    if (inTopics && inVenues && editions[0].year != null) bump(counts.years, editions[0].year);
    if (!inYears(editions, filters.from, filters.to)) continue;
    if (inVenues) {
      for (const id of paper.topic_ids) bump(counts.topics, id);
      for (const group of new Set(paper.topic_ids.map((id) => catalog.topics.get(id)?.group ?? 'Topics'))) bump(counts.topicGroups, group);
    }
    if (inTopics) {
      for (const label of new Set(venuesOf(editions).map((venue) => venue.label))) bump(counts.venues, label);
      for (const group of new Set(venuesOf(editions).map((venue) => venue.group))) bump(counts.venueGroups, group);
    }
  }
  return counts;
}

function fold(value) {
  return String(value).normalize('NFKD').replace(/\p{Mark}/gu, '').toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, ' ').trim();
}

// Optimal string alignment distance, abandoned as soon as it must exceed the limit.
function editDistance(a, b, limit) {
  if (Math.abs(a.length - b.length) > limit) return limit + 1;
  let before = null;
  let previous = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    let lowest = i;
    for (let j = 1; j <= b.length; j += 1) {
      let cost = Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + Number(a[i - 1] !== b[j - 1]));
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) cost = Math.min(cost, before[j - 2] + 1);
      current[j] = cost;
      lowest = Math.min(lowest, cost);
    }
    if (lowest > limit) return limit + 1;
    before = previous;
    previous = current;
  }
  return previous[b.length];
}

// Spelling tolerance applies only to a term that appears nowhere in the directory, so correct terms stay exact.
function closestWords(catalog, term) {
  if (catalog.spelling.has(term)) return catalog.spelling.get(term);
  const allowed = /\d/.test(term) || term.length < 4 ? 0 : term.length < 8 ? 1 : 2;
  let closest = [];
  if (allowed && ![...catalog.joined.values()].some((text) => text.includes(term))) {
    let best = allowed + 1;
    for (const word of catalog.words) {
      const distance = Math.min(editDistance(term, word, allowed),
        word.length > term.length ? editDistance(term, word.slice(0, term.length), allowed) : allowed + 1);
      if (distance > allowed || distance > best) continue;
      if (distance < best) closest = [];
      best = distance;
      closest.push(word);
    }
  }
  catalog.spelling.set(term, closest);
  return closest;
}

export function spellingMatches(catalog, query) {
  return fold(query ?? '').split(' ').filter(Boolean).flatMap((term) => closestWords(catalog, term));
}

// The editions a reader sees: with Top venues only, a paper's non-top versions drop out of tags, counts and filters.
export function shownEditions(catalog, paper, topOnly) {
  const editions = editionsOf(paper);
  return topOnly ? editions.filter((edition) => catalog.editionVenues.get(edition.id).top) : editions;
}

function inYears(editions, from, to) {
  return from == null || to == null || editions.some((edition) => edition.year != null && edition.year >= from && edition.year <= to);
}

export function filterPapers(catalog, { query, topic, year, topics, venues, from, to, topOnly }) {
  const terms = fold(query ?? '').split(' ').filter(Boolean).map((term) => ({ term, closest: closestWords(catalog, term) }));
  return catalog.papers.filter((paper) => {
    const editions = shownEditions(catalog, paper, topOnly);
    return editions.length > 0 &&
      (!topic || (paper.topic_ids ?? []).includes(topic)) &&
      (topics == null || paper.topic_ids.some((id) => topics.has(id))) &&
      (venues == null || editions.some((edition) => venues.has(catalog.editionVenues.get(edition.id).label))) &&
      inYears(editions, from, to) &&
      (!year || (year === 'unknown' ? paper.year == null : String(paper.year) === year)) &&
      terms.every(({ term, closest }) => catalog.searchable.get(paper.id).includes(term)
        || catalog.joined.get(paper.id).includes(term)
        || closest.some((word) => catalog.searchable.get(paper.id).includes(word)));
  });
}

export function authorFromHash(hash) {
  const match = hash.match(/^#\/(?:author|(?:institution\/[^/]+|unlinked)\/researcher)\/([^/]+)$/);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function safeWebUrl(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}
