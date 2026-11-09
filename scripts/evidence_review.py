"""Recall safeguards. These nominate evidence review; they never authorize adoption."""
import re


def intersection_title(title):
    text = title.lower()
    setting = re.search(r'bitcoin|blockchain|ethereum|\bdefi\b|cryptocurrenc|decentralized (governance|mechanism)|transaction fee|automated market maker', text)
    strategy = re.search(r'incentiv|mechanism|auction|collus|strateg|game|welfare|revenue|mining pool|governance|market|fee|economic', text)
    security = re.search(r'cryptograph|secur|secret sharing|coin toss|privacy', text)
    game = re.search(r'rational|game.theor|incentive|strateg|mechanism|arbitrary preferences', text)
    return bool((setting and strategy) or (security and game))


def evidence_review(record, label, abstract=None):
    """Absence of evidence is not evidence of irrelevance, even after an old model label."""
    if label.get('evidence_validation') or label.get('decision') == 'uncertain':
        return {'status': 'review_evidence', 'reason': 'Unresolved classification/evidence; obtain primary text or publisher description.'}
    text = record.get('abstract', '') if abstract is None else abstract
    if not text.strip():
        return {'status': 'review_evidence', 'reason': 'No abstract evidence recovered; a negative model label cannot establish exclusion. Recover source evidence first.'}
    if intersection_title(record.get('title', '')) and (len(text.split()) < 80 or label.get('decision') != 'core'):
        return {'status': 'review_evidence', 'reason': 'Intersection-bearing title conflicts with a thin or negative abstract-only assessment; primary evidence required.'}
    return None


def prefer_abstract(previous, incoming):
    """A sparse enrichment response must not destroy already collected evidence."""
    return incoming if len((incoming or '').strip()) > len((previous or '').strip()) else previous or ''


def retain_editorial_followup(previous, computed):
    """Only an explicit resolution can release a supervisor's pending review."""
    if previous.get('editorial_review_required') and not previous.get('editorial_resolution'):
        return previous.get('followup') or {'status': 'review_evidence', 'reason': 'Independent editorial review remains pending.'}
    return computed


def persist_reviews(path, rows, report):
    """Independent unresolved lane survives source-ID dedup and future model reruns."""
    from directory import read_json, write_json
    relevant=[row for row in rows if row.get('status')=='review_evidence']
    if not relevant:return
    document=read_json(path) if path.exists() else {'schema_version':1,'records':[]}
    by_id={row['id']:row for row in document['records']}
    for row in relevant:
        identifier=row['classification']['id'];evidence=row['evidence_input']
        saved=by_id.setdefault(identifier,{'id':identifier,'classification_history':[]})
        observation={'report':str(report),'row':row}
        if observation not in saved['classification_history']:saved['classification_history'].append(observation)
        saved.update(raw_input=evidence['raw_input'],abstract=evidence['abstract'],followup=row['followup'],
                     status='resolved' if saved.get('editorial_resolution') else 'review_evidence')
    document['records']=list(by_id.values());write_json(path,document)
