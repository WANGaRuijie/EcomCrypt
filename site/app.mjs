import { authorFromHash, facetCounts, shownEditions, filterPapers, groupAffiliationPapers, groupAuthorPapers, makeCatalog, safeWebUrl, spellingMatches, UNKNOWN_AFFILIATION } from './catalog.mjs?v=ecomcrypt-10';
import { availableVenueGroups, PREPRINTS, venueCaption } from './venues.mjs?v=ecomcrypt-10';

const byId = (id) => document.getElementById(id);
const form = byId('filters');
const results = byId('results');
const expanded = new Set();
const cells = { years: new Map(), topics: new Map(), topicGroups: new Map(), venues: new Map(), venueGroups: new Map() };
let listTimer = 0;
let frame = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function link(label, href) {
  const node = element('a', label);
  node.href = href;
  return node;
}

function paperUrl(record) {
  const doi = typeof record.doi === 'string' && /^10\.\d{4,9}\/\S+$/.test(record.doi)
    ? `https://doi.org/${record.doi.split('/').map(encodeURIComponent).join('/')}`
    : null;
  return safeWebUrl(record.url) ?? doi;
}

function sourceUrl(source, identifier) {
  if (typeof identifier !== 'string') return null;
  const url = safeWebUrl(identifier);
  if (url) return url;
  if (source === 'openalex' && /^W\d+$/.test(identifier)) return `https://openalex.org/${identifier}`;
  if (source === 'arxiv' && /^(?:\d{4}\.\d{4,5}|[a-z-]+\/\d{7})$/.test(identifier)) return `https://arxiv.org/abs/${identifier}`;
  if (source === 'dblp' && /^(?:journals|conf|books|reference|series|tr)\/[\w./-]+$/.test(identifier)) {
    return `https://dblp.org/rec/${identifier.split('/').map(encodeURIComponent).join('/')}.html`;
  }
  if (source === 'crossref') return paperUrl({ doi: identifier });
  return null;
}

function recordDetails(paper) {
  const raw = paper.raw_input;
  const versions = [...(paper.also ?? []), ...(paper.versions ?? [])];
  const sources = Object.entries(paper.source_ids ?? {}).filter(([, value]) => value);
  const primarySources = paper.primary_sources ?? [];
  if (!raw && !versions.length && !sources.length && !paper.doi) return null;

  const details = element('details', null, 'record-details');
  details.append(element('summary', 'Record details'));
  // The body is built on first open: most rows are never expanded, and thousands of hidden subtrees slow every redraw.
  details.addEventListener('toggle', () => { if (details.open && details.childElementCount === 1) fillDetails(details, paper, raw, versions, sources, primarySources); });
  return details;
}

function fillDetails(details, paper, raw, versions, sources, primarySources) {
  if(paper.inclusion_note)details.append(element('p',paper.inclusion_note));
  if (paper.doi) details.append(element('p', `DOI ${paper.doi}`));
  if(paper.accepted_venue) {
    const evidence=safeWebUrl(paper.acceptance_source);
    const line=element('p', `Accepted at ${paper.accepted_venue}. Proceedings metadata pending. `);
    if(evidence) line.append(link('Acceptance evidence',evidence));
    details.append(line);
  }
  const venueSource = safeWebUrl(paper.venue_source);
  if (venueSource) details.append(link('Proceedings record', venueSource));
  for (const [label, value] of [['Version link evidence', paper.relation_source], ['Earlier version evidence', paper.earlier_version_evidence]]) {
    const url = safeWebUrl(value);
    if (url) {
      const line = element('p');
      line.append(link(label, url));
      details.append(line);
    }
  }
  if (sources.length) {
    const labels = { openalex: 'OpenAlex', dblp: 'DBLP', crossref: 'Crossref' };
    const sourcesList = element('ul');
    for (const [source, value] of sources) {
      for (const identifier of [value].flat()) {
        if (typeof identifier !== 'string' || !identifier) continue;
        const sourceItem = element('li');
        const label = `${labels[source] ?? source} · ${identifier}`;
        const url = sourceUrl(source, identifier);
        sourceItem.append(url ? link(label, url) : element('span', label));
        sourcesList.append(sourceItem);
      }
    }
    if (sourcesList.childElementCount) details.append(element('p', 'Source records'), sourcesList);
  }
  if (primarySources.length) {
    const list = element('ul');
    for (const record of primarySources) {
      const url = safeWebUrl(record.url);
      if (!url) continue;
      const row = element('li');
      row.append(link(record.locator || record.source, url));
      list.append(row);
    }
    if (list.childElementCount) details.append(element('p', 'Primary evidence'), list);
  }
  if (versions.length) {
    const versionList = element('ul');
    for (const version of versions) {
      const row = element('li');
      const label = [version.title, version.venue, version.year, version.kind].filter(Boolean).join(' · ');
      const url = paperUrl(version);
      row.append(url ? link(label || 'Source version', url) : element('span', label || 'Source version'));
      versionList.append(row);
    }
    details.append(element('p', 'Linked versions'), versionList);
  }
}

function treeRow(label, count, key, children) {
  const node = element('details', null, 'tree-row');
  node.open = expanded.has(key);
  const summary = element('summary');
  summary.append(element('span', label), element('span', count, 'count'));
  node.append(summary);
  let built = false;
  function populate() {
    if (!built && node.open) {
      node.append(children());
      built = true;
    }
  }
  populate();
  node.addEventListener('toggle', () => {
    if (node.open) expanded.add(key);
    else expanded.delete(key);
    populate();
  });
  return node;
}

const FIRST_ROWS = 120;
const MORE_ROWS = 200;

// Long lists are drawn in slices: the first rows at once, the next slice when the reader scrolls near the end.
function paperList(catalog, papers) {
  const list = element('ul', null, 'papers');
  let drawn = 0;
  const sentinel = element('li', null, 'more-rows');
  const observer = 'IntersectionObserver' in window
    ? new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) more(MORE_ROWS); }, { rootMargin: '1200px 0px' })
    : null;
  function more(count) {
    sentinel.remove();
    const slice = papers.slice(drawn, drawn + count);
    drawn += slice.length;
    list.append(...slice.map((paper) => paperRow(catalog, paper)));
    if (drawn < papers.length) {
      sentinel.textContent = (papers.length - drawn) + ' more records';
      list.append(sentinel);
      if (observer) observer.observe(sentinel);
      else more(papers.length);
    } else if (observer) observer.disconnect();
  }
  sentinel.addEventListener('click', () => more(MORE_ROWS));
  more(FIRST_ROWS);
  return list;
}

function paperRow(catalog, paper) {
  {
    const row = element('li', null, 'paper');
    const title = element('div', null, 'paper-title');
    const url = paperUrl(paper);
    title.append(url ? link(paper.title, url) : element('span', paper.title));
    if (paper.year != null) title.append(element('span', paper.year, 'year'));
    row.append(title);
    if (paper.authors?.length) row.append(element('div', paper.authors.join(', '), 'byline'));
    const tags = element('div', null, 'tags');
    for (const id of paper.topic_ids) {
      const tag = element('span', catalog.topics.get(id)?.name ?? id, 'tag topic-tag');
      tags.append(tag);
    }
    const shown = new Set();
    for (const edition of shownEditions(catalog, paper, byId('top-only').checked)) {
      const venue = catalog.editionVenues.get(edition.id);
      if ((!edition.venue && venue.label === 'Unlisted') || shown.has(venue.label)) continue;
      shown.add(venue.label);
      const tag = element('span', venueCaption(edition,venue), 'tag venue-tag' + (venue.group === PREPRINTS ? ' preprint-tag' : venue.top ? ' top-tag' : ''));
      tag.title = edition.accepted_venue ?? edition.venue ?? venue.label;
      tags.append(tag);
    }
    const details = recordDetails(paper);
    if (details) tags.append(details);
    row.append(tags);
    return row;
  }
}

function checkbox(container, name, value, caption, total) {
  const label = element('label', null, 'choice');
  const input = element('input');
  input.type = 'checkbox';
  input.name = name;
  input.value = value;
  input.defaultChecked = true;
  input.checked = true;
  label.append(input, element('span', caption), element('small', total));
  container.append(label);
  return input;
}

function selected(name) {
  return new Set(new FormData(form).getAll(name));
}

function selectionActions(kind,scope) {
  const box=element('div',null,'selection-actions');
  for(const [caption,checked] of [['Select All',true],['Deselect All',false]]) {
    const button=element('button',caption);button.type='button';
    button.dataset.selection=kind;button.dataset.checked=String(checked);button.dataset.scope=scope;
    box.append(button);
  }
  return box;
}

function showCounts(catalog, filters) {
  const counts = facetCounts(catalog, filters);
  const put = (cell, value) => {
    const text = String(value ?? 0);
    if (cell.textContent !== text) cell.textContent = text;
    cell.closest('.choice')?.classList.toggle('zero', !value);
  };
  put(byId('top-count'), counts.top);
  const tallest = Math.max(1, ...counts.years.values());
  const [from, to] = [Number(byId('from').value), Number(byId('to').value)];
  for (const [year, bar] of cells.years) {
    const value = counts.years.get(year) ?? 0;
    bar.style.height = (value ? Math.max(4, value / tallest * 100) : 0) + '%';
    bar.classList.toggle('outside', year < from || year > to);
    bar.title = year + ': ' + value;
  }
  for (const [family, map] of [['topics', cells.topics], ['topicGroups', cells.topicGroups], ['venues', cells.venues], ['venueGroups', cells.venueGroups]]) {
    for (const [key, cell] of map) put(cell, counts[family].get(key));
  }
}

function affiliationTree(catalog, papers) {
  const groups = groupAffiliationPapers(catalog, papers, catalog.affiliationOf);
  const note = element('p', 'Current affiliation where known, otherwise the institution on the most recent byline. Inferred automatically and may be out of date.', 'affiliation-note');
  const rows = groups.map(({ name, ids, authors }, index) => {
    const row = treeRow(name, ids.size, 'affiliation:' + name, () => {
      const list = element('div', null, 'papers');
      list.append(...authors.map((author) => treeRow(author.name, author.papers.length, 'affiliation:' + name + ':' + author.key, () => paperList(catalog, author.papers))));
      return list;
    });
    if (name !== UNKNOWN_AFFILIATION) row.querySelector('summary').prepend(element('span', index + 1, 'rank'));
    return row;
  });
  return { rows: [note, ...rows], count: groups.filter(({ name }) => name !== UNKNOWN_AFFILIATION).length };
}

function drawResults(catalog, papers, authors) {
  const mode = byId('browse-mode').value;
  const none = element('p', 'No papers match these filters.', 'empty');
  if (mode === 'paper') {
    results.replaceChildren(papers.length ? paperList(catalog, papers) : none);
  } else if (mode === 'affiliation') {
    results.replaceChildren(...(papers.length ? affiliationTree(catalog, papers).rows : [none]));
  } else {
    results.replaceChildren(...(authors.length ? authors.map(({ key, name, papers: records }) =>
      treeRow(name, records.length, key, () => paperList(catalog, records))) : [none]));
  }
}

function render(catalog, { deferList = false } = {}) {
  for (const button of document.querySelectorAll('[data-view]')) button.setAttribute('aria-pressed', String(button.dataset.view === byId('browse-mode').value));
  const start = byId('from');
  const end = byId('to');
  byId('from-value').value = start.value;
  byId('to-value').value = end.value;
  const span = Number(start.max) - Number(start.min) || 1;
  byId('year-range').style.setProperty('--start', ((Number(start.value) - Number(start.min)) / span * 100) + '%');
  byId('year-range').style.setProperty('--end', ((Number(end.value) - Number(start.min)) / span * 100) + '%');
  start.style.zIndex = start.value === start.max ? '3' : '1';
  start.setAttribute('aria-valuetext', 'From ' + start.value);
  end.setAttribute('aria-valuetext', 'Through ' + end.value);
  const filters = {
    query: byId('search').value,
    topics: selected('topic'),
    venues: selected('venue'),
    from: start.value === start.min && end.value === end.max ? null : Number(start.value),
    to: start.value === start.min && end.value === end.max ? null : Number(end.value),
    topOnly: byId('top-only').checked,
  };
  const papers = filterPapers(catalog, filters);
  showCounts(catalog, filters);
  const rows = groupAuthorPapers(catalog, papers);
  const authorCount = rows.filter(({ key }) => key !== 'uncredited').length;
  const closest = spellingMatches(catalog, byId('search').value);
  byId('result-summary').textContent = papers.length + ' records · ' + authorCount + ' authors'
    + (closest.length ? ' · closest match: ' + closest.slice(0, 4).join(', ') : '');
  clearTimeout(listTimer);
  if (deferList) listTimer = setTimeout(() => drawResults(catalog, papers, rows), 140);   // numbers follow a dragged slider at once, the long list when it pauses
  else drawResults(catalog, papers, rows);
}

async function load() {
  // catalog.json is the slim build of directory.json. no-cache revalidates (304 when unchanged) instead of re-downloading.
  const response = await fetch(new URL('./data/catalog.json', import.meta.url), { cache: 'no-cache' });
  if (!response.ok) throw new Error('Directory request failed');
  const catalog = makeCatalog(await response.json());
  catalog.affiliationOf = new Map();
  const affiliationData = await fetch(new URL('./data/affiliations.json', import.meta.url), { cache: 'no-cache' }).then((reply) => (reply.ok ? reply.json() : {})).catch(() => ({}));
  for (const [key, affiliation] of Object.entries(affiliationData)) {
    const person = catalog.authorIndex.byName.get(key);
    if (person && !catalog.affiliationOf.has(person)) catalog.affiliationOf.set(person, affiliation);
  }
  const requested = new URLSearchParams(location.search).get('view');
  if (['paper', 'author', 'affiliation'].includes(requested)) byId('browse-mode').value = requested;
  if (authorFromHash(location.hash)) byId('browse-mode').value = 'author';
  byId('browse-mode').addEventListener('change', () => {
    const url = new URL(location.href);
    url.searchParams.set('view', byId('browse-mode').value);
    history.replaceState(null, '', url);
    render(catalog);
  });
  for (const button of document.querySelectorAll('[data-view]')) button.addEventListener('click', () => {
    byId('browse-mode').value = button.dataset.view;
    byId('browse-mode').dispatchEvent(new Event('change'));
  });
  const years = catalog.papers.map((paper) => paper.year).filter(Number.isInteger);
  for (const id of ['from', 'to']) {
    const input = byId(id);
    input.min = Math.min(...years);
    input.max = Math.max(...years);
    input.defaultValue = id === 'from' ? input.min : input.max;
    input.value = input.defaultValue;
  }
  for (let year = Number(byId('from').min); year <= Number(byId('to').max); year += 1) {
    const bar = element('span');
    cells.years.set(year, bar);
    byId('year-histogram').append(bar);
  }
  const topicGroups=new Map();
  for(const topic of catalog.topics.values()) {
    const total=catalog.papers.filter((paper) => paper.topic_ids.includes(topic.id)).length;
    if(!total)continue;
    const group=topic.group??'Topics';
    if(!topicGroups.has(group))topicGroups.set(group,[]);
    topicGroups.get(group).push({topic,total});
  }
  for(const [group,topics] of topicGroups) {
    const branch=element('details',null,'venue-group');
    const groupSummary=element('summary');
    const groupCount=element('span',null,'count');
    groupSummary.append(element('span',group),groupCount);
    cells.topicGroups.set(group,groupCount);
    branch.append(groupSummary);
    const choices=element('div',null,'venue-choices');choices.id='topic-group-'+topics[0].topic.id;
    choices.append(selectionActions('topic',choices.id));
    for (const {topic,total} of topics) {
      const input=checkbox(choices, 'topic', topic.id, topic.name, total);
      input.title=topic.name;
      cells.topics.set(topic.id,input.parentNode.querySelector('small'));
    }
    branch.append(choices);byId('topics').append(branch);
  }
  for (const { name: group, entries } of availableVenueGroups(catalog.editionVenues)) {
    const branch = element('details', null, 'venue-group');
    const summary = element('summary');
    const total = entries.reduce((sum, entry) => sum + entry.count, 0);
    const groupCount = element('span', total, 'count');
    cells.venueGroups.set(group, groupCount);
    summary.append(element('span', group), groupCount);
    const choices = element('div', null, 'venue-choices');
    choices.id='venue-group-'+byId('venues').childElementCount;
    choices.append(selectionActions('venue',choices.id));
    entries.forEach(({ label, count, top, display }, index) => {
      if (index && entries[index - 1].top && !top) choices.append(element('hr', null, 'venue-divider'));
      const input=checkbox(choices, 'venue', label, venueCaption({venue:label},{group,label,display}), count);
      input.title=label;
      cells.venues.set(label,input.parentNode.querySelector('small'));
    });
    branch.append(summary, choices);
    branch.open = group === 'EconCS';
    byId('venues').append(branch);
  }

  form.addEventListener('submit', (event) => event.preventDefault());
  form.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-selection]');
    if (!button) return;
    const scope=button.dataset.scope ? byId(button.dataset.scope) : form;
    for (const input of scope.querySelectorAll('input[name="' + button.dataset.selection + '"]')) {
      input.checked = button.dataset.checked === 'true';
    }
    render(catalog);
  });
  form.addEventListener('input', (event) => {
    const start = byId('from');
    const end = byId('to');
    if (Number(start.value) > Number(end.value)) {
      if (event.target === start) end.value = start.value;
      else start.value = end.value;
    }
    const deferList = event.target.type === 'range';
    clearTimeout(frame);
    frame = setTimeout(() => render(catalog, { deferList }), event.target.type === 'search' || event.target.type === 'text' ? 150 : 16);   // wait for a pause in typing
  });
  form.addEventListener('reset', () => queueMicrotask(() => render(catalog)));
  function openRoute() {
    const author = authorFromHash(window.location.hash);
    if (author) expanded.add(catalog.authorIndex.routeKeys.get(author) ?? author);
    render(catalog);
  }
  window.addEventListener('hashchange', openRoute);
  openRoute();
  byId('load-state').hidden = true;
  byId('directory').hidden = false;
}

load().catch((error) => {
  console.error(error);
  byId('load-state').textContent = 'The directory data could not be loaded. Reload this page through a local server.';
});
