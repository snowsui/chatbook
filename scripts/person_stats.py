"""每人一份统计 → work/stats/<人>.md。

用法：
  python3 scripts/person_stats.py --project <dir> [--person 张三 ...]

内容：消息总数与各群分布、按年/按小时发言量、消息类型、常发短句（≤10字）、相对别人特别爱用的词
（2–4 字 n-gram，本人频率 / 其他人频率，按「含该词的不同消息数」计、至少 8 条——同一句话刷屏多次只算一次）、
紧挨着说话最多的人、TA 引用回复谁、谁引用回复 TA。
“有文字”的口径：去掉开头占位符后还有文字即算（`[图片] 配文` 算文字），与 split_chunks 一致。
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, body, display, is_text, kind, load_all, people, reply_to, safe, sender_key  # noqa: E402

SKIP = re.compile(r'[\s⏎，。！？、,.!?：:；;~～…“”"\'（）()\[\]【】@]')


def grams(text):
    for n in (2, 3, 4):
        for i in range(len(text) - n + 1):
            g = text[i:i + n]
            if not SKIP.search(g):
                yield g


def main():
    a = args(__doc__, lambda p: p.add_argument('--person', nargs='*', help='只处理这些人'))
    cfg = a.cfg
    allm = load_all(a)
    gm = collections.defaultdict(collections.Counter)
    allg = collections.Counter()
    seen = collections.defaultdict(set)  # 每人已计过的消息正文：同一句话重复发只算一次
    for m in allm:
        t = body(m['c'])
        if t and t not in seen[m['s']]:
            seen[m['s']].add(t)
            for g in set(grams(t)):
                gm[m['s']][g] += 1
                allg[g] += 1
    tot_all = sum(allg.values()) or 1
    replied_by = collections.defaultdict(collections.Counter)  # 被谁引用回复
    for m in allm:
        r = reply_to(m['c'])
        if r:
            replied_by[sender_key(cfg, r)][m['s']] += 1
    out = a.work / 'stats'
    out.mkdir(parents=True, exist_ok=True)
    for p in people(cfg, a.person):
        s = sender_key(cfg, p)
        idx = [i for i, m in enumerate(allm) if m['s'] == s]
        if not idx:
            print(f'{p}: 无发言，跳过')
            continue
        tm = [allm[i] for i in idx]
        years = collections.Counter(m['t'][:4] for m in tm)
        hours = collections.Counter(int(m['t'][11:13]) for m in tm)
        groups = collections.Counter(m['g'] for m in tm)
        kinds = collections.Counter(kind(m['c']) for m in tm)
        short = collections.Counter(body(m['c']) for m in tm if is_text(m) and len(body(m['c'])) <= 10)
        tot = sum(gm[s].values()) or 1
        dist = sorted(((n / tot) / ((allg[g] - n + 1) / tot_all), g, n) for g, n in gm[s].items() if n >= 8)
        my_replies = collections.Counter(sender_key(cfg, reply_to(m['c'])) for m in tm if reply_to(m['c']))
        nb = collections.Counter()
        for i in idx:
            for j in (i - 1, i + 1):
                if 0 <= j < len(allm) and allm[j]['s'] != s and allm[j]['g'] == allm[i]['g']:
                    nb[allm[j]['s']] += 1
        D = lambda x: display(cfg, x)  # noqa: E731
        lines = [
            f'# {p} 统计',
            f'- 消息总数 {len(tm)}（' + ' / '.join(f'{g} {n}' for g, n in groups.most_common()) + f'），{tm[0]["t"][:10]} ~ {tm[-1]["t"][:10]}',
            '- 按年：' + ' '.join(f'{y}:{n}' for y, n in sorted(years.items())),
            '- 按小时：' + ' '.join(f'{h}点:{hours[h]}' for h in range(24)),
            '- 消息类型：' + ' '.join(f'{k}:{n}' for k, n in kinds.most_common()),
            '- 紧挨着说话最多的人：' + '、'.join(f'{D(x)}({n})' for x, n in nb.most_common(10)),
            '- TA 最常引用回复的人：' + '、'.join(f'{D(x)}({n})' for x, n in my_replies.most_common(10)),
            '- 最常引用回复 TA 的人：' + '、'.join(f'{D(x)}({n})' for x, n in replied_by[s].most_common(10) if x != s),
            '\n## 常发短句（≤10 字）',
            ' | '.join(f'{x}×{n}' for x, n in short.most_common(50)),
            '\n## 相对别人特别爱用的词（本人频率 / 他人频率，按不同消息计，≥8 条）',
            ' | '.join(f'{g}×{n}' for _, g, n in dist[-80:][::-1]),
        ]
        (out / f'{safe(p)}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'{p}: {len(tm)} 条 → {out / (safe(p) + ".md")}')


if __name__ == '__main__':
    main()
