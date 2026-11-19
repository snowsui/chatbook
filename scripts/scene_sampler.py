"""群聊戏「场景节拍表」：按各人真实的发言类型分布、单条/连发比例、“谁接谁”、冷场率抽样，逐 turn 给写手一张节拍表。
另有三个辅助模式，供“像不像”盲测（prompts/19）用：--real 截取真实片段、--pack 打乱成 A/B、--tally 统计被识破率。

用法：
  python3 scripts/scene_sampler.py --project <dir> --people A,B,C [--turns 40] [--seed 1] [--situation "..."] [--tag x]
      → work/scenes/beats-<tag>.md + beats-<tag>.json（先跑 turnmix.py）
  python3 scripts/scene_sampler.py --project <dir> --real --people A,B,C [--turns 40] [--seed 1] [--count 3] [--tag x]
      → work/scenes/real-<tag>-1.md …：互不重叠的真实片段（同一群、连续 N 个 turn、发言人都在 --people 里），
        日期换成“第N天”、正文里的年月日换成“某日”；-1 做盲测对照，其余可给评审当“熟悉这群人”的材料
  python3 scripts/scene_sampler.py --project <dir> --pack <生成.md> <真实.md> [--id b1] [--seed 1]
      → work/scenes/blind/<id>-q.md（片段 A/B，评审用）+ <id>-key.json（哪段是真的，评审不能看）
  python3 scripts/scene_sampler.py --project <dir> --tally
      → 读 work/scenes/blind/*-key.json 与同名 *-r.md（评审报告），打印并写 work/scenes/blind/summary.md

数据来源（节拍表）：
  发言类型分布、单条占比：work/turns/<人>.md（turnmix.py 产出）；若 out/personas/<人>.md 的「0.6」节有本人那一行
    的类型表（列名用 turnmix 的类别名），以人物模型为准（它可能是修订过的）；「私人频道」一句里的话题供跳线用。
  谁接谁、冷场后谁开头（及开头的钟点）、冷场率、连发条数、turn 间隔、被点名后接话率：从 work/all.json 现算（口径同 metrics.py）。
节拍里“开新线”的规则：冷场后的开头、跳线、转链接开新线；纯反应和开头后的第一句接上一句；其余 turn 七成接上一 turn
  所在的线、三成接本轮（上次冷场之后）仍在进行的另一条线（“回到前面那条线”，写手可用引用回复）。这个 0.7 是经验值，
  不是统计值。只有一个 turn、没人接的线标“落空”。
"""
import collections
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, body, display, is_pure_text, load_all, names_of, safe, sender_key, turns  # noqa: E402

CATS = ['只发图/语音', '纯反应', '转链接', '跳线', '点名他人', '追问', '讲自己', '短评', '其他']
HINT = {'只发图/语音': '只发图/语音（可配一句）', '纯反应': '纯反应：哈哈/表情/附和', '转链接': '转链接，配 ≤15 字',
        '跳线': '跳线：说自己那条线的事，与上文无共同字词', '点名他人': '点名某人（称呼或 @）', '追问': '追问/提问',
        '讲自己': '讲自己的事（含“我”）', '短评': '短评 ≤15 字', '其他': '接话长评 >15 字'}
GAP = 2 * 3600
STAY = 0.7  # 接上一 turn 所在线的概率（经验值）
LINE = re.compile(r'^\*\*(\d{1,2}:\d{2}) ([^*]+?)\*\*[:：]')
DAY = re.compile(r'^—— 第\s*\d+\s*天 ——$')
YMD = re.compile(r'\d{4}\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}\s*日?')


def extra(p):
    p.add_argument('--people', help='逗号分隔的显示名（节拍表/真实片段的出场人）')
    p.add_argument('--turns', type=int, default=40)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--situation', default='', help='情境（第一条线的话题）')
    p.add_argument('--tag', help='输出文件名后缀，默认 s<seed>')
    p.add_argument('--real', action='store_true', help='截取真实片段')
    p.add_argument('--count', type=int, default=1, help='--real：截几段（互不重叠）')
    p.add_argument('--pack', nargs=2, metavar=('GEN', 'REAL'), help='把生成片段与真实片段打乱成 A/B')
    p.add_argument('--id', help='--pack：盲测编号，默认 b<seed>')
    p.add_argument('--tally', action='store_true', help='统计 blind/ 下的盲测结果')


def pick(rnd, weights):
    """weights: {key: w}，按权重抽一个。"""
    ks = [k for k, w in weights.items() if w > 0]
    return rnd.choices(ks, [weights[k] for k in ks])[0]


def pct_cells(cells):
    return [float(c.strip().rstrip('%')) if re.fullmatch(r'\s*[\d.]+%?\s*', c) else None for c in cells]


def read_turns_md(f):
    """work/turns/<人>.md → (类型分布 {类: 份额}, 单条占比)。"""
    t = f.read_text(encoding='utf-8')
    m = re.search(r'单条占比 ([\d.]+)%', t)
    dist = {}
    for c in CATS:
        r = re.search(r'^\| %s \| ([\d.]+)%% \| (\d+) \|' % re.escape(c), t, re.M)
        if r:
            dist[c] = float(r.group(1))
    return dist, (float(m.group(1)) / 100 if m else None)


def read_persona_06(f, person):
    """out/personas/<人>.md 的 0.6 节：本人那一行的类型表（可选）+ 私人频道话题。"""
    t = f.read_text(encoding='utf-8')
    m = re.search(r'^#+\s*0\.6[^\n]*\n(.*?)(?=^#{1,2}\s)', t, re.M | re.S)
    if not m:
        return None, None, []
    sec = m.group(1)
    rows = [[c.strip() for c in ln.strip().strip('|').split('|')] for ln in sec.splitlines() if ln.strip().startswith('|')]
    dist, single = None, None
    if len(rows) >= 3:
        head = rows[0]
        for r in rows[2:]:
            if r and (person in r[0] or r[0] in ('本人', 'TA', '本人（turn）')):
                vals = pct_cells(r)
                d = {}
                for i, h in enumerate(head):  # 一列只算第一个匹配的类别（“短评/其他”记为短评）
                    c = next((c for c in CATS if c in h), None)
                    if c and c not in d and i < len(vals) and vals[i] is not None:
                        d[c] = vals[i]
                if len(d) >= 5:
                    dist = d
                    for i, h in enumerate(head):
                        if '单条' in h and i < len(vals) and vals[i] is not None:
                            single = vals[i] / 100
                break
    topics = []
    p = re.search(r'私人频道[^\n：:]*[：:]?\**[：:]?(.*?)(?:\n\s*\n|\Z)', sec, re.S)
    if p:
        txt = re.sub(r'[*`>#]|（[^）]*）|\([^)]*\)', '', p.group(1))
        for tok in re.split(r'[、，,；;/\n]|以及|和', txt):
            tok = re.sub(r'^[\s\-\d.、]+|[。.\s]+$', '', tok)
            if 1 <= len(tok) <= 12:
                topics.append(tok)
    return dist, single, topics


def group_stats(cfg, allm, keys):
    """从 all.json 现算：谁接谁、冷场后谁开头、冷场率、连发条数、间隔、被点名后接话率。"""
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    names = names_of(cfg, allm)
    tl = turns(allm)
    by_g = collections.defaultdict(list)
    for t in tl:
        by_g[t[0]].append(t)
    follows = collections.defaultdict(collections.Counter)
    opens, nturn, cold = collections.Counter(), collections.Counter(), collections.Counter()
    runs = collections.defaultdict(list)
    gaps, open_hours = [], []
    men_n, men_hit = 0, 0
    for g, tt in by_g.items():
        for i, (_, s, idx) in enumerate(tt):
            nturn[s] += 1
            if len(idx) > 1:
                runs[s].append(len(idx))
            nxt = tt[i + 1] if i + 1 < len(tt) else None
            gap = (ts[nxt[2][0]] - ts[idx[-1]]).total_seconds() if nxt else None
            if gap is None or gap > GAP:
                cold[s] += 1
            else:
                gaps.append(gap)
                follows[nxt[1]][s] += 1
            if i == 0 or (ts[idx[0]] - ts[tt[i - 1][2][-1]]).total_seconds() > GAP:
                opens[s] += 1
                open_hours.append(ts[idx[0]].hour * 60 + ts[idx[0]].minute)
            text = ' '.join(body(allm[j]['c']) for j in idx if is_pure_text(allm[j]))
            hit = [x for x, ns in names.items() if x != s and any(n in text for n in ns)]
            if hit and nxt and gap <= GAP:
                men_n += 1
                men_hit += nxt[1] in hit
    share = {k: nturn[k] / max(1, sum(nturn[x] for x in keys)) for k in keys}
    return dict(follows=follows, opens=opens, nturn=nturn, cold={k: cold[k] / nturn[k] if nturn[k] else 0.15 for k in keys},
                runs=runs, gaps=gaps or [60], open_hours=open_hours or [20 * 60],
                mention_rate=men_hit / men_n if men_n else 0.5, share=share)


def beats(a, cfg, allm, ppl):
    rnd = random.Random(a.seed)
    keys = [sender_key(cfg, p) for p in ppl]
    disp = dict(zip(keys, ppl))
    st = group_stats(cfg, allm, keys)
    prof, src = {}, {}
    for p, k in zip(ppl, keys):
        f = a.work / 'turns' / f'{safe(p)}.md'
        if not f.exists():
            sys.exit(f'找不到 {f}，先运行 turnmix.py')
        dist, single = read_turns_md(f)
        src[p] = 'work/turns'
        topics = []
        pf = a.project / 'out' / 'personas' / f'{safe(p)}.md'
        if pf.exists():
            d2, s2, topics = read_persona_06(pf, p)
            if d2:
                dist, src[p] = d2, '人物模型 0.6'
                single = s2 if s2 is not None else single
        prof[k] = dict(dist=dist, single=single if single is not None else 0.6, topics=topics)
    # 下一位发言人：P(B|A) ∝ B 接 A 的次数 + 1 × B 的份额（平滑）；冷场后的开头按“冷场后开话题”次数
    def next_speaker(prev, mentioned):
        if mentioned and rnd.random() < st['mention_rate']:
            return mentioned
        w = {b: st['follows'][b][prev] + 1 + 10 * st['share'][b] for b in keys if b != prev}
        return pick(rnd, w)

    out, lines = [], []
    t = timedelta(minutes=rnd.choice(st['open_hours']))
    prev, mentioned, cold_prev, since = None, None, True, 1
    for n in range(1, a.turns + 1):
        opener = cold_prev
        if n > 1 and cold_prev:  # 冷场后：按真实“开话题”的钟点抽，至少隔 2 小时（不会落到没人说话的凌晨）
            m = rnd.choice(st['open_hours'])
            nt = timedelta(days=t.days, minutes=m)
            t = nt if nt - t > timedelta(hours=2) else nt + timedelta(days=1)
        elif n > 1:
            t += timedelta(seconds=rnd.choice(st['gaps']))
        if opener:
            cand = {k: st['opens'][k] + 1 for k in keys if k != prev}
            s = pick(rnd, cand)
        else:
            s = next_speaker(prev, mentioned)
        pr = prof[s]
        dist = dict(pr['dist'])
        if opener:  # 冷场后的开头不会是纯反应；turnmix 也不把冷场后的开头判成跳线
            dist.pop('纯反应', None)
            dist.pop('跳线', None)
        typ = pick(rnd, dist)
        nmsg = 1 if rnd.random() < pr['single'] or not st['runs'][s] else rnd.choice(st['runs'][s])
        if typ == '只发图/语音' and nmsg == 1 and rnd.random() < 0.3:
            nmsg = 2
        if opener:
            since = n  # 冷场之后，前面的线不再续（真实里偶有隔天引用回复，量小，不抽）
        active = [ln for ln in lines if ln['turns'][-1] >= since and n - ln['last'] <= 12][-3:]
        note = []
        if opener or typ in ('跳线', '转链接') or not active:
            topic = (a.situation if not lines and a.situation else
                     ('私人频道：' + rnd.choice(pr['topics']) if typ == '跳线' and pr['topics'] else
                      '私人频道（见人物模型 0.6）' if typ == '跳线' else
                      '转的链接' if typ == '转链接' else '新话题（写手定）'))
            line = dict(id=len(lines) + 1, topic=topic, last=n, turns=[n], owner=disp[s])
            lines.append(line)
            reply_to = '—'
        else:
            prev_line = next((ln for ln in lines if out and out[-1]['line'] == ln['id']), None)
            others = [ln for ln in active if ln is not prev_line]
            stay = typ == '纯反应' or out[-1]['opener'] or rnd.random() < STAY  # 纯反应、开头后的第一句接上一句
            line = prev_line if prev_line and (stay or not others) else rnd.choice(others or active)
            last_turn = out[line['last'] - 1]
            reply_to = last_turn['speaker'] if last_turn['speaker'] != disp[s] else '自己（接着自己那条线说）'
            if line is not prev_line:
                note.append(f'回到第 {line["id"]} 条线（可用引用回复）')
            line['last'] = n
            line['turns'].append(n)
        mentioned = None
        if typ == '点名他人':
            w = {b: st['follows'][s][b] + st['follows'][b][s] + 1 for b in keys if b != s}
            mentioned = pick(rnd, w)
            note.append(f'点名 {disp[mentioned]}')
        cold_prev = n < a.turns and rnd.random() < st['cold'][s]
        if cold_prev:
            note.append('之后冷场（>2 小时没人说话）')
        out.append(dict(n=n, day=t.days + 1, time=f'{t.seconds // 3600:02d}:{t.seconds % 3600 // 60:02d}',
                        speaker=disp[s], type=typ, msgs=nmsg, line=line['id'], reply_to=reply_to,
                        opener=opener, cold_after=cold_prev, note=note))
        prev = s
    for ln in lines:
        if len(ln['turns']) == 1 and not (ln['id'] == 1 and a.situation):
            out[ln['turns'][0] - 1]['note'].append('落空：这条线没人接')
    for b in out:
        b['note'] = '；'.join(b['note'])
    return dict(people=ppl, seed=a.seed, situation=a.situation, sources=src,
                profiles={disp[k]: v for k, v in prof.items()}, cold_rate={disp[k]: round(v, 3) for k, v in st['cold'].items()},
                mention_reply_rate=round(st['mention_rate'], 3),
                lines=[{k: ln[k] for k in ('id', 'topic', 'owner', 'turns')} for ln in lines], beats=out)


def beats_md(res):
    L = [f'# 场景节拍表（{len(res["beats"])} 个 turn，seed={res["seed"]}）', '',
         f'情境：{res["situation"] or "（未指定，写手定）"}', f'出场：{"、".join(res["people"])}', '',
         '这张表是按各人真实的发言类型分布抽出来的“比例骨架”：哪一 turn 谁说、哪一类、单条还是连发、接谁、哪里冷场、哪条线落空。'
         '写手用人物模型第 4 节的声音、0.6 节的私人频道把它写成群聊（prompts/18）。可以偏离，但要在偏离说明里写理由。', '',
         '| 人 | 来源 | 单条占比 | ' + ' | '.join(CATS) + ' | 冷场率 |', '|' + '---|' * (len(CATS) + 4)]
    for p in res['people']:
        pr = res['profiles'][p]
        tot = sum(pr['dist'].values()) or 1
        L.append(f'| {p} | {res["sources"][p]} | {pr["single"]:.0%} | ' +
                 ' | '.join(f'{100 * pr["dist"].get(c, 0) / tot:.0f}%' for c in CATS) + f' | {res["cold_rate"][p]:.0%} |')
    L += ['', f'被点名后下一 turn 就是被点名者的概率：{res["mention_reply_rate"]:.0%}', '', '## 线', '']
    L += [f'- 线 {ln["id"]}（{ln["owner"]} 开）：{ln["topic"]}｜turn {",".join(map(str, ln["turns"]))}' for ln in res['lines']]
    L += ['', '## 节拍', '', '| # | 时刻 | 发言人 | 类型 | 条数 | 线 | 接谁 | 备注 |', '|---|---|---|---|---|---|---|---|']
    day = 1
    for b in res['beats']:
        if b['day'] != day:
            day = b['day']
            L.append(f'| | **第 {day} 天** | | | | | | |')
        typ = ('开头·' if b['opener'] else '') + HINT[b['type']]
        L.append(f'| {b["n"]} | {b["time"]} | {b["speaker"]} | {typ} | {b["msgs"]} | {b["line"]} | {b["reply_to"]} | {b["note"]} |')
    L += ['', '说明：时刻是建议值（按真实 turn 间隔抽样），写手可微调；“接谁”是这条线上一个说话的人，'
          '不等于一定要回复 TA——跳线、讲自己的 turn 本来就和上文无关。']
    return '\n'.join(L) + '\n'


def real(a, cfg, allm, ppl):
    rnd = random.Random(a.seed)
    keys = {sender_key(cfg, p) for p in ppl}
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    tl = turns(allm)
    by_g = collections.defaultdict(list)
    for t in tl:
        by_g[t[0]].append(t)
    cands, best = [], (0, None)
    for g, tt in by_g.items():
        for i in range(len(tt) - a.turns + 1):
            w = tt[i:i + a.turns]
            k = sum(x[1] in keys for x in w)
            if k == a.turns and len({x[1] for x in w}) >= min(len(keys), 3):
                cands.append((g, i))
            elif k > best[0]:
                best = (k, (g, i))
    if not cands:
        if not best[1]:
            sys.exit('没有足够长的片段')
        print(f'提示：找不到全由 {"、".join(ppl)} 组成的连续 {a.turns} 个 turn，退而取出场人占比最高的一段（{best[0]}/{a.turns}）',
              file=sys.stderr)
        cands = [best[1]]
    rnd.shuffle(cands)
    chosen = []
    for g, i in cands:
        if all(g != g2 or i + a.turns <= i2 or i2 + a.turns <= i for g2, i2 in chosen):
            chosen.append((g, i))
        if len(chosen) == a.count:
            break
    if len(chosen) < a.count:
        print(f'提示：只找到 {len(chosen)} 段互不重叠的片段', file=sys.stderr)
    d = a.work / 'scenes'
    d.mkdir(parents=True, exist_ok=True)
    tag = a.tag or f's{a.seed}'
    meta = []
    for no, (g, i) in enumerate(chosen, 1):
        w = by_g[g][i:i + a.turns]
        L, days, srcs = [], {}, []
        for _, s, idx in w:
            for j in idx:
                m = allm[j]
                dk = m['t'][:10]
                if dk not in days:
                    days[dk] = len(days) + 1
                    L.append(f'—— 第 {days[dk]} 天 ——')
                c = YMD.sub('某日', m['c'].replace(' ⏎ ', ' '))
                L.append(f'**{m["t"][11:16]} {display(cfg, s)}**：{c}')
                srcs.append(m['k'])
        f = d / f'real-{tag}-{no}.md'
        f.write_text('\n'.join(L) + '\n', encoding='utf-8')
        meta.append({'file': f.name, 'group': g, 'from': allm[w[0][2][0]]['t'], 'to': allm[w[-1][2][-1]]['t'],
                     'turns': len(w), 'keys': srcs})
        print(f'{f}  {len(w)} 个 turn、{len(srcs)} 条（{g} {meta[-1]["from"][:10]} ~ {meta[-1]["to"][:10]}）')
    (d / f'real-{tag}.json').write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')


def chat_lines(f):
    """取出聊天行与“第N天”分隔行，天数重编号；没有分隔行就在开头补一个。"""
    L, day = [], 0
    for ln in Path(f).read_text(encoding='utf-8').splitlines():
        ln = ln.strip()
        if DAY.match(ln):
            day += 1
            L.append(f'—— 第 {day} 天 ——')
        elif LINE.match(ln):
            if day == 0:
                day = 1
                L.append('—— 第 1 天 ——')
            L.append(ln)
    return L


def n_turns(L):
    n, prev = 0, None
    for ln in L:
        m = LINE.match(ln)
        if m and m.group(2) != prev:
            n += 1
        prev = m.group(2) if m else prev
    return n


def pack(a):
    rnd = random.Random(a.seed)
    gen, rl = chat_lines(a.pack[0]), chat_lines(a.pack[1])
    if not gen or not rl:
        sys.exit('有一份文件里没有 `**HH:MM 名字**：内容` 格式的聊天行')
    real_is_a = rnd.random() < 0.5
    A, B = (rl, gen) if real_is_a else (gen, rl)
    bid = a.id or f'b{a.seed}'
    d = a.work / 'scenes' / 'blind'
    d.mkdir(parents=True, exist_ok=True)
    q = [f'# 盲测 {bid}', '', '下面两段群聊，一段是真实聊天记录，一段是写手按人物模型写的。日期已换成“第N天”。', '',
         f'## 片段 A（{n_turns(A)} 个 turn，{sum(bool(LINE.match(x)) for x in A)} 条）', '', *A, '',
         f'## 片段 B（{n_turns(B)} 个 turn，{sum(bool(LINE.match(x)) for x in B)} 条）', '', *B, '']
    (d / f'{bid}-q.md').write_text('\n'.join(q), encoding='utf-8')
    key = {'id': bid, 'real': 'A' if real_is_a else 'B', 'gen_file': str(a.pack[0]), 'real_file': str(a.pack[1])}
    (d / f'{bid}-key.json').write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{d / (bid + "-q.md")}（给评审）  {d / (bid + "-key.json")}（答案，别给评审）')
    if abs(n_turns(A) - n_turns(B)) > max(3, n_turns(rl) // 5):
        print(f'提示：两段长度差得多（{n_turns(A)} vs {n_turns(B)} 个 turn），长度本身会成为破绽', file=sys.stderr)


def tally(a):
    d = a.work / 'scenes' / 'blind'
    rows, per = [], collections.defaultdict(lambda: {'gen': [], 'real': []})
    for kf in sorted(d.glob('*-key.json')):
        key = json.loads(kf.read_text(encoding='utf-8'))
        rf = d / f'{key["id"]}-r.md'
        if not rf.exists():
            print(f'跳过 {key["id"]}：没有 {rf.name}', file=sys.stderr)
            continue
        t = rf.read_text(encoding='utf-8')
        m = re.search(r'真实片段[:：]\s*\**\s*([AB])', t)
        if not m:
            print(f'跳过 {key["id"]}：{rf.name} 里找不到「真实片段：A/B」', file=sys.stderr)
            continue
        conf = re.search(r'把握[:：]\s*\**\s*([1-5])', t)
        rows.append((key['id'], m.group(1), key['real'], m.group(1) == key['real'], conf.group(1) if conf else '-'))
        gen_side = 'B' if key['real'] == 'A' else 'A'
        sec = re.search(r'逐人[^\n]*\n(.*?)(?=^#|\Z)', t, re.M | re.S)
        for ln in (sec.group(1) if sec else '').splitlines():
            c = [x.strip().strip('*').strip() for x in ln.strip().strip('|').split('|')]
            if len(c) >= 3 and re.fullmatch(r'[1-5]|-', c[1]) and re.fullmatch(r'[1-5]|-', c[2]):
                sc = {'A': c[1], 'B': c[2]}
                for side, lab in ((gen_side, 'gen'), (key['real'], 'real')):
                    if sc[side] != '-':
                        per[c[0]][lab].append(int(sc[side]))
    if not rows:
        sys.exit('没有可统计的盲测（需要 <id>-key.json 与 <id>-r.md）')
    hit = sum(r[3] for r in rows)
    L = ['# 盲测汇总', '', f'被识破率：{hit}/{len(rows)} = {hit / len(rows):.0%}（评审认出了哪段是真的；50% 附近 = 分不出来）', '',
         '| 编号 | 评审判为真实 | 实际真实 | 识破 | 把握 |', '|---|---|---|---|---|']
    L += [f'| {i} | {g} | {r} | {"是" if ok else "否"} | {c} |' for i, g, r, ok, c in rows]
    if per:
        L += ['', '## 逐人“像不像”（1–5，均值）', '', '| 人 | 生成片段 | 真实片段 | 差 |', '|---|---|---|---|']
        for p, v in per.items():
            g = sum(v['gen']) / len(v['gen']) if v['gen'] else None
            r = sum(v['real']) / len(v['real']) if v['real'] else None
            diff = f'{g - r:+.1f}' if g is not None and r is not None else '-'
            L.append(f'| {p} | {g if g is None else f"{g:.1f}"} | {r if r is None else f"{r:.1f}"} | {diff} |')
    L += ['', f'注：{len(rows)} 组。组数少时被识破率只能看方向：n=2 只有 0/50/100% 三种结果；'
          '要说“分不出来”，至少 10 组且识破率落在 30–70%。破绽看各 *-r.md 的「破绽」节，按出现次数归类。']
    (d / 'summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


def main():
    a = args(__doc__, extra)
    if a.tally:
        return tally(a)
    if a.pack:
        return pack(a)
    cfg = a.cfg
    if not a.people:
        sys.exit('需要 --people A,B,C')
    ppl = [p.strip() for p in re.split(r'[,，、]', a.people) if p.strip()]
    if len(ppl) < 2:
        sys.exit('--people 至少两人')
    allm = load_all(a)
    known = {display(cfg, m['s']) for m in allm}
    miss = [p for p in ppl if p not in known]
    if miss:
        sys.exit(f'all.json 里没有这些发言人：{"、".join(miss)}')
    if a.real:
        return real(a, cfg, allm, ppl)
    res = beats(a, cfg, allm, ppl)
    d = a.work / 'scenes'
    d.mkdir(parents=True, exist_ok=True)
    tag = a.tag or f's{a.seed}'
    (d / f'beats-{tag}.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    (d / f'beats-{tag}.md').write_text(beats_md(res), encoding='utf-8')
    print(f'{len(res["beats"])} 个 turn、{len(res["lines"])} 条线 → {d / f"beats-{tag}.md"}（及 .json）')


if __name__ == '__main__':
    main()
