"""全体成员（config.members，缺省按发言量推断）横向可比指标 → work/metrics.md（行=指标，列=人，最后一列是全群基线）。

用法：
  python3 scripts/metrics.py --project <dir> [--gap-hours 2]

指标（比例的分母见每行说明）：
  文字消息长度中位/均值、>50 字占比；连发（每个 turn 平均条数、≥3 条的 turn 占比）；
  提问/笑/@/感叹/省略号/英文/粗口/暖词/组局词：含该类特征的文字消息占比；表情：[表情] 占全部消息比例；
  生日祝福次数；凌晨(0–5点)/早晨(6–8点)发言占比；
  冷场后开话题：同群距上一条超过 --gap-hours 小时后第一个说话的次数，及占本人 turn 的比例；
  最常接谁的话：本人 turn 的上一个 turn（同群）是谁，前三名。
词表可在 config 里覆盖："metric_words": {"粗口": "正则", ...}
config.lang = "en" 时换英文词表（WORDS_EN，不分大小写），「英文」一项换成「全大写」（≥3 个大写字母的词，喊话），
长度按词数计（>50 字占比 → >30 词占比）。
"""
import collections
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import QUESTION, args, body, display, is_text, kind, load_all, members, sender_key, turns  # noqa: E402

WORDS = {
    '提问': QUESTION.pattern,
    '笑': r'哈哈|hhh|笑死|233|嘿嘿|嘻嘻|😂|🤣|\[捂脸\]|\[破涕为笑\]|\[偷笑\]|\[笑哭\]',
    '@': r'@',
    '感叹': r'[!！]',
    '省略号': r'…|\.\.\.|。。。',
    '英文': r'[A-Za-z]{2,}',
    '粗口': r'卧槽|我靠|我操|妈的|他妈|tmd|TMD|尼玛|艹|傻逼|sb|SB|fuck|shit|日了狗',
    '暖词': r'谢谢|辛苦|抱抱|加油|注意身体|保重|爱你|想你|么么|心疼|照顾好|早点休息|别太累|平安',
    '组局词': r'约|聚|吃饭|走起|组局|一起|周末|有空|出来|来不来|安排|喝酒|撸串|火锅|开黑|打球|唱歌',
}
WORDS_EN = {
    '提问': r'\?|\b(what|why|how|when|where|who|which|anyone|anybody|is it|are you|do you|did you)\b',
    '笑': r'\b(lo+l+|lmf?ao+|rofl|ha(ha)+h?|hehe+|hah|xd)\b|😂|🤣|💀|😆|😹',
    '@': r'@',
    '感叹': r'!',
    '省略号': r'…|\.\.\.',
    '全大写': r'(?-i:\b[A-Z]{3,}\b)',
    '粗口': r'\b(fuck\w*|f+k|shit\w*|damn|wtf|wth|omfg|ffs|stfu|bitch\w*|ass(hole)?s?|bullshit|crap|piss\w*|dick)\b',
    '暖词': r'\b(thanks?|thank (you|u)|ty|tysm|love (you|u|ya)|ily|miss (you|u|ya)|take care|hugs?|proud of (you|u)|get well|'
           r'congrats|congratulations|happy for (you|u)|sleep well|rest up|safe travels|xoxo|you got this)\b|❤️|♥️|🥰|🤗|🫶',
    '组局词': r'\b(meet ?up|hang ?out|dinner|lunch|brunch|drinks?|bbq|game night|anyone free|free (tonight|tmr|tomorrow|this weekend)|'
            r'this weekend|let\'?s (go|grab|get|meet|do)|who\'?s (in|down|coming)|down for|catch up|road ?trip|party|pub|bar)\b',
}
BIRTHDAY = re.compile(r'生日快乐|生快|happy birthday|Happy Birthday|HBD', re.I)


def pct(x, n):
    return f'{100 * x / n:.1f}%' if n else '-'


def main():
    a = args(__doc__, lambda p: p.add_argument('--gap-hours', type=float, default=2, help='冷场阈值（小时），默认 2'))
    cfg = a.cfg
    en = cfg.get('lang') == 'en'
    words = {k: re.compile(v, re.I if en else 0) for k, v in {**(WORDS_EN if en else WORDS), **(cfg.get('metric_words') or {})}.items()}
    size = (lambda t: len(t.split())) if en else len
    long_n, unit = (30, '词') if en else (50, '字')
    allm = load_all(a)
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    tl = turns(allm)
    # 冷场后开话题 & 接谁的话
    opens = collections.Counter()
    follows = collections.defaultdict(collections.Counter)
    nturns = collections.Counter()
    runs = collections.defaultdict(list)
    last_turn = {}
    for g, s, idx in tl:
        nturns[s] += 1
        runs[s].append(len(idx))
        pt = last_turn.get(g)
        if pt is None or (ts[idx[0]] - ts[pt[2][-1]]).total_seconds() > a.gap_hours * 3600:
            if pt is not None:
                opens[s] += 1
        else:
            follows[s][pt[1]] += 1
        last_turn[g] = (g, s, idx)

    cols = [(p, sender_key(cfg, p)) for p in members(cfg, allm)] + [('全群', None)]
    rows = collections.OrderedDict()
    for label, s in cols:
        ms = [m for m in allm if s is None or m['s'] == s]
        tx = [body(m['c']) for m in ms if is_text(m)]
        lens = [size(t) for t in tx] or [0]
        nt = len(tx)
        hrs = [int(m['t'][11:13]) for m in ms]
        rn = runs[s] if s else [x for v in runs.values() for x in v]
        tn = nturns[s] if s else sum(nturns.values())
        op = opens[s] if s else sum(opens.values())
        col = collections.OrderedDict()
        col['消息总数'] = str(len(ms))
        col['文字消息数'] = str(nt)
        col['文字长度中位数'] = str(int(statistics.median(lens)))
        col['文字长度均值'] = f'{statistics.mean(lens):.1f}'
        col[f'>{long_n}{unit}占比'] = pct(sum(x > long_n for x in lens), nt)
        col['连发：每 turn 平均条数'] = f'{statistics.mean(rn):.2f}' if rn else '-'
        col['连发：≥3条的 turn 占比'] = pct(sum(x >= 3 for x in rn), len(rn))
        for k, r in words.items():
            col[f'{k}（占文字）'] = pct(sum(bool(r.search(t)) for t in tx), nt)
        col['表情（占全部）'] = pct(sum(kind(m['c']) == '表情' for m in ms), len(ms))
        col['生日祝福次数'] = str(sum(bool(BIRTHDAY.search(t)) for t in tx))
        col['凌晨0–5点占比'] = pct(sum(h < 6 for h in hrs), len(hrs))
        col['早晨6–8点占比'] = pct(sum(6 <= h < 9 for h in hrs), len(hrs))
        col[f'冷场>{a.gap_hours:g}h后开话题次数'] = str(op)
        col['开话题占本人 turn 比例'] = pct(op, tn)
        if s:
            col['最常接谁的话'] = '、'.join(f'{display(cfg, x)}({n})' for x, n in follows[s].most_common(3))
        else:
            col['最常接谁的话'] = '-'
        for k, v in col.items():
            rows.setdefault(k, []).append(v)
    head = '| 指标 | ' + ' | '.join(c for c, _ in cols) + ' |'
    sep = '|' + '---|' * (len(cols) + 1)
    lines = [f'# 横向指标（{allm[0]["t"][:10]} ~ {allm[-1]["t"][:10]}，{len(allm)} 条消息）', '',
             'turn = 同群连续同一人的发言。比例分母：词类=本人文字消息；表情/时段=本人全部消息。', '', head, sep]
    lines += ['| ' + k + ' | ' + ' | '.join(v) + ' |' for k, v in rows.items()]
    lines += ['', '## 词表', ''] + [f'- {k}：`{r.pattern}`' for k, r in words.items()]
    (a.work / 'metrics.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(cols) - 1} 人 × {len(rows)} 项指标 → {a.work / "metrics.md"}')


if __name__ == '__main__':
    main()
