import { buildAuthorIndex, nameKey } from './authors.mjs';
import { venueFor } from './venues.mjs?v=ecomcrypt-6';

export function sortPapers(papers) {
  return [...papers].sort((a, b) => (b.year ?? 0) - (a.year ?? 0)
    || a.title.localeCompare(b.title, 'en', { sensitivity: 'base' })
    || a.id.localeCompare(b.id));
}

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
  const papers = sortPapers(dataset.papers.flatMap((work) => {
    const editions = (work.publications ?? []).map((publication) => ({
      ...publication, work_id: work.id, topic_ids: work.topic_ids, raw_input: work.raw_input,
      versions: [work, ...(work.versions ?? [])].filter((version) => version.doi !== publication.doi),
    }));
    return work.formal_publication || !editions.length ? [work, ...editions] : editions;
  }));
  const searchable = new Map(papers.map((paper) => {
    const authors = (paper.researcher_ids ?? []).map((id) => researchers.get(id)).filter(Boolean);
    const fields = [paper.title, paper.raw_input?.title, ...(paper.versions ?? []).map(v=>v.title),
      ...(paper.supplemental_seed_inputs ?? []).map(s=>s.title), paper.year, paper.accepted_venue, paper.venue, paper.doi, ...(paper.authors ?? []),
      ...authors.map((author) => author.name),
      ...(paper.topic_ids ?? []).map((id) => topics.get(id)?.name)];
    return [paper.id, fold(fields.join(' '))];
  }));

  const venues = new Map(papers.map((paper) => [paper.id, venueFor(paper)]));
  const catalog = { researchers, topics, papers, searchable, venues };
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
      if(!groups.get(key).papers.some(p=>p.id===paper.id))groups.get(key).papers.push(paper);
    }
  }
  return [...groups.values()].sort((a, b) =>
    Number(a.key === 'uncredited') - Number(b.key === 'uncredited')
    || b.papers.length - a.papers.length
    || a.name.localeCompare(b.name)
    || a.key.localeCompare(b.key));
}

function fold(value) {
  return String(value).normalize('NFKD').replace(/\p{Mark}/gu, '').toLowerCase()
    .replace(/[^\p{Letter}\p{Number}]+/gu, ' ').trim();
}

export function filterPapers(catalog, { query, topic, year, topics, venues, from, to }) {
  const terms = fold(query ?? '').split(' ').filter(Boolean);
  return catalog.papers.filter((paper) =>
    (!topic || (paper.topic_ids ?? []).includes(topic)) &&
    (topics == null || paper.topic_ids.some((id) => topics.has(id))) &&
    (venues == null || venues.has(catalog.venues.get(paper.id).label)) &&
    (from == null || (paper.year != null && paper.year >= from)) &&
    (to == null || (paper.year != null && paper.year <= to)) &&
    (!year || (year === 'unknown' ? paper.year == null : String(paper.year) === year)) &&
    terms.every((term) => catalog.searchable.get(paper.id).includes(term)));
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
