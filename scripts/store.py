"""Persistent candidate store for the monthly pipeline (SQLite, stdlib only).

One row per *work*; every source record (DBLP key, DOI, arXiv ID, OpenAlex ID,
ePrint ID, normalized title) is an alias of exactly one work. Screening results
are keyed by (work, stage, rubric version), so a work is screened once per rubric
version no matter how many sources or months it reappears in.
"""
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from metadata import normalize_doi, normalize_title

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / '.cache/pipeline/store.sqlite'

SCHEMA = """
CREATE TABLE IF NOT EXISTS works (
  key TEXT PRIMARY KEY, title TEXT, year INTEGER, venue TEXT, doi TEXT, kind TEXT,
  venue_decision TEXT, venue_group TEXT, venue_id TEXT,
  abstract TEXT DEFAULT '', abstract_source TEXT, tldr TEXT DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new', status_reason TEXT, signals TEXT,
  origin TEXT, first_seen TEXT, updated TEXT, directory_id TEXT, curated INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS works_status ON works(status);
CREATE TABLE IF NOT EXISTS aliases (alias TEXT PRIMARY KEY, key TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS aliases_key ON aliases(key);
CREATE TABLE IF NOT EXISTS editions (
  source TEXT NOT NULL, source_id TEXT NOT NULL, key TEXT NOT NULL, record TEXT NOT NULL, seen TEXT,
  PRIMARY KEY (source, source_id));
CREATE INDEX IF NOT EXISTS editions_key ON editions(key);
CREATE TABLE IF NOT EXISTS screens (
  key TEXT NOT NULL, stage TEXT NOT NULL, rubric TEXT NOT NULL, input_hash TEXT NOT NULL,
  model TEXT, result TEXT NOT NULL, at TEXT, PRIMARY KEY (key, stage, rubric, input_hash));
CREATE TABLE IF NOT EXISTS watermarks (name TEXT PRIMARY KEY, value TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS llm_requests (
  request_id TEXT PRIMARY KEY, run TEXT, status TEXT, reserved INTEGER, charged INTEGER, at TEXT);
"""

TERMINAL = {'in_directory', 'promoted'}
# Lanes whose records are already strong nominations (cite a directory paper, or were
# flagged by the legacy evidence review): they skip the keyword prefilter, never the venue gate.
CURATED_ORIGINS = ('legacy:evidence-queue', 'openalex:cites', 'restore')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def arxiv_id(value):
    value = re.sub(r'v\d+$', '', (value or '').lower().strip())
    value = value.removeprefix('arxiv:').removeprefix('10.48550/arxiv.')
    return value if re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[a-z]+)?/\d{7})', value) else None


def aliases_for(record):
    """Identity strings for one source record. Order: strongest first."""
    out = []
    doi = normalize_doi(record.get('doi'))
    ax = arxiv_id(record.get('arxiv') or (record.get('source_id') if record.get('source') == 'arxiv' else ''))
    if doi and doi.startswith('10.48550/arxiv.'):
        ax = ax or arxiv_id(doi)
        doi = None
    for value in [record.get('url'), record.get('source_url'), *(record.get('ee') or [])]:
        match = re.search(r'arxiv\.org/(?:abs|pdf)/([^?#\s]+)', value or '')
        if match:
            ax = ax or arxiv_id(match[1].removesuffix('.pdf'))
    if doi:
        out.append('doi:' + doi)
    if ax:
        out.append('arxiv:' + ax)
    ids = dict(record.get('source_ids') or {})
    if record.get('source') and record.get('source_id'):
        ids.setdefault(record['source'], record['source_id'])
    for source, value in sorted(ids.items()):
        if not value or source in {'crossref', 'arxiv'}:
            continue
        if source == 'publisher':
            continue
        out.append(f'{source}:{value}')
    title = normalize_title(record.get('title'))
    if len(title) >= 25 and len(title.split()) >= 4:
        out.append('t:' + title)
    return list(dict.fromkeys(out))


def _key_for(aliases):
    strong = [a for a in aliases if not a.startswith('t:')] or aliases
    return 'w:' + hashlib.sha256(strong[0].encode()).hexdigest()[:20]


class Store:
    def __init__(self, path=DEFAULT):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=60, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(works)')}
        if 'curated' not in columns:
            self.db.execute('ALTER TABLE works ADD COLUMN curated INTEGER DEFAULT 0')

    def close(self):
        self.db.close()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield self.db
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')

    # --- identity -------------------------------------------------------
    def lookup(self, aliases):
        if not aliases:
            return set()
        marks = ','.join('?' * len(aliases))
        return {row['key'] for row in self.db.execute(f'SELECT key FROM aliases WHERE alias IN ({marks})', aliases)}

    def _merge(self, target, others):
        for key in others:
            if key == target:
                continue
            self.db.execute('UPDATE aliases SET key=? WHERE key=?', (target, key))
            self.db.execute('UPDATE editions SET key=? WHERE key=?', (target, key))
            self.db.execute('UPDATE OR IGNORE screens SET key=? WHERE key=?', (target, key))
            self.db.execute('DELETE FROM screens WHERE key=?', (key,))
            old = self.db.execute('SELECT * FROM works WHERE key=?', (key,)).fetchone()
            keep = self.db.execute('SELECT * FROM works WHERE key=?', (target,)).fetchone()
            if old and keep:
                if old['status'] in TERMINAL and keep['status'] not in TERMINAL:
                    self.db.execute('UPDATE works SET status=?, directory_id=? WHERE key=?',
                                    (old['status'], old['directory_id'], target))
                if old['curated']:
                    self.db.execute('UPDATE works SET curated=1 WHERE key=?', (target,))
                if len(old['abstract'] or '') > len(keep['abstract'] or ''):
                    self.db.execute('UPDATE works SET abstract=?, abstract_source=? WHERE key=?',
                                    (old['abstract'], old['abstract_source'], target))
            self.db.execute('DELETE FROM works WHERE key=?', (key,))

    def add(self, record, *, origin, abstract=None, status=None, directory_id=None):
        """Insert/attach one source record. Returns (key, is_new_work)."""
        aliases = aliases_for(record)
        if not aliases:
            return None, False
        with self.tx():
            keys = self.lookup(aliases)
            if keys:
                rows = self.db.execute(
                    f"SELECT key, first_seen FROM works WHERE key IN ({','.join('?' * len(keys))}) ORDER BY first_seen, key",
                    sorted(keys)).fetchall()
                target = rows[0]['key'] if rows else sorted(keys)[0]
                self._merge(target, keys - {target})
                new = False
            else:
                target, new = _key_for(aliases), True
            for alias in aliases:
                self.db.execute('INSERT OR REPLACE INTO aliases(alias, key) VALUES (?, ?)', (alias, target))
            source = record.get('source') or origin
            source_id = record.get('source_id') or aliases[0]
            self.db.execute('INSERT OR REPLACE INTO editions(source, source_id, key, record, seen) VALUES (?,?,?,?,?)',
                            (source, source_id, target, json.dumps(record, ensure_ascii=False, sort_keys=True), now()))
            stamp = now()
            if new:
                self.db.execute(
                    'INSERT INTO works(key, title, year, venue, doi, kind, origin, first_seen, updated, status, directory_id) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (target, record.get('title'), record.get('year'), record.get('venue'), normalize_doi(record.get('doi')),
                     record.get('kind'), origin, stamp, stamp, status or 'new', directory_id))
            else:
                self.db.execute('UPDATE works SET updated=? WHERE key=?', (stamp, target))
                if status in TERMINAL:
                    self.db.execute('UPDATE works SET status=?, directory_id=COALESCE(?, directory_id) WHERE key=?',
                                    (status, directory_id, target))
            if origin.startswith(CURATED_ORIGINS):
                self.db.execute('UPDATE works SET curated=1 WHERE key=?', (target,))
            if abstract:
                self.set_abstract(target, abstract, source, _tx=False)
        return target, new

    def set_abstract(self, key, text, source, *, tldr=None, _tx=True):
        text = ' '.join((text or '').split())
        def apply():
            row = self.db.execute('SELECT abstract FROM works WHERE key=?', (key,)).fetchone()
            if row is not None and len(text) > len(row['abstract'] or ''):
                self.db.execute('UPDATE works SET abstract=?, abstract_source=? WHERE key=?', (text[:6000], source, key))
            if tldr:
                self.db.execute("UPDATE works SET tldr=? WHERE key=? AND COALESCE(tldr,'')=''", (tldr[:600], key))
        if _tx:
            with self.tx():
                apply()
        else:
            apply()

    # --- queries --------------------------------------------------------
    def editions(self, key):
        return [json.loads(row['record']) for row in
                self.db.execute('SELECT record FROM editions WHERE key=? ORDER BY source, source_id', (key,))]

    def work(self, key):
        row = self.db.execute('SELECT * FROM works WHERE key=?', (key,)).fetchone()
        return dict(row) if row else None

    def works(self, statuses=None, limit=None):
        sql, args = 'SELECT * FROM works', []
        if statuses:
            sql += f" WHERE status IN ({','.join('?' * len(statuses))})"
            args = list(statuses)
        sql += ' ORDER BY first_seen, key'
        if limit:
            sql += f' LIMIT {int(limit)}'
        return [dict(row) for row in self.db.execute(sql, args)]

    def set_status(self, key, status, reason=None, **fields):
        cols = ['status=?', 'status_reason=?', 'updated=?']
        args = [status, reason, now()]
        for name, value in fields.items():
            cols.append(f'{name}=?')
            args.append(json.dumps(value) if isinstance(value, (list, dict)) else value)
        self.db.execute(f"UPDATE works SET {', '.join(cols)} WHERE key=?", (*args, key))

    def counts(self):
        return {row['status']: row['n'] for row in
                self.db.execute('SELECT status, COUNT(*) n FROM works GROUP BY status ORDER BY n DESC')}

    # --- screens --------------------------------------------------------
    def screen(self, key, stage, rubric):
        row = self.db.execute('SELECT result, input_hash FROM screens WHERE key=? AND stage=? AND rubric=? ORDER BY at DESC LIMIT 1',
                              (key, stage, rubric)).fetchone()
        return (json.loads(row['result']), row['input_hash']) if row else (None, None)

    def save_screen(self, key, stage, rubric, input_hash, model, result):
        self.db.execute('INSERT OR REPLACE INTO screens VALUES (?,?,?,?,?,?,?)',
                        (key, stage, rubric, input_hash, model, json.dumps(result, ensure_ascii=False), now()))

    # --- watermarks -----------------------------------------------------
    def get_mark(self, name, default=None):
        row = self.db.execute('SELECT value FROM watermarks WHERE name=?', (name,)).fetchone()
        return row['value'] if row else default

    def set_mark(self, name, value):
        self.db.execute('INSERT OR REPLACE INTO watermarks VALUES (?,?,?)', (name, str(value), now()))


class Spend:
    """Per-run LLM budget with durable pre-request reservations (nanodollars)."""

    def __init__(self, store, run, limit_usd):
        self.store, self.run, self.limit = store, run, int(round(limit_usd * 1e9))
        self._lock = __import__('threading').Lock()

    @property
    def used(self):
        row = self.store.db.execute('SELECT COALESCE(SUM(charged),0) s FROM llm_requests WHERE run=?', (self.run,)).fetchone()
        return int(row['s'])

    def reserve(self, amount):
        with self._lock:
            if self.used + amount > self.limit:
                raise BudgetExhausted(f'LLM budget for run {self.run} exhausted (${self.used / 1e9:.4f} of ${self.limit / 1e9:.2f})')
            request_id = f'{self.run}:{time.time_ns()}'
            self.store.db.execute('INSERT INTO llm_requests VALUES (?,?,?,?,?,?)',
                                  (request_id, self.run, 'pending', amount, amount, now()))
            return request_id

    def settle(self, request_id, amount):
        with self._lock:
            self.store.db.execute("UPDATE llm_requests SET status='settled', charged=? WHERE request_id=?",
                                  (int(amount), request_id))

    def total_all_runs(self):
        row = self.store.db.execute('SELECT COALESCE(SUM(charged),0) s FROM llm_requests').fetchone()
        return int(row['s'])


class BudgetExhausted(RuntimeError):
    pass
