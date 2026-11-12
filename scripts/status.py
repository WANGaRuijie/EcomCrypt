"""One-page progress board for the owner: what is running, what is waiting, and on whom.

    python scripts/status.py [--log PATH ...] [--out .out/status/index.html]

Reads the pipeline store read-only, so it is safe while a run is in progress.
"""
import argparse
import html
import json
import math
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from venue_policy import queue_rank  # noqa: E402

STORE = ROOT / '.cache/pipeline/store.sqlite'
BACKOFF = ROOT / '.cache/source-backoff'
CATALOG = ROOT / 'site/data/catalog.json'

# (status, label, what it means, who moves it on)
STAGES = [
    ('new', '未分流', '刚抓进来，还没核对 venue', '自动，不花钱'),
    ('venue_unknown', 'venue 未登记', '出处不在登记表里，直接淘汰（2026-11-11 决定）', '不再处理'),
    ('denied_venue', 'venue 被拒', '出处在拒收名单', '不再处理'),
    ('prefilter_drop', '规则预筛淘汰', '关键词明显不沾边', '不再处理'),
    ('prefilter_pass', '规则预筛通过', '等标题筛', '自动，花 LLM'),
    ('title_drop', '标题筛淘汰', '模型看标题判为无关', '不再处理'),
    ('title_keep', '标题筛保留', '等摘要筛', '自动，花 LLM'),
    ('screen_exclude', '摘要筛排除', '读过摘要，不收', '不再处理'),
    ('needs_fulltext', '缺摘要', '没有摘要，判不了', '夜里补摘要后重筛'),
    ('screen_include', '摘要筛收录', '等写入目录', '你批准后写入'),
    ('review_confidence', '待复核：把握不足', '模型或 ChatGPT 拿不准', '你'),
    ('review_metadata', '待复核：元数据', '出处、年份或版本对不上', '你或我核对'),
    ('held_editorial', '待编辑决定', '如只有预印本的 SoK', '你'),
    ('promoted', '已写入（本次）', '本轮写进账本', '完成'),
    ('in_directory', '已在目录', '网站上能看到', '完成'),
]
WAITING_ON_OWNER = ('review_confidence', 'held_editorial', 'review_metadata', 'screen_include')
QUEUE_LISTS = ('review_confidence', 'held_editorial', 'review_metadata', 'needs_fulltext')
RANK_LABEL = {-1: 'micro/机制设计优先', 0: '顶级', 1: '普通', 2: '预印本/未知', 3: '低优先', 9: '推迟(SSRN)'}


def esc(value):
    return html.escape('' if value is None else str(value))


def local(ts):
    return datetime.fromtimestamp(ts).strftime('%m-%d %H:%M')


def running_jobs():
    """Pipeline processes on this machine (Windows), best effort."""
    command = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='py.exe'\" | "
               "Select-Object ProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True,
                             text=True, timeout=30).stdout.strip()
        rows = json.loads(out) if out else []
    except Exception:
        return None
    rows = [rows] if isinstance(rows, dict) else rows
    jobs = []
    for row in rows:
        line = row.get('CommandLine') or ''
        if 'scripts' in line and 'status.py' not in line:
            cmd = line.split('scripts', 1)[-1].lstrip('\\/').replace('"', '')
            if all(job['cmd'] != cmd for job in jobs):  # the py launcher and its child share one command
                jobs.append({'pid': row['ProcessId'], 'cmd': cmd})
    return jobs


def cooldowns():
    rows = []
    for path in sorted(BACKOFF.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        until = data.get('retry_after_epoch') or 0
        rows.append({'source': path.stem, 'reason': data.get('reason'), 'until': until,
                     'active': until > time.time()})
    return rows


def log_tail(paths, lines=25):
    candidates = [Path(p) for p in paths] or sorted(
        list((ROOT / '.out/monthly').glob('*.txt')) + list((ROOT / '.out/monthly').glob('*/*.log')),
        key=lambda p: p.stat().st_mtime)[-1:]
    tails = []
    for path in candidates:
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()
        # Collapse identical retry lines so a stuck source shows as one row.
        collapsed = []
        for line in text:
            body = line.split('] ', 1)[-1]
            if collapsed and collapsed[-1][1] == body:
                collapsed[-1][2] += 1
                collapsed[-1][3] = line[1:9]
            else:
                collapsed.append([line, body, 1, None])
        rendered = [row[0] + (f'  ×{row[2]}（最后一次 {row[3]}）' if row[2] > 1 else '') for row in collapsed]
        tails.append({'path': str(path), 'mtime': path.stat().st_mtime, 'lines': rendered[-lines:]})
    return tails


def git_changes():
    try:
        out = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout
        ahead = subprocess.run(['git', 'rev-list', '--count', '@{u}..HEAD'], cwd=ROOT, capture_output=True,
                               text=True, timeout=30).stdout.strip()
        last = subprocess.run(['git', 'log', '-1', '--format=%h %cd %s', '--date=format:%m-%d %H:%M'], cwd=ROOT,
                              capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return None
    return {'files': [line for line in out.splitlines() if line.strip()], 'ahead': ahead, 'last': last}


def collect(log_paths):
    db = sqlite3.connect(f'file:{STORE.as_posix()}?mode=ro', uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    counts = Counter(dict(db.execute('SELECT status, COUNT(*) FROM works GROUP BY status').fetchall()))
    today = datetime.now().strftime('%Y-%m-%d')
    utc_today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    fresh = db.execute("SELECT origin, status, COUNT(*) n FROM works WHERE substr(first_seen,1,10) IN (?,?) "
                       "AND origin != 'directory' GROUP BY 1,2", (today, utc_today)).fetchall()
    by_group = defaultdict(Counter)
    lists = defaultdict(list)
    marks = ','.join('?' * len(QUEUE_LISTS))
    for row in db.execute(f'SELECT key, title, year, venue, venue_group, status, status_reason FROM works '
                          f'WHERE status IN ({marks})', QUEUE_LISTS):
        by_group[row['status']][row['venue_group'] or '未知'] += 1
        lists[row['status']].append(dict(row))
    for status, rows in lists.items():
        for row in rows:
            row['rank'] = queue_rank(row['venue'])
        rows.sort(key=lambda r: (r['rank'], -(r['year'] or 0)))
    spend = db.execute('SELECT run, COUNT(*) n, SUM(charged) c FROM llm_requests GROUP BY run ORDER BY run DESC LIMIT 6').fetchall()
    catalog = None
    if CATALOG.exists():
        data = json.loads(CATALOG.read_text(encoding='utf-8'))
        catalog = len(data.get('papers') or data.get('p') or [])
    return {
        'generated': time.time(), 'counts': counts, 'fresh': [dict(r) for r in fresh],
        'by_group': by_group, 'lists': lists, 'spend': [dict(r) for r in spend], 'catalog': catalog,
        'jobs': running_jobs(), 'cooldowns': cooldowns(), 'logs': log_tail(log_paths), 'git': git_changes(),
    }


CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e3e3e0;--bar:#4a6fa5;--warn:#b5651d;
--ok:#2e7d4f;--you:#8a3ffc;--soft:#eef1f6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#151517;--card:#1f1f22;--ink:#ececee;
--mute:#9a9aa2;--line:#33333a;--bar:#7f9fd4;--warn:#e0a060;--ok:#6cc08b;--you:#b48cff;--soft:#26282e}}
:root[data-theme="dark"]{--bg:#151517;--card:#1f1f22;--ink:#ececee;--mute:#9a9aa2;--line:#33333a;--bar:#7f9fd4;
--warn:#e0a060;--ok:#6cc08b;--you:#b48cff;--soft:#26282e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
main{max-width:1080px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 4px}
h2{font-size:16px;margin:28px 0 10px}.mute{color:var(--mute)}.card{background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:14px 16px;margin:10px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile b{display:block;font-size:24px;font-variant-numeric:tabular-nums}.tile.you b{color:var(--you)}
.tile.warn b{color:var(--warn)}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-weight:600;color:var(--mute);font-size:12px}td.n{text-align:right;white-space:nowrap}
.bar{height:10px;background:var(--bar);border-radius:3px;min-width:2px}.who{font-size:12px;white-space:nowrap}
.who.you{color:var(--you);font-weight:600}.who.auto{color:var(--ok)}.who.done{color:var(--mute)}
pre{background:var(--soft);padding:10px;border-radius:8px;overflow-x:auto;font-size:12px;margin:6px 0;white-space:pre-wrap}
details{margin:8px 0}summary{cursor:pointer;font-weight:600}.pill{display:inline-block;padding:1px 8px;border-radius:99px;
font-size:12px;background:var(--soft)}.pill.on{background:var(--warn);color:#fff}.pill.ok{background:var(--ok);color:#fff}
.scroll{overflow-x:auto}.small{font-size:12px}
"""


def who_class(who):
    if who == '你' or who.startswith('你'):
        return 'you'
    if who.startswith('自动') or who.startswith('夜里'):
        return 'auto'
    return 'done'


def render(d):
    c = d['counts']
    out = []
    add = out.append
    add(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" '
        f'content="width=device-width,initial-scale=1"><title>EcomCrypt 进度</title><style>{CSS}</style></head><body><main>')
    add(f'<h1>EcomCrypt 进度看板</h1><div class="mute">生成于 {local(d["generated"])}（本机时间）。'
        f'数据直接读自流水线数据库，不是我口述的。</div>')

    # 1. what is running now
    add('<h2>① 现在在跑什么</h2><div class="card">')
    jobs = d['jobs']
    if jobs is None:
        add('<div class="mute">查不到进程列表。</div>')
    elif not jobs:
        add('<div><span class="pill ok">空闲</span> 没有流水线脚本在运行。</div>')
    else:
        for job in jobs:
            add(f'<div><span class="pill on">运行中</span> <code>{esc(job["cmd"][:160])}</code> '
                f'<span class="mute">pid {job["pid"]}</span></div>')
    for row in d['cooldowns']:
        if row['active']:
            mins = int((row['until'] - time.time()) / 60)
            add(f'<div style="margin-top:6px"><span class="pill on">限流</span> {esc(row["source"])} 被限流'
                f'（{esc(row["reason"])}），到 {local(row["until"])} 才能再用，还有约 {mins} 分钟。</div>')
        else:
            add(f'<div class="mute small" style="margin-top:6px">{esc(row["source"])}：没有限流。</div>')
    for tail in d['logs']:
        add(f'<details open><summary>最近日志 <span class="mute small">{esc(Path(tail["path"]).name)}，'
            f'更新于 {local(tail["mtime"])}</span></summary><pre>{esc(chr(10).join(tail["lines"]))}</pre></details>')
    add('</div>')

    # 2. headline numbers
    waiting = sum(c[s] for s in WAITING_ON_OWNER)
    add('<h2>② 关键数字</h2><div class="tiles">')
    add(f'<div class="tile"><b>{d["catalog"] or c["in_directory"]:,}</b>网站上的论文</div>')
    add(f'<div class="tile you"><b>{waiting:,}</b>等你决定</div>')
    add(f'<div class="tile warn"><b>{c["needs_fulltext"]:,}</b>缺摘要，判不了</div>')
    add(f'<div class="tile"><b>{c["new"] + c["prefilter_pass"] + c["title_keep"]:,}</b>还没筛完（自动处理中）</div>')
    add(f'<div class="tile"><b>{c["venue_unknown"]:,}</b>venue 未登记（已淘汰）</div>')
    add('</div>')

    # 3. funnel
    top = max(c.values()) if c else 1
    add('<h2>③ 每篇论文走到了哪一步</h2><div class="card scroll"><table><tr><th>阶段</th><th>含义</th>'
        '<th class="n">篇数</th><th style="width:28%">规模（对数刻度）</th><th>下一步由谁</th></tr>')
    for status, label, meaning, who in STAGES:
        n = c.get(status, 0)
        width = 0 if not n else max(1.5, 100 * math.log10(n + 1) / math.log10(top + 1))
        add(f'<tr><td><b>{label}</b></td><td class="mute">{meaning}</td><td class="n">{n:,}</td>'
            f'<td><div class="bar" style="width:{width:.1f}%"></div></td>'
            f'<td class="who {who_class(who)}">{who}</td></tr>')
    other = {k: v for k, v in c.items() if k not in {s[0] for s in STAGES}}
    for status, n in other.items():
        add(f'<tr><td>{esc(status)}</td><td></td><td class="n">{n:,}</td><td></td><td></td></tr>')
    add('</table><div class="mute small" style="margin-top:6px">从上往下大致就是一篇论文经过的顺序。'
        '紫色是要你出手的，绿色是机器会自己推进的。</div></div>')

    # 4. today's intake
    if d['fresh']:
        by_origin = defaultdict(Counter)
        for row in d['fresh']:
            by_origin[row['origin'] or '-'][row['status']] += row['n']
        add('<h2>④ 今天新抓进来的</h2><div class="card scroll"><table><tr><th>来源</th><th class="n">总数</th>'
            '<th class="n">未分流</th><th class="n">已淘汰</th><th class="n">还在筛</th><th class="n">收录或等你</th></tr>')
        dropped = {'denied_venue', 'prefilter_drop', 'title_drop', 'screen_exclude', 'venue_unknown'}
        pending = {'new', 'prefilter_pass', 'title_keep', 'needs_fulltext'}
        for origin, counter in sorted(by_origin.items(), key=lambda kv: -sum(kv[1].values())):
            total = sum(counter.values())
            add(f'<tr><td>{esc(origin)}</td><td class="n">{total:,}</td><td class="n">{counter["new"]:,}</td>'
                f'<td class="n">{sum(counter[s] for s in dropped):,}</td>'
                f'<td class="n">{sum(counter[s] for s in pending - {"new"}):,}</td>'
                f'<td class="n">{total - sum(counter[s] for s in dropped | pending):,}</td></tr>')
        add('</table></div>')

    # 5. queues by group
    groups = sorted({g for s in QUEUE_LISTS for g in d['by_group'][s]},
                    key=lambda g: -sum(d['by_group'][s][g] for s in QUEUE_LISTS))
    add('<h2>⑤ 没看完的队列，按领域</h2><div class="card scroll"><table><tr><th>领域</th>')
    names = {s: label for s, label, _, _ in STAGES}
    for s in QUEUE_LISTS:
        add(f'<th class="n">{names[s]}</th>')
    add('</tr>')
    for g in groups:
        add(f'<tr><td>{esc(g)}</td>' + ''.join(f'<td class="n">{d["by_group"][s][g] or ""}</td>' for s in QUEUE_LISTS) + '</tr>')
    add('</table></div>')

    # 6. the lists themselves
    add('<h2>⑥ 队列里具体是哪些论文</h2><div class="mute small">按 venue 优先级排（micro/机制设计、顶级在前），每个队列显示前 60 篇。</div>')
    for s in QUEUE_LISTS:
        rows = d['lists'].get(s, [])
        add(f'<details><summary>{names[s]}（{len(rows)} 篇）</summary><div class="scroll"><table class="small">'
            '<tr><th>优先级</th><th>标题</th><th>年</th><th>venue</th><th>原因</th></tr>')
        for row in rows[:60]:
            add(f'<tr><td class="who">{RANK_LABEL.get(row["rank"], row["rank"])}</td><td>{esc(row["title"])}</td>'
                f'<td>{esc(row["year"])}</td><td>{esc(row["venue"])}</td>'
                f'<td class="mute">{esc((row["status_reason"] or "")[:160])}</td></tr>')
        add('</table></div></details>')

    # 7. spend and git
    add('<h2>⑦ 花费和未推送的改动</h2><div class="card">')
    if d['spend']:
        add('<table class="small"><tr><th>运行（日期）</th><th class="n">LLM 请求</th><th class="n">花费</th></tr>')
        for row in d['spend']:
            add(f'<tr><td>{esc(row["run"])}</td><td class="n">{row["n"]:,}</td><td class="n">${(row["c"] or 0) / 1e9:.2f}</td></tr>')
        add('</table>')
    git = d['git']
    if git:
        add(f'<div style="margin-top:10px">最近一次提交：<code>{esc(git["last"])}</code>'
            f'{"，还有 " + esc(git["ahead"]) + " 个提交没推送" if git["ahead"] not in ("", "0") else ""}。</div>')
        if git['files']:
            add(f'<div>{len(git["files"])} 个文件有改动还没提交：</div><pre>{esc(chr(10).join(git["files"][:30]))}</pre>')
        else:
            add('<div class="mute">没有未提交的改动。</div>')
    add('</div></main></body></html>')
    return ''.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', action='append', default=[], help='run log to show (repeatable)')
    parser.add_argument('--out', default=str(ROOT / '.out/status/index.html'))
    args = parser.parse_args(argv)
    page = render(collect(args.log))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
