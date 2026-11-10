import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { authorFromHash, filterPapers, groupAuthorPapers, makeCatalog, safeWebUrl, sortPapers } from '../site/catalog.mjs';
import { availableVenueGroups, venueFor } from '../site/venues.mjs';

const dataset = JSON.parse(readFileSync(new URL('../site/data/directory.json', import.meta.url), 'utf8'));
const catalog = makeCatalog(dataset);

test('Stackelberg attack proceedings use ECAI rather than the FAIA series', () => {
 const papers=catalog.papers.filter(p=>p.doi==='10.3233/faia230501');
 assert.equal(papers.length,1);
 assert.equal(papers[0].year,2023);
 assert.equal(papers[0].kind,'conference-paper');
 assert.deepEqual(venueFor(papers[0]),{group:'EconCS',label:'ECAI'});
 assert.equal(papers[0].raw_input.venue,'Frontiers in artificial intelligence and applications');
 assert.ok(papers[0].venue_source.startsWith('https://pure.au.dk/'));
});

test('primary RFS byline excludes acknowledgements and uses journal publication year', () => {
 const paper=catalog.papers.find(p=>p.doi==='10.1093/rfs/hhz007');
 assert.equal(paper.year,2019);
 assert.deepEqual(paper.authors,['Lin William Cong','Zhiguo He']);
 assert.ok(paper.raw_input.authors.includes('Jingtao Zheng'));
 assert.equal(paper.raw_input.year,2017);
 assert.equal(paper.source_ids.openalex,'W3122636688');
 assert.ok(paper.primary_sources.some(s=>s.url.includes('linwilliamcong.com/_files/')));
});

test('Revisiting TFM uses its formal EC abstract and suppresses the related preprint', () => {
 const papers=catalog.papers.filter(p=>p.doi==='10.1145/3670865.3673621');
 assert.equal(papers.length,1);
 assert.equal(papers[0].year,2024);
 assert.equal(papers[0].kind,'conference-abstract');
 assert.equal(venueFor(papers[0]).label,'EC');
 assert.ok(papers[0].topic_ids.includes('tfm'));
 assert.ok(papers[0].topic_ids.includes('rational-cryptography'));
 assert.ok(papers[0].versions.some(p=>p.source_ids.arxiv==='2410.07566'));
 assert.ok(!catalog.papers.some(p=>p.doi==='10.48550/arxiv.2410.07566'));
});

test('publisher-confirmed AFT edition replaces stale preprint venue and year', () => {
 const works=catalog.papers.filter(p=>p.doi==='10.4230/lipics.aft.2025.24');
 assert.equal(works.length,1);
 assert.equal(works[0].year,2025);
 assert.equal(works[0].formal_publication,true);
 assert.equal(venueFor(works[0]).label,'AFT');
 assert.equal(works[0].source_ids.arxiv,'2402.08661');
 assert.ok(works[0].publication_corrections.some(p=>p.kind==='preprint'&&p.year===2024));
});

test('disciplinary aliases distinguish conferences, workshops and overlapping journal names', () => {
 for(const [venue,group,label] of [
  ['ACM SIGOPS Symposium on Operating Systems Principles (SOSP)','Systems','SOSP'],
  ['Proceedings of the ACM SIGOPS 30th Symposium on Operating Systems Principles (SOSP 2024)','Systems','SOSP'],
  ['Journal of Cybersecurity','Security & Crypto','J. Cybersecurity'],
  ['Frontiers in Blockchain','Blockchain','Front. Blockchain'],
  ['GLOBECOM 2023 - 2023 IEEE Global Communications Conference','Systems','GLOBECOM'],
  ['2023 IEEE Security and Privacy Workshops (SPW)','Security & Crypto','IEEE S&P Workshops'],
  ['2018 3rd IEEE European Symposium on Security and Privacy Workshops (EuroS&PW)','Security & Crypto','EuroS&P Workshops'],
  ['IEEE Computer Security Foundations Workshop (CSFW)','Security & Crypto','CSF'],
  ['Applied Economics Letters','Econ','Applied Econ. Lett.'],
  ['Applied Mathematical Finance','Finance','Applied Math. Finance'],
  ['Journal of International Money and Finance','Finance','JIMF'],
  ['Decision Analysis','OR/MS','Decision Analysis'],
  ['2025 IEEE Global Blockchain Conference (GBC)','Blockchain','GBC'],
 ])assert.deepEqual(venueFor({venue}),{group,label});
 assert.equal(venueFor({venue:'Economics Letters'}).label,'Economics Letters');
 assert.equal(venueFor({venue:'Mathematical Finance'}).label,'Mathematical Finance');
 assert.equal(venueFor({venue:'An Unregistered Venue with ECinsideItsName'}).group,'Interdisciplinary');
 assert.equal(venueFor({venue:'IEEE European Symposium on Security and Privacy'}).label,'EuroS&P');
});

test('JCO journal version replaces the differently titled Bitcoin preprint', () => {
 const paper=catalog.papers.filter(p=>p.doi==='10.1007/s10878-021-00768-4');
 assert.equal(paper.length,1);assert.equal(paper[0].year,2022);
 assert.equal(venueFor(paper[0]).label,'JCO');assert.equal(venueFor(paper[0]).group,'OR/MS');
 assert.equal(paper[0].authors.length,5);
 assert.ok(!catalog.papers.some(p=>p.title==='Discouraging Pool Block Withholding Attacks in Bitcoins'));
 assert.ok(filterPapers(catalog,{query:'Discouraging Pool Block Withholding Attacks in Bitcoins'}).some(p=>p.doi===paper[0].doi));
});

test('foundational Algorand is included once and fallback venue groups are separate', () => {
 const records=catalog.papers.filter(p=>p.doi==='10.1145/3132747.3132757');
 assert.equal(records.length,1);assert.equal(records[0].collection_basis,'foundational_context');
 assert.ok(records[0].topic_ids.includes('pos'));
 assert.equal(venueFor({venue:'A Source Not Yet Classified'}).group,'Interdisciplinary');
 assert.equal(venueFor({venue:null}).group,'Unlisted');
 const groups=availableVenueGroups(new Map([['a',venueFor({venue:'A Source Not Yet Classified'})],['b',venueFor({venue:null})]]));
 assert.deepEqual(groups.map(g=>g.name),['Interdisciplinary','Unlisted']);
 assert.deepEqual(groups[0].entries.map(e=>e.label),['A Source Not Yet Classified']);
 assert.ok(![...catalog.venues.values()].some(v=>v.label==='Other' || v.group==='Other venues'));
});

test('new EconCS sources are mapped and governance has a concise caption', () => {
 for(const venue of ['ECAI','ADT','COMSOC'])assert.equal(venueFor({venue}).group,'EconCS');
 assert.equal(catalog.topics.get('governance').name,'Blockchain Governance');
 assert.ok(![...catalog.topics.values()].some(t=>t.name==='Blockchain Economics'));
});

test('middle-name omissions merge by default, conflicting full initials remain distinct', () => {
 const c={researchers:new Map([['r',{id:'r',name:'Rafael Frongillo'}]])};
 const ps=[{id:'a',author_credits:[{name:'Rafael Frongillo',researcher_id:'r'},{name:'Alice Example'}]},
 {id:'b',author_credits:[{name:'Rafael M. Frongillo'},{name:'Alice Example'}]}];
 assert.equal(groupAuthorPapers(c,ps).filter(g=>g.name.includes('Frongillo')).length,1);
 assert.equal(groupAuthorPapers(c,[{...ps[1],author_credits:[{name:'Rafael M. Frongillo'},{name:'Other Person'}]},ps[0]]).filter(g=>g.name.includes('Frongillo')).length,1);
 const c2={researchers:new Map([['r',{id:'r',name:'Rafael J. Frongillo'}]])};
 assert.equal(groupAuthorPapers(c2,[{...ps[0],author_credits:[{name:'Rafael J. Frongillo',researcher_id:'r'},{name:'Alice Example'}]},ps[1]]).filter(g=>g.name.includes('Frongillo')).length,2);
});

test('economic, finance and operations venues are categorized independently of quality', () => {
  assert.equal(venueFor({venue:'Journal of Institutional Economics'}).group,'Econ');
  assert.equal(venueFor({venue:'Energy Economics'}).group,'Econ');
  assert.equal(venueFor({venue:'Journal of Futures Markets'}).group,'Finance');
  assert.equal(venueFor({venue:'European Finance Review'}).group,'Finance');
  assert.equal(venueFor({venue:'Journal of Operations Management'}).group,'OR/MS');
});

test('same-name authors merge despite missing or contradictory provider IDs', () => {
  const c={researchers:new Map([['a',{id:'a',name:'Aviv Yaish'}]])};
  const papers=[{id:'one',author_credits:[{name:'Aviv Yaish',researcher_id:'a'}]},
    {id:'two',author_credits:[{name:'Aviv Yaish'}]}];
  assert.equal(groupAuthorPapers(c,papers).length,1);
  assert.equal(groupAuthorPapers(c,papers)[0].papers.length,2);
  c.researchers.set('b',{id:'b',name:'Aviv Yaish'});
  assert.equal(groupAuthorPapers(c,[papers[0],{id:'other',author_credits:[{name:'Aviv Yaish',researcher_id:'b'}]}]).length,1);
});

test('merged names count shared papers once and keep stable keys under filters', () => {
 const fixture=makeCatalog({schema_version:1,topics:[],institutions:[],researchers:[
  {id:'a',name:'Ciamac Moallemi'},{id:'b',name:'Ciamac C. Moallemi'}],papers:[
  {id:'p1',title:'One',topic_ids:[],author_credits:[{name:'Ciamac Moallemi',researcher_id:'a'},{name:'Ciamac C. Moallemi',researcher_id:'b'}]},
  {id:'p2',title:'Two',topic_ids:[],author_credits:[{name:'Ciamac C. Moallemi',researcher_id:'b'}]}]});
 const all=groupAuthorPapers(fixture,fixture.papers),subset=groupAuthorPapers(fixture,fixture.papers.filter(p=>p.id==='p2'));
 assert.equal(all.length,1);assert.equal(all[0].papers.length,2);assert.equal(subset[0].key,all[0].key);
 assert.equal(fixture.authorIndex.routeKeys.get('a'),fixture.authorIndex.routeKeys.get('b'));
});

test('reported duplicate authors have one display entry', () => {
  const rows=groupAuthorPapers(catalog,catalog.papers);
  for(const name of ['Rafael Frongillo','Aviv Yaish','Elaine Shi']) assert.equal(rows.filter(row=>row.name===name).length,1);
});

test('paper view sorts newest first, then title alphabetically and unknown years last', () => {
  const records = [{id:'z',title:'Zulu',year:2025},{id:'b',title:'Beta',year:null},
    {id:'c',title:'Charlie',year:2026},{id:'a',title:'alpha',year:2025}];
  assert.deepEqual(sortPapers(records).map(p => p.id), ['c','a','z','b']);
  assert.equal(records[0].id, 'z');
});

test('preprints have an explicit venue group and formal publications suppress their preprints', () => {
  assert.deepEqual(venueFor({kind:'preprint',venue:'arXiv'}), {group:'Preprints & Working Papers',label:'arXiv'});
  assert.equal(venueFor({kind:'preprint',venue:'arXiv',doi:'10.48550/arxiv.2605.27602',accepted_venue:'FC'}).label,'FC');
  assert.ok(availableVenueGroups(catalog.venues).some(group => group.name === 'Preprints & Working Papers'));
  const fixture = makeCatalog({schema_version:1,researchers:[],institutions:[],topics:[],papers:[{
    id:'work',title:'Paper',formal_publication:false,kind:'preprint',publications:[{
      id:'formal',title:'Paper',venue:'EC',year:2025}],topic_ids:[]}]});
  assert.deepEqual(fixture.papers.map(p => p.id), ['formal']);
});

test('Golden Seeds are indexed and filter controls compose', () => {
  assert.equal(dataset.papers.filter(({ id }) => id.startsWith('gs-')).length, 50);
  assert.equal(catalog.topics.size, 13);
  assert.ok(catalog.papers.some(p => p.topic_ids.includes('incentive-systems')));
  assert.deepEqual(
    filterPapers(catalog, { query: 'nAKAMOTO peer', year: '2008', topic: 'foundations' }).map(({ id }) => id),
    ['gs-001'],
  );
  assert.deepEqual(filterPapers(catalog, { query: 'Nakamoto peer', year: '2019' }), []);
  assert.ok(filterPapers(catalog, { year: 'unknown' }).every(({ year }) => year == null));
});

test('author routes can open a linked profile', () => {
  const { id } = dataset.researchers[0];
  assert.equal(authorFromHash('#/author/' + encodeURIComponent(id)), id);
  assert.equal(authorFromHash('#/institution/legacy/researcher/' + id), id);
  assert.equal(authorFromHash('#/author/%'), null);
});

test('external links reject code, credential-bearing URLs, and invalid URLs', () => {
  assert.equal(safeWebUrl('javascript:alert(1)'), null);
  assert.equal(safeWebUrl('https://user:secret@example.org'), null);
  assert.equal(safeWebUrl('/relative'), null);
  assert.equal(safeWebUrl('https://doi.org/10.1000/test'), 'https://doi.org/10.1000/test');
});

test('topic and venue checkboxes combine with inclusive years', () => {
  const rows = filterPapers(catalog, {
    topics: new Set(['tfm', 'amm']),
    venues: new Set(['AFT', 'EC']),
    from: 2020,
    to: 2021,
  });
  assert.ok(rows.some(({ id }) => id === 'gs-020'));
  assert.ok(rows.some(({ id }) => id === 'gs-030'));
  assert.ok(rows.every((paper) => paper.year >= 2020 && paper.year <= 2021));
  assert.ok(rows.every((paper) => ['AFT', 'EC'].includes(catalog.venues.get(paper.id).label)));
  assert.equal(catalog.venues.get('gs-023').label, 'IEEE S&P');
  assert.equal(catalog.venues.get('gs-001').label, 'Unlisted');
});

test('each Red Balloons coauthor gets exactly one publication row', () => {
  const paper = catalog.papers.find(({ id }) => id === 'gs-006');
  const groups = groupAuthorPapers(catalog, [paper]);
  assert.equal(groups.length, 4);
  for (const { papers } of groups) assert.deepEqual(papers, [paper]);
  assert.deepEqual(filterPapers(catalog, { query: 'red balloons microsoft israel' }), []);
});

test('authors are sorted by matching edition count with alphabetical ties', () => {
  for (const papers of [catalog.papers, filterPapers(catalog, { year: '2024' })]) {
    const groups = groupAuthorPapers(catalog, papers);
    const named = groups.filter(({ key }) => key !== 'uncredited');
    assert.deepEqual(named, [...named].sort((a, b) =>
      b.papers.length - a.papers.length || a.name.localeCompare(b.name) || a.key.localeCompare(b.key)));
    assert.equal(new Set(groups.flatMap((group) => group.papers.map(({ id }) => id))).size, papers.length);
  }
});

test('venue counts distinguish conference and journal editions and suppress their preprints', () => {
  const backbone = catalog.papers.filter((paper) => paper.id === 'gs-003' || paper.work_id === 'gs-003');
  assert.deepEqual(backbone.map((paper) => catalog.venues.get(paper.id).label).sort(), ['EUROCRYPT', 'JACM']);
  assert.equal(catalog.venues.get(backbone.find((paper) => paper.work_id).id).group, 'TCS');
  assert.equal(catalog.venues.get('gs-005').group, 'Systems');
  assert.equal(catalog.venues.get('gs-022').label, 'FC Workshops');
  assert.equal(catalog.venues.get(catalog.papers.find((paper) => paper.work_id === 'gs-031').id).label, 'DeFi@CCS');
  assert.equal(catalog.venues.get(catalog.papers.find((paper) => paper.work_id === 'gs-033').id).label, 'RFS');
  assert.ok(catalog.papers.every((paper) => paper.venue !== 'Lecture Notes in Computer Science'));
  const feeDesign = catalog.papers.filter((paper) => paper.id === 'gs-018' || paper.work_id === 'gs-018');
  assert.deepEqual(feeDesign.map((paper) => catalog.venues.get(paper.id).label).sort(), ['EC', 'JACM']);
});

test('empty checkbox selection shows no papers and selecting everything restores all', () => {
  assert.deepEqual(filterPapers(catalog, { topics: new Set() }), []);
  assert.deepEqual(filterPapers(catalog, { venues: new Set() }), []);
  const all = filterPapers(catalog, {
    topics: new Set(catalog.topics.keys()),
    venues: new Set([...catalog.venues.values()].map(({ label }) => label)),
  });
  assert.equal(all.length, catalog.papers.length);
});

test('venue menus contain only indexed venues with positive counts', () => {
  const groups = availableVenueGroups(catalog.venues);
  assert.ok(groups.length);
  assert.ok(groups.every((group) => group.entries.length && group.entries.every(({ count }) => count > 0)));
  assert.equal(groups.flatMap(({ entries }) => entries).reduce((sum, { count }) => sum + count, 0), catalog.papers.length);
  assert.deepEqual(availableVenueGroups(new Map()), []);
});

test('journal names take precedence over overlapping conference phrases', () => {
  assert.equal(venueFor({ venue: 'ACM Transactions on Economics and Computation' }).label, 'TEAC');
  assert.equal(venueFor({ venue: 'Transactions on Economics and Computation' }).label, 'TEAC');
  assert.equal(venueFor({ venue: 'Proceedings of the 25th ACM Conference on Economics and Computation' }).label, 'EC');
  assert.equal(venueFor({ venue: 'Journal of Economic Theory' }).label, 'JET');
  assert.equal(venueFor({ venue: 'Economic Theory' }).label, 'ET');
  assert.equal(venueFor({ venue: 'Theoretical Economics' }).label, 'TE');
  assert.equal(venueFor({ venue: 'Journal of Political Economy Microeconomics' }).label, 'JPE Micro');
  assert.equal(venueFor({ venue: 'Mathematics of Operations Research' }).label, 'MOR');
  const journal = catalog.papers.find(({ doi }) => doi === '10.1145/3530799');
  assert.equal(catalog.venues.get(journal.id).label, 'TEAC');
});

test('an earlier title remains searchable after a formal edition upgrade', () => {
  const upgraded=catalog.papers.find(p=>p.doi==='10.1007/978-3-031-68974-1_8');
  assert.ok(upgraded);
  assert.ok(catalog.searchable.get(upgraded.id).includes('greedy transaction fee mechanisms'));
  assert.equal(catalog.papers.filter(p=>p.doi==='10.48550/arxiv.2210.07793').length,0);
});
