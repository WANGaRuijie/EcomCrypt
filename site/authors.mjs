// Display identities follow the user's small-field, name-first policy.
// Original bylines and provider IDs are never overwritten.
export function nameKey(name) {
  return String(name ?? '').normalize('NFKD').replace(/\p{Mark}/gu,'')
    .toLowerCase().replace(/\b\d{4}\b/g,'').replace(/[^\p{Letter}\p{Number}]+/gu,' ').trim();
}

function middleCompatible(a,b,shared) {
  const x=a.slice(1,-1),y=b.slice(1,-1);
  if(!x.length || !y.length)return true;
  const longX=x.filter(t=>t.length>2).join(' '),longY=y.filter(t=>t.length>2).join(' ');
  if(longX && longX===longY)return true; // omitted middle initials, compound surnames
  const initials=v=>v.map(t=>t.length<=2?t:t[0]).join('');
  const i=initials(x),j=initials(y);
  if(i===j)return true;
  return shared && [...i].sort().join('')===[...j].sort().join('');
}

export function buildAuthorIndex(catalog) {
  const nodes=new Map(), parent=new Map(), routes=new Map(), ids=new Map();
  function add(name,weight=0) {
    const key=nameKey(name);if(!key)return null;
    if(!nodes.has(key)){nodes.set(key,{key,names:new Map(),coauthors:new Set(),ids:new Set()});parent.set(key,key);}
    const n=nodes.get(key);n.names.set(name,(n.names.get(name)??0)+weight);return key;
  }
  const root=k=>parent.get(k)===k?k:(parent.set(k,root(parent.get(k))),parent.get(k));
  const join=(a,b)=>{a=root(a);b=root(b);if(a!==b)parent.set(a<b?b:a,a<b?a:b);};
  for(const [id,r] of catalog.researchers) {
    const key=add(r.name,1);if(!key)continue;
    ids.set(id,key);nodes.get(key).ids.add(id);routes.set(id,key);
  }
  for(const p of catalog.papers) {
    const credits=p.author_credits ?? [];
    for(const c of credits) {
      const key=add(c.name,1);if(!key)continue;
      routes.set('name:'+c.name.normalize('NFC'),key);
      if(ids.has(c.researcher_id))join(key,ids.get(c.researcher_id));
      for(const other of credits)if(other!==c)nodes.get(key).coauthors.add(nameKey(other.name));
    }
  }
  const surnames=new Map();
  for(const key of nodes.keys()) {
    const tokens=key.split(' ');if(tokens.length<2)continue;
    const surname=tokens.at(-1);if(!surnames.has(surname))surnames.set(surname,[]);
    surnames.get(surname).push(key);
  }
  for(const bucket of surnames.values())for(let i=0;i<bucket.length;i++)for(let j=i+1;j<bucket.length;j++) {
    const a=nodes.get(bucket[i]),b=nodes.get(bucket[j]),x=a.key.split(' '),y=b.key.split(' ');
    const shared=[...a.coauthors].some(n=>b.coauthors.has(n));
    if(x[0]===y[0] && middleCompatible(x,y,shared))join(a.key,b.key);
    else if(shared && ((x[0].length===1 && y[0].startsWith(x[0])) || (y[0].length===1 && x[0].startsWith(y[0])))) {
      if(middleCompatible(x,y,shared))join(a.key,b.key);
    }
    // S. Matthew Weinberg / Matthew Weinberg: leading first-name initial omitted.
    else if(shared && ((x[0].length===1 && x[1]===y[0]) || (y[0].length===1 && y[1]===x[0])))join(a.key,b.key);
  }
  const people=new Map();
  for(const n of nodes.values()) {
    const key='author:'+root(n.key);
    if(!people.has(key))people.set(key,{key,names:new Map(),sourceIds:new Set()});
    const p=people.get(key);
    for(const [name,score] of n.names)p.names.set(name,(p.names.get(name)??0)+score);
    for(const id of n.ids)p.sourceIds.add(id);
  }
  for(const p of people.values()) {
    p.name=[...p.names].sort((a,b)=>b[1]-a[1] || a[0].localeCompare(b[0]))[0][0];
    p.aliases=[...p.names.keys()];p.sourceIds=[...p.sourceIds];delete p.names;
  }
  const byName=new Map([...nodes.keys()].map(k=>[k,'author:'+root(k)]));
  const routeKeys=new Map([...routes].map(([route,k])=>[route,'author:'+root(k)]));
  return {people,byName,routeKeys};
}
