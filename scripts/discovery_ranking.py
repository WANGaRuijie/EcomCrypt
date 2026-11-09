"""Order cached candidates for review without filtering author bibliographies."""
import re
from quality import assess

INTERSECTION = re.compile(
    r'blockchain|bitcoin|ethereum|cryptocurrenc|proof.of.stake|proof.of.work|miner|defi|'
    r'decentralized.*(?:financ|exchange)|constant.function|automated.market|transaction.fee|'
    r'cryptograph|security.game|rational.*(?:secur|protocol|secret)|attacker.defender|'
    r'pseudo.?equilibr|collusion.preserv|incoercib|(?:crypt.*game|game.*crypt)', re.I)


def review_priority(candidate, priority_author_ids):
    record = candidate['record']
    signal = bool(INTERSECTION.search(record.get('title', '')))
    requested_author = any(author.get('ids', {}).get('openalex') in priority_author_ids
                           for author in record.get('authors', []))
    # A known author's unrelated work must not displace an intersection candidate.
    # Abstract availability is deliberately absent from this ordering.
    return (not signal, not requested_author, assess(record)['decision'] != 'priority',
            not bool(candidate.get('hints')), -len(candidate.get('seeds', ())), record['source_id'])
