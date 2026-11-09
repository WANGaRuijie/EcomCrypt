"""Add independently supported secondary topics; retain the original classification."""
import re
from pathlib import Path

from directory import read_json

TAXONOMY = Path(__file__).resolve().parents[1] / 'data/topic_taxonomy_v2.json'
ASSIGNMENTS = TAXONOMY.parent / 'topic_assignments_v2.json'


def apply_taxonomy(directory):
    """Replace display topics with the fine-grained taxonomy; papers not yet assigned use the legacy mapping."""
    if not TAXONOMY.exists():
        return
    taxonomy = read_json(TAXONOMY)
    records = read_json(ASSIGNMENTS)['records'] if ASSIGNMENTS.exists() else {}
    directory['topics'] = [{'id': t['id'], 'name': t['name'], 'group': g['name']} for g in taxonomy['groups'] for t in g['topics']]
    for paper in directory['papers']:
        legacy = list(paper['topic_ids'])
        mapped = [new for old in legacy for new in taxonomy['legacy_map'].get(old, [])]
        paper['legacy_topic_ids'] = legacy
        paper['topic_ids'] = records.get(paper['id'], {}).get('topics') or list(dict.fromkeys(mapped))

RULES = {
 'tfm':r'transaction fee|fee market|eip.?1559|base fee|gas auction',
 'amm':r'automated market maker|\bamm\b|\bamms\b|uniswap|constant.function market|liquidity provision',
 'mev':r'\bmev\b|extractable value|transaction order|sandwich|front.running|ordering auction',
 'defi':r'\bdefi\b|decentralized (?:finance|exchange|lending)|stablecoin|liquidation|uniswap|automated market maker',
 'mining':r'selfish min|mining pool|miner revenue|block withholding|mining game|double.spend',
 'pos':r'proof.of.stake|\bstaking\b|validator incentive|slashing|liquid staking',
 'rational-cryptography':r'rational (?:cryptograph|secret sharing)|security game|game.theoretic.*(?:security|coin toss|fair)|cryptographic commitment|strategic.*(?:adversar|privacy)',
}

def annotate(paper, extra_text=''):
    text=paper['title']+' '+extra_text
    evidence=[]
    economic_topics=[]
    for topic,pattern in {
      'tokenomics':r'tokenomics|token (?:supply|valuation|issuance|distribution)|monetary policy|seigniorage|cryptocurrency adoption|network adoption|token econ|inflation',
      'economic-security':r'economic security|security budget|attack costs?|cost of attack|double.spend|selfish mining|bribery|bribing|corruptive|stake attacks?'
    }.items():
        match=re.search(pattern,text,re.I)
        if match:
            economic_topics.append(topic)
            if topic not in paper['topic_ids']:paper['topic_ids'].append(topic)
            evidence.append({'topic':topic,'method':'economic_subtopic_explicit_text_v1','excerpt':match.group()})
    if economic_topics and 'economics' in paper['topic_ids']:paper['topic_ids'].remove('economics')
    governance=re.search(r'governance|\bdao\b|vote delegation|voting|delegatee',text,re.I)
    strategic=re.search(r'game.theor|nash|equilibri|strategic|incentive|collusion|brib|mechanism|impossibility|rational|quadratic voting',text,re.I)
    blockchain=re.search(r'blockchain|\bdao\b|\bdefi\b|\bpos\b|proof.of.stake|\bdpos\b',text,re.I)
    if governance and strategic and blockchain:
        if 'governance' not in paper['topic_ids']:paper['topic_ids'].append('governance')
        evidence.append({'topic':'governance','method':'blockchain_governance_and_strategic_evidence_v1','excerpt':governance.group()+' / '+strategic.group()})
    for topic,pattern in RULES.items():
        match=re.search(pattern,text,re.I)
        if match:
            if topic not in paper['topic_ids']:paper['topic_ids'].append(topic)
            evidence.append({'topic':topic,'method':'explicit_text_rule_v1','excerpt':match.group()})
    if evidence:paper['topic_annotations']=evidence
