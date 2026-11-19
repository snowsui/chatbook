"""大群（50–500 人）选核心人物：按发言量、被回复/被点名的中心性、持续活跃月数给每位发言人打分排名 → work/core.md，
并打印建议写进 config.members / config.people 的名单。

用法：
  python3 scripts/select_core.py --project <dir> [--top 40] [--min-msgs 30] [--reply-window 10]

指标（每位发言人）：
  消息数        本人全部消息
  活跃月数      至少发过 3 条的月份数；跨度 = 首条到末条的月数
  被引用回复    别人的引用回复 `（回复 X: …）` 里 X 是 TA 的次数
  被接话        同群里 TA 的一次发言（turn）结束后 --reply-window 分钟内、紧接着由别人开口的次数（别人在接 TA 的话）
  接话人数      接过 TA 话（引用或紧接）的不同发言人数——衡量 TA 连着多少人，而不只是和一两个搭子对聊
  被点名        别人消息里出现 `@TA的称呼` 或 TA 的称呼（显示名 + aliases 反查 + config.nicknames，≥2 字）
综合分 = 六项的百分位名次平均（0–100）。
建议 members：活跃 ≥ 全程 1/4（至少 3 个月）的人按综合分依次收，直到覆盖 85% 消息，另加综合分 ≥60 的，上限 60；people 候选取其中前 1/4（3–12 人）。只算 ≥ --min-msgs 条消息的发言人；“被点名”的全文匹配只对按消息数排前 150 的人做（太慢）。

排名只是起点，不是结论：话多不等于是群的核心（可能是转发机器人、广告号、只在一段时间活跃的人），
被接话多的人才是大家在回应的人。把排名给用户看，由用户圈定 members（统计口径）和 people（要写的人）。
"""
import collections
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ME, args, display, load_all, reply_to, sender_key, turns  # noqa: E402

AT = re.compile(r'@([^\s@，,：:]{1,20})')


def extra(p):
    p.add_argument('--top', type=int, default=40, help='排名表显示前几名，默认 40')
    p.add_argument('--min-msgs', type=int, default=30, help='进入排名的最少消息数，默认 30')
    p.add_argument('--reply-window', type=float, default=10, help='「被接话」的时间窗（分钟），默认 10')


def pct_rank(values):
    """{key: value} → {key: 0–100 百分位名次}（并列取平均名次）。"""
    items = sorted(values.items(), key=lambda kv: kv[1])
    n = len(items)
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        r = (i + j) / 2
        for k in range(i, j + 1):
            out[items[k][0]] = 100 * r / (n - 1) if n > 1 else 100
        i = j + 1
    return out


def months_between(x, y):
    return (int(y[:4]) - int(x[:4])) * 12 + int(y[5:7]) - int(x[5:7]) + 1


def measure(allm, cand, names, reply_owner, window=10.0, heavy_n=150):
    """六项指标与综合分（roster.py 也用）。
    allm 的 s 是“人”的键；cand 按消息数降序；names: {键: [称呼…]}（≥2 字、非纯数字）；reply_owner(引用回复里的名字) → 键或 None。
    返回 dict：cnt first last feats score order responders。"""
    cnt = collections.Counter(m['s'] for m in allm)
    cs = set(cand)
    per_month = collections.defaultdict(collections.Counter)
    first, last = {}, {}
    for m in allm:
        s = m['s']
        if s in cs:
            per_month[s][m['t'][:7]] += 1
            first.setdefault(s, m['t'])
            last[s] = m['t']

    # 被引用回复 / 接话人
    quoted = collections.Counter()
    responders = collections.defaultdict(set)
    for m in allm:
        r = reply_to(m['c'])
        if r:
            t = reply_owner(r)
            if t in cs and t != m['s']:
                quoted[t] += 1
                responders[t].add(m['s'])

    # 被接话：按 turn，同群上一 turn 结束 window 分钟内换人开口
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    followed = collections.Counter()
    last_turn = {}
    for g, s, idx in turns(allm):
        pt = last_turn.get(g)
        if pt and pt[0] != s and pt[0] in cs and (ts[idx[0]] - ts[pt[1]]).total_seconds() <= window * 60:
            followed[pt[0]] += 1
            responders[pt[0]].add(s)
        last_turn[g] = (s, idx[-1])

    # 被点名：@称呼 + 正文出现称呼（只对前 heavy_n 名做全文匹配）
    owner = {n.lower(): s for s in cand for n in names.get(s, [])}
    named = collections.Counter()
    heavy = set(cand[:heavy_n])
    pats = {s: re.compile('|'.join(re.escape(n) for n in names[s]), re.I) for s in heavy if names.get(s)}
    for m in allm:
        c = m['c']
        hit = set()
        for at in AT.findall(c):
            s = owner.get(at.lower())
            if s:
                hit.add(s)
        body = re.sub(r'（回复 [^:：]*?: .*?）$', '', c)
        for s, p in pats.items():
            if s not in hit and p.search(body):
                hit.add(s)
        for s in hit:
            if s != m['s']:
                named[s] += 1

    feats = {
        '消息数': {s: cnt[s] for s in cand},
        '活跃月数': {s: sum(1 for v in per_month[s].values() if v >= 3) for s in cand},
        '被引用回复': {s: quoted[s] for s in cand},
        '被接话': {s: followed[s] for s in cand},
        '接话人数': {s: len(responders[s]) for s in cand},
        '被点名': {s: named[s] for s in cand},
    }
    ranks = {k: pct_rank(v) for k, v in feats.items()}
    score = {s: sum(ranks[k][s] for k in feats) / len(feats) for s in cand}
    order = sorted(cand, key=lambda s: -score[s])
    return {'cnt': cnt, 'first': first, 'last': last, 'feats': feats, 'score': score, 'order': order,
            'responders': responders, 'heavy': heavy}


def suggest(R, nmonths):
    """建议 members / people 与提示（roster.py 也用）。返回 (need_months, sug_members, sug_people, flags)。"""
    cnt, feats, score, order = R['cnt'], R['feats'], R['score'], R['order']
    cand = list(feats['消息数'])
    # 建议 members：活跃 ≥ 全程 1/4（至少 3 个月，不超过全程）的人按综合分依次收，直到覆盖候选人消息量的 85%，
    # 另加综合分 ≥ 60 的；上限 60 人。people 候选：members 前 1/4（3–12 人）。
    need_months = min(nmonths, max(3, nmonths // 4))
    steady = [s for s in order if feats['活跃月数'][s] >= need_months]
    cand_total = sum(cnt[s] for s in cand)
    sug_members, acc = [], 0
    for s in steady:
        if acc < 0.85 * cand_total or score[s] >= 60:
            sug_members.append(s)
            acc += cnt[s]
    if len(cand) <= 15:  # 小群：稳定活跃的都算
        sug_members = steady
    sug_members = sug_members[:60]
    sug_people = sug_members[:min(12, max(3, len(sug_members) // 4))]
    flags = {}
    for s in cand:
        f = []
        if feats['活跃月数'][s] < need_months:
            f.append('活跃期短')
        if order and len(cand) > 4 and cnt[s] >= cnt[order[0]] * 0.3 and feats['接话人数'][s] <= 3:  # 人太少时接话的人本来就少
            f.append('话多但少有人接（机器人/广告号？）')
        if feats['被点名'][s] == 0 and s in R['heavy']:
            f.append('没人点名')
        flags[s] = f
    return need_months, sug_members, sug_people, flags


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    allm = load_all(a)
    aliases = cfg.get('aliases') or {}
    nicks = cfg.get('nicknames') or {}
    cnt = collections.Counter(m['s'] for m in allm)
    cand = [s for s, n in cnt.most_common() if n >= a.min_msgs]
    if not cand:
        sys.exit(f'没有发言人达到 --min-msgs {a.min_msgs} 条')
    cs = set(cand)
    names = {}
    for s in cand:
        disp = display(cfg, s)
        ns = {disp} | {k for k, v in aliases.items() if v == disp} | set(nicks.get(disp, []))
        names[s] = sorted((n for n in ns if len(n) >= 2 and not n.isdigit()), key=len, reverse=True)
    R = measure(allm, cand, names, lambda r: sender_key(cfg, aliases.get(r, r)), a.reply_window)
    feats, score, order, first, last = R['feats'], R['score'], R['order'], R['first'], R['last']
    quoted, followed, named = feats['被引用回复'], feats['被接话'], feats['被点名']
    responders = R['responders']
    total = len(allm)
    nmonths = months_between(allm[0]['t'], allm[-1]['t'])
    need_months, sug_members, sug_people, flags = suggest(R, nmonths)
    flags = {s: '、'.join(f) for s, f in flags.items()}

    D = lambda s: display(cfg, s)  # noqa: E731
    lines = [f'# 核心人物排名（{allm[0]["t"][:10]} ~ {allm[-1]["t"][:10]}，{total} 条消息，{len(cnt)} 位发言人，{nmonths} 个月）', '',
             f'只排 ≥{a.min_msgs} 条消息的 {len(cand)} 人。综合分 = 下面六项百分位名次的平均（0–100）。'
             f'「活跃月数」= 发过 ≥3 条的月份数；「被接话」= TA 一次发言后 {a.reply_window:g} 分钟内别人紧接着开口的次数。', '',
             '| # | 发言人 | 综合分 | 消息数（占比） | 活跃月数/跨度 | 被引用回复 | 被接话 | 接话人数 | 被点名 | 提示 |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for i, s in enumerate(order[:a.top]):
        lines.append(f'| {i + 1} | {D(s)} | {score[s]:.0f} | {cnt[s]}（{100 * cnt[s] / total:.1f}%） | '
                     f'{feats["活跃月数"][s]}/{months_between(first[s], last[s])} | {quoted[s]} | {followed[s]} | '
                     f'{len(responders[s])} | {named[s]} | {flags[s]} |')
    cover = sum(cnt[s] for s in sug_members)
    lines += ['', '## 建议', '',
              f'- **members（统计口径）**：活跃 ≥{need_months} 个月、按综合分依次收到覆盖 85% 消息（另加综合分 ≥60）的 {len(sug_members)} 人，'
              f'覆盖全部消息的 {100 * cover / total:.0f}%。',
              '  ' + '、'.join(D(s) for s in sug_members),
              f'- **people（要写人物志的人）候选**：前 {len(sug_people)} 名。大群的人物志只写核心人物；其余人只在大事记里出现。',
              '  ' + '、'.join(D(s) for s in sug_people),
              '- 给用户看这张表，请他：去掉机器人/广告号/已退群的人；把同一个人的多个昵称并进 aliases 后重跑；'
              '确认 members 与 people。',
              '', '```json', json.dumps({'members': [D(s) for s in sug_members], 'people': [D(s) for s in sug_people]},
                                       ensure_ascii=False), '```']
    a.work.mkdir(parents=True, exist_ok=True)
    (a.work / 'core.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[4:6 + min(a.top, 15)]))
    print(f'\n建议 members {len(sug_members)} 人、people 候选 {len(sug_people)} 人 → {a.work / "core.md"}')
    if ME in cs and cfg.get('me') is None:
        print('提示：config.me 未配置，作者本人显示为 me', file=sys.stderr)


if __name__ == '__main__':
    main()
