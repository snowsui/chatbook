"""人物名单：跨所有群汇总发言人 → 编号表给用户圈定核心人物 → 写回 config。

用法：
  python3 scripts/roster.py --project <dir> build [--min-msgs 30] [--top 60]
  python3 scripts/roster.py --project <dir> apply --core 1,2,5 [--members 3,4 | --members auto]
        [--merge 3=7,8] [--split 9] [--rename 2=大爷] [--me 4] [--drop 11]   （--merge/--split/--rename 可写多次）
  多人改名：--rename 1=芳姐,2=小周（逗号/顿号分隔多对）；多组合并：--merge "3=7,8;4=9"（合并里逗号分隔成员，组与组之间用分号）。
  编号可以写 1,2,5、1-3、1、2、5、"1 2 5"，也可以直接写 roster.md 里的称呼（--core 小鹿,大熊）。

build → work/roster.json（机器读）+ work/roster.md（给用户看的编号表 + “可能同一人”建议）。
  合并规则：
  ① 同一平台账号（json-array 的 sender_id / QQ 号 / ChatLab platformId / Telegram from_id，来自 ingest 的 work/senders.json）自动合并，
     全部曾用名收进别名；ingest 后 all.json 里同一个名字的发言也视为同一人（config.aliases 已经并过的同理）。
  ② 没有账号的（txt / csv），只给“可能同一人”的建议，不自动合并：
     引用回复里被引用的名字 ↔ 被引用消息的实际发送者（有引用 ID 时按 ID，没有时在同群往前找开头相同的消息）、
     名字包含 / 编辑距离 1、同一群里一个名字不再说话后不久另一个名字开始说话（改名衔接）、
     和作者本人（json-array is_self / ChatLab ownerId）用过的名字相同或相近。两人同期在同一个群都在说话的，不建议合并。
  另外：一个名字下有两个以上账号、且在同一群同期都在说话的，提示“可能是两个人共用一个名字”（用 --split 拆开）。
  每人：编号（跨多次 build 稳定）、称呼、曾用名、各群消息数、活跃月数与首末日期、被引用回复/被接话/被点名与综合分
  （select_core.py 的口径）、是否作者本人、推荐等级：
     核心 = select_core 的 people 候选；成员 = select_core 的 members 建议，另加：≤15 人的群里活跃（≥5 条且 ≥ 该群 1%）的人、作者本人；
     其余 = 路人。只给 ≥ --min-msgs 条的人和小群活跃者打分。

apply：按编号写回 chronicle.config.json，然后重跑 ingest（名字归一生效）和 build。幂等，可多次调用。
  --core       核心人物 → config.core（“要写的人”的缺省：没写 people 时 people = core；数据页的核心成员也取它）
  --members    全体成员（统计口径）：列表 = core + 这些人 + 作者本人；auto = core + 推荐为成员的人（不含 --drop 的）。
               不写且 config 里没有 members 时按 auto；已有时保留（核心人物自动并入）。
  --merge 3=7,8  把 7、8 并进 3（名字和账号都写进 aliases，3 的称呼不变）
  --split 9    把 9 拆回各个账号（同名不同人）；每个账号按它最近的名字单独成人，重名的加（2）
  --rename 2=大爷  改称呼（旧称呼也写进 aliases；config 里 members/core/people/gender/nicknames/deep_read/me 跟着改）
  --me 4       作者本人 → config.me（有 is_self/ownerId 识别出的“本人”时，两者合并）
  --drop 11    排除（机器人、广告号、已退群的人）：从 core/members/people 去掉，auto 也不再收
"""
import collections
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ME, args, load_all, reply_to  # noqa: E402
from select_core import measure, months_between, suggest  # noqa: E402

GENERIC = {'我', 'me', 'Me', '?', '？', ''}
REPLY_Q = re.compile(r'（回复 ([^:：]*?): (.*?)）$')
LEVELS = ('核心', '成员', '路人')


def extra(p):
    p.add_argument('cmd', choices=('build', 'apply'))
    p.add_argument('--min-msgs', type=int, default=30, help='打分的最少消息数（小群活跃者不受限），默认 30')
    p.add_argument('--top', type=int, default=60, help='roster.md 最多列几人（核心/成员/作者本人总会列出），默认 60')
    p.add_argument('--core', default=None, help='核心人物编号，逗号分隔')
    p.add_argument('--members', default=None, help='成员编号（逗号分隔）或 auto')
    p.add_argument('--merge', action='append', default=[], help='3=7,8：把 7、8 并进 3；多组用分号 "3=7,8;4=9" 或写多次')
    p.add_argument('--split', action='append', default=[], help='把某编号拆回各个账号')
    p.add_argument('--rename', action='append', default=[], help='2=新称呼；多人 1=芳姐,2=小周 或写多次')
    p.add_argument('--me', default=None, help='作者本人的编号')
    p.add_argument('--drop', default=None, help='排除的编号，逗号分隔')


LOOKUP = {}  # 称呼 → 编号（apply 时填好，nums 用它把称呼换成编号）
AMBIG = {}   # 几个人用过的名字 → 编号列表（报错时提示写编号）


def nums(s):
    """'1,2,5' / '1-3' / '1、2、5' / '1 2 5' / '小鹿,大熊' → 编号列表。"""
    out = []
    for x in re.split(r'[,，、;；\s]+', str(s or '')):
        x = x.strip()
        if not x:
            continue
        m = re.fullmatch(r'(\d+)\s*[-~～—]\s*(\d+)', x)
        if m and int(m[1]) <= int(m[2]):
            out += list(range(int(m[1]), int(m[2]) + 1))
        elif x.isdigit():
            out.append(int(x))
        elif x in LOOKUP:
            out.append(LOOKUP[x])
        elif x in AMBIG:
            sys.exit(f'「{x}」有几个人用过（编号 {"、".join(map(str, AMBIG[x]))}）：写编号或 work/roster.md 里带（2）的称呼')
        else:
            sys.exit(f'认不出「{x}」：写编号（1,2,5 或 1-3）或 work/roster.md 里的称呼')
    return out


def single(s, what):
    xs = nums(s)
    if len(xs) != 1:
        sys.exit(f'{what} 只能写一个编号或称呼：{s!r}')
    return xs[0]


def norm_name(n):
    return re.sub(r'[\W_]+', '', (n or '').lower())


def edit1(x, y):
    """编辑距离 ≤ 1。"""
    if x == y:
        return True
    if abs(len(x) - len(y)) > 1:
        return False
    if len(x) > len(y):
        x, y = y, x
    i = 0
    while i < len(x) and x[i] == y[i]:
        i += 1
    return x[i + (len(x) == len(y)):] == y[i + 1:]


def day(t):
    return datetime.strptime(t[:10], '%Y-%m-%d')


# ---------------- 读数据 ----------------
class Data:
    def __init__(self, a):
        self.a, self.cfg = a, a.cfg
        self.raw_cfg = json.loads((a.project / 'chronicle.config.json').read_text(encoding='utf-8'))
        self.allm = load_all(a)
        f = a.work / 'senders.json'
        rows = None
        if f.exists():
            rows = json.loads(f.read_text(encoding='utf-8')).get('rows')
            if rows is not None and len(rows) != len(self.allm):
                rows = None
        if rows is None:
            print('提示：没有 work/senders.json（或与 all.json 对不上），先重跑 ingest.py；这次只按名字汇总，不能按账号合并。',
                  file=sys.stderr)
            rows = [[None, m['s'], None] for m in self.allm]
        self.rows = rows
        # 发言“句柄”：有账号用账号，没有用原始昵称
        self.H = [('u:' + r[0]) if r[0] else ('n:' + (r[1] or m['s'])) for m, r in zip(self.allm, rows)]
        self.kidx = {m['k']: i for i, m in enumerate(self.allm)}
        self.roster_file = a.work / 'roster.json'
        prev = json.loads(self.roster_file.read_text(encoding='utf-8')) if self.roster_file.exists() else {}
        self.prev_ids = {int(k): v for k, v in (prev.get('ids') or {}).items()}
        self.dropped = set(prev.get('dropped') or [])

    def default_partition(self):
        """并查集：同一句柄（账号）的所有消息、同一个 s（ingest 归一后的名字）的所有句柄 → 一个人。返回 {句柄: 组号}。"""
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for m, h in zip(self.allm, self.H):
            ra, rb = find(h), find('s:' + m['s'])
            if ra != rb:
                parent[ra] = rb
        roots, part = {}, {}
        for h in sorted(set(self.H)):
            part[h] = roots.setdefault(find(h), len(roots))
        return part


# ---------------- 汇总一个分组方案 ----------------
def describe(D, part, renames=None, min_msgs=30):
    """part: {句柄: 组号} → 人物列表（含指标、推荐等级、编号），以及建议、冲突。"""
    cfg, allm, rows, H = D.cfg, D.allm, D.rows, D.H
    renames = renames or {}
    gid = [part[h] for h in H]
    ents = collections.defaultdict(lambda: {'handles': set(), 'msgs': 0, 's': collections.Counter(),
                                            'raw': {}, 'groups': collections.Counter(), 'gm': collections.defaultdict(set),
                                            'gspan': {}, 'uids': set(), 'self': False, 'ref_names': collections.Counter(),
                                            'hlast': {}, 'pm': collections.Counter(),
                                            'hm': collections.defaultdict(lambda: collections.defaultdict(set))})
    for i, (m, r, h) in enumerate(zip(allm, rows, H)):
        e = ents[gid[i]]
        e['handles'].add(h)
        e['msgs'] += 1
        e['s'][m['s']] += 1
        n = r[1] or m['s']
        if n not in GENERIC:
            e['raw'][n] = m['t']
        e['hlast'][h] = (m['t'], n)
        e['groups'][m['g']] += 1
        e['gm'][m['g']].add(m['t'][:7])
        e['pm'][m['t'][:7]] += 1
        e['hm'][m['g']][h].add(m['t'][:7])
        sp = e['gspan'].get(m['g'])
        e['gspan'][m['g']] = (sp[0] if sp else m['t'], m['t'])
        if r[0]:
            e['uids'].add(r[0])
        if m['s'] == ME:
            e['self'] = True

    # 称呼 → 组号（有歧义的不收）
    owners = collections.defaultdict(set)
    for g, e in ents.items():
        for n in list(e['s']) + list(e['raw']):
            owners[n].add(g)
        if e['self']:
            owners[ME].add(g)
            if cfg.get('me'):
                owners[cfg['me']].add(g)
    for k, v in (cfg.get('aliases') or {}).items():
        for g, e in ents.items():
            if v in e['s'] or (v == cfg.get('me') and e['self']):
                owners[k].add(g)
    name_of = {n: next(iter(gs)) for n, gs in owners.items() if len(gs) == 1}

    # 引用回复：被引用的名字 ↔ 被引用消息的实际发送者
    reply_pairs = collections.Counter()
    by_group = collections.defaultdict(list)
    for i, m in enumerate(allm):
        by_group[m['g']].append(i)
    pos = {}
    for g, idx in by_group.items():
        for j, i in enumerate(idx):
            pos[i] = j
    for i, m in enumerate(allm):
        mm = REPLY_Q.search(m['c'])
        if not mm:
            continue
        x, q = mm.group(1).strip(), mm.group(2).strip()
        if x in ('', '?'):
            continue
        target = None
        ref = rows[i][2]
        if ref and ref in D.kidx:
            target = gid[D.kidx[ref]]
        elif len(norm_name(q)) >= 2:
            want = q.replace(' ⏎ ', ' ')[:20]
            idx = by_group[m['g']]
            for j in range(pos[i] - 1, max(-1, pos[i] - 300), -1):
                c = REPLY_Q.sub('', allm[idx[j]]['c']).replace(' ⏎ ', ' ')
                if c.startswith(want):
                    target = gid[idx[j]]
                    break
        if target is None:
            continue
        ex = name_of.get(x)
        if ex is None and x not in owners:
            ents[target]['ref_names'][x] += 1
        elif ex is not None and ex != target:
            reply_pairs[tuple(sorted((ex, target)))] += 1

    # 显示名
    canon = set((cfg.get('aliases') or {}).values()) | set(cfg.get('members') or []) | set(cfg.get('core') or []) \
        | set(cfg.get('people') or []) | set(cfg.get('gender') or {})
    used = collections.Counter()
    order0 = sorted(ents, key=lambda g: (-ents[g]['msgs'], min(ents[g]['handles'])))
    for g in order0:
        e = ents[g]
        if g in renames:
            name = renames[g]
        elif e['self'] and cfg.get('me'):
            name = cfg['me']
        else:
            hits = [s for s, _ in e['s'].most_common() if s != ME and s in canon]
            if hits:
                name = hits[0]
            elif e['raw']:
                name = max(e['raw'], key=lambda n: (e['raw'][n], n))
            else:
                name = next((s for s, _ in e['s'].most_common() if s != ME), '我')
        used[name] += 1
        e['name'] = name if used[name] == 1 else f'{name}（{used[name]}）'

    # 指标（select_core 口径）
    remap = [dict(m, s=f'#{gid[i]}') for i, m in enumerate(allm)]
    cnt = collections.Counter(m['s'] for m in remap)
    small_active = set()
    gtotal = collections.Counter(m['g'] for m in allm)
    gspk = {g: [x for x in ents if g in ents[x]['groups']] for g in gtotal}
    for g, xs in gspk.items():
        if len(xs) <= 15:
            for x in xs:
                n = ents[x]['groups'][g]
                if n >= 5 and n >= 0.01 * gtotal[g]:
                    small_active.add(x)
    cand = [s for s, n in cnt.most_common() if n >= min_msgs or int(s[1:]) in small_active]
    keyed = {f'#{g}': g for g in ents}
    names = {}
    for s in cand:
        e = ents[keyed[s]]
        ns = {e['name']} | set(e['raw']) | set(e['ref_names']) | set((cfg.get('nicknames') or {}).get(e['name'], []))
        ns |= {k for k, v in (cfg.get('aliases') or {}).items() if v == e['name']}
        names[s] = sorted((n for n in ns if len(n) >= 2 and not n.isdigit()), key=len, reverse=True)
    level = {}
    if cand:
        R = measure(remap, cand, names, lambda x: (f'#{name_of[x]}' if x in name_of else None))
        # 多群时间跨度不同（老 QQ 群 + 新微信群）：“全程”按消息最多的那个群算
        main_g = gtotal.most_common(1)[0][0]
        gm = [m['t'] for m in allm if m['g'] == main_g]
        nmonths = months_between(gm[0], gm[-1])
        need, sug_m, sug_p, flags = suggest(R, nmonths)
        for s in cand:
            g = keyed[s]
            e = ents[g]
            f = R['feats']
            e.update(score=round(R['score'][s]), quoted=f['被引用回复'][s], followed=f['被接话'][s],
                     responders=f['接话人数'][s], named=f['被点名'][s], months=f['活跃月数'][s], flags=flags[s])
        for s in sug_m:
            level[keyed[s]] = '成员'
        for s in sug_p:
            level[keyed[s]] = '核心'
    for g in small_active:
        level.setdefault(g, '成员')
    for g, e in ents.items():
        if e['self']:
            level.setdefault(g, '成员')
        e['level'] = level.get(g, '路人')
        e.setdefault('score', None)
        e.setdefault('flags', [])
        if 'months' not in e:
            e['months'] = sum(1 for v in e['pm'].values() if v >= 3)
        e['dropped'] = bool(e['handles'] & D.dropped)

    for g, e in ents.items():
        ts = [s for s in (e['gspan'][x] for x in e['gspan'])]
        e['first'] = min(t[0] for t in ts)
        e['last'] = max(t[1] for t in ts)

    # 冲突：一个人名下有多个账号、同群同期都在说话
    conflicts = []
    for g, e in ents.items():
        if sum(1 for h in e['handles'] if h.startswith('u:')) < 2:
            continue
        for grp, hm in sorted(e['hm'].items()):
            hs = sorted(h for h in hm if h.startswith('u:'))
            both = [(x, y) for xi, x in enumerate(hs) for y in hs[xi + 1:] if len(hm[x] & hm[y]) >= 2]
            if both:
                conflicts.append((g, grp, len(hs)))
                break

    # 建议：可能同一人（不自动合并）
    sug = collections.defaultdict(lambda: {'score': 0, 'why': []})

    def concurrent(x, y):
        return sum(len(ents[x]['gm'][grp] & ents[y]['gm'][grp]) for grp in ents[x]['gm'] if grp in ents[y]['gm'])

    for (x, y), n in reply_pairs.items():
        k = tuple(sorted((x, y)))
        sug[k]['score'] += 3
        sug[k]['why'].append(f'引用回复里 {n} 次用「{ents[x]["name"]}」或「{ents[y]["name"]}」称呼对方发的消息')
    pool = sorted(ents, key=lambda g: -ents[g]['msgs'])[:400]
    nn = {g: {norm_name(n) for n in set(ents[g]['raw']) | {ents[g]['name']}} - {''} for g in pool}
    for i, x in enumerate(pool):
        for y in pool[i + 1:]:
            hit = None
            for p in nn[x]:
                for q in nn[y]:
                    short, long_ = sorted((p, q), key=len)
                    if p == q or (len(short) >= 2 and short in long_) or (len(short) >= 3 and edit1(p, q)):
                        hit = (p, q)
                        break
                if hit:
                    break
            if not hit:
                continue
            k = tuple(sorted((x, y)))
            if ents[x]['self'] or ents[y]['self']:
                sug[k]['score'] += 3
                sug[k]['why'].append('名字和作者本人用过的名字相同或相近')
            else:
                sug[k]['score'] += 2
                sug[k]['why'].append('名字相近')
    # 改名衔接
    for grp, xs in gspk.items():
        if len(xs) > 200:
            continue
        g0, g1 = min(ents[x]['gspan'][grp][0] for x in xs), max(ents[x]['gspan'][grp][1] for x in xs)
        for x in xs:
            ax = ents[x]
            if ax['groups'][grp] < 3 or (day(g1) - day(ax['gspan'][grp][1])).days < 30:
                continue
            for y in xs:
                ay = ents[y]
                if y == x or ay['groups'][grp] < 3 or (day(ay['gspan'][grp][0]) - day(g0)).days < 30:
                    continue
                gap = (day(ay['gspan'][grp][0]) - day(ax['gspan'][grp][1])).days
                uid_x = any(h.startswith('u:') for h in ax['handles'])
                uid_y = any(h.startswith('u:') for h in ay['handles'])
                if 0 <= gap <= 45 and not (uid_x and uid_y):
                    k = tuple(sorted((x, y)))
                    sug[k]['score'] += 1
                    sug[k]['why'].append(f'{grp}：「{ax["name"]}」{ax["gspan"][grp][1][:10]} 最后一次说话，'
                                         f'{gap} 天后「{ay["name"]}」第一次说话（改名？）')
    suggestions = []
    for (x, y), v in sug.items():
        both_uid = any(h.startswith('u:') for h in ents[x]['handles']) and any(h.startswith('u:') for h in ents[y]['handles']) \
            and not (ents[x]['self'] or ents[y]['self'])
        cc = concurrent(x, y)
        if both_uid and v['score'] < 3:
            continue  # 两边都有不同账号：名字像不算数
        if cc >= 2 and v['score'] < 3:
            continue
        if v['score'] < 2 and len(gspk) and max(len(gspk[grp]) for grp in gspk) > 30:
            continue
        note = '两人同期在同一个群都在说话，更可能是外号被共用' if cc >= 2 else ''
        suggestions.append({'a': x, 'b': y, 'score': v['score'], 'why': v['why'], 'note': note, 'weak': v['score'] < 2})
    suggestions.sort(key=lambda s: (-s['score'], min(s['a'], s['b'])))
    return ents, suggestions[:40], conflicts


def number(D, ents):
    """编号跨多次 build 稳定：沿用上次含相同句柄的编号（取最小）；新出现的人按综合分接着编。返回 {组号: 编号}。"""
    claim = collections.defaultdict(list)
    for no, hs in D.prev_ids.items():
        hs = set(hs)
        for g, e in ents.items():
            if e['handles'] & hs:
                claim[g].append(no)
    out, taken = {}, set()
    for g in sorted(ents, key=lambda g: -ents[g]['msgs']):
        for no in sorted(claim.get(g, [])):
            if no not in taken:
                out[g] = no
                taken.add(no)
                break
    nxt = max(list(D.prev_ids) + [0])
    rest = sorted((g for g in ents if g not in out),
                  key=lambda g: (LEVELS.index(ents[g]['level']), -(ents[g]['score'] or -1), -ents[g]['msgs'], ents[g]['name']))
    for g in rest:
        nxt += 1
        out[g] = nxt
    return out


def resolve(D, ents, numbering, no):
    """编号 → 组号；已经并掉的旧编号按它当时的账号找到现在所在的人。"""
    for g, n in numbering.items():
        if n == no:
            return g
    hs = set(D.prev_ids.get(no) or [])
    for g, e in ents.items():
        if e['handles'] & hs:
            return g
    sys.exit(f'编号 {no} 不存在（看 work/roster.md）')


# ---------------- 输出 ----------------
def write(D, ents, suggestions, conflicts, numbering, top):
    cfg, allm, a = D.cfg, D.allm, D.a
    N = numbering
    ids = dict(D.prev_ids)
    for g, no in N.items():
        ids[no] = sorted(ents[g]['handles'])
    core, mem = set(cfg.get('core') or []), set(cfg.get('members') or [])
    people = []
    for g in sorted(ents, key=lambda g: N[g]):
        e = ents[g]
        people.append({
            'no': N[g], 'name': e['name'], 'aliases': sorted(set(e['raw']) - {e['name']}),
            'ref_names': sorted(e['ref_names']), 'groups': dict(e['groups'].most_common()), 'msgs': e['msgs'],
            'months': e['months'], 'first': e['first'], 'last': e['last'], 'score': e['score'],
            'quoted': e.get('quoted'), 'followed': e.get('followed'), 'named': e.get('named'),
            'self': e['self'], 'level': e['level'], 'dropped': e['dropped'], 'flags': e['flags'],
            'current': '核心' if e['name'] in core else '成员' if e['name'] in mem else '',
            'accounts': sorted(e['uids']), 'handles': sorted(e['handles'])})
    gstat = []
    for g in cfg.get('groups') or []:
        ms = [m for m in allm if m['g'] == g['label']]
        if not ms:
            continue
        files = g['file'] if isinstance(g.get('file'), list) else [g.get('file')]
        gstat.append({'key': g['key'], 'label': g['label'], 'msgs': len(ms), 'speakers': len({x for x in ents if g['label'] in ents[x]['groups']}),
                      'from': ms[0]['t'][:10], 'to': ms[-1]['t'][:10], 'files': len(files)})
    merged = [{'no': N[g], 'name': ents[g]['name'], 'names': sorted(set(ents[g]['raw']) | set(ents[g]['s']) - {ME}),
               'accounts': len(ents[g]['uids']), 'self': ents[g]['self']}
              for g in ents if (len(ents[g]['raw']) > 1 or len(ents[g]['uids']) > 1) and ents[g]['uids']]
    out = {'v': 1, 'groups': gstat, 'people': people,
           'suggestions': [{'a': N[s['a']], 'b': N[s['b']], 'score': s['score'], 'why': s['why'], 'note': s['note']} for s in suggestions],
           'conflicts': [{'no': N[g], 'group': grp, 'accounts': n} for g, grp, n in conflicts],
           'ids': {str(k): v for k, v in sorted(ids.items())}, 'dropped': sorted(D.dropped)}
    a.work.mkdir(parents=True, exist_ok=True)
    D.roster_file.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    L = [f'# 人物名单（{allm[0]["t"][:10]} ~ {allm[-1]["t"][:10]}，{len(allm)} 条消息，{len(ents)} 人）', '']
    L += ['## 各群', '', '| 群 | 消息 | 说过话的人 | 时间 | 导出 |', '|---|---|---|---|---|']
    L += [f'| [{g["key"]}] {g["label"]} | {g["msgs"]} | {g["speakers"]} | {g["from"]} ~ {g["to"]} | {g["files"]} 份'
          + ('（已去重合并）' if g['files'] > 1 else '') + ' |' for g in gstat]
    if merged:
        L += ['', '## 按账号自动合并的人', '']
        L += [f'- {x["no"]} 号 {x["name"]}：{" / ".join(x["names"])}'
              + ('（导出者本人，按“本人”标记合并）' if x['self'] else
                 '（同一账号）' if x['accounts'] == 1 else f'（{x["accounts"]} 个账号，同名或 aliases 里已合并）')
              for x in sorted(merged, key=lambda x: x['no'])]
    multi = len(gstat) > 1
    L += ['', '## 名单', '',
          '推荐：核心 = 建议写人物志的人；成员 = 统计、点名、横向对比用的全体成员；路人 = 只计入整体数字。'
          '「当前」= config 里已选的。被引用 / 被接话 / 被点名的口径同 select_core.py（references/12-scale-incremental.md 第三节）。', '',
          '| 编号 | 称呼 | 曾用名 | ' + ('各群消息' if multi else '消息') + ' | 活跃月 | 首末 | 被引用/被接话/被点名 | 综合分 | 推荐 | 当前 | 备注 |',
          '|---|---|---|---|---|---|---|---|---|---|---|']
    shown = [p for p in people if p['level'] != '路人' or p['self'] or p['current']]
    shown += [p for p in sorted(people, key=lambda p: -p['msgs']) if p not in shown][:max(0, top - len(shown))]
    shown.sort(key=lambda p: (LEVELS.index(p['level']), p['no']))
    for p in shown:
        gs = '、'.join(f'{k} {v}' for k, v in p['groups'].items()) if multi else str(p['msgs'])
        note = (['作者本人'] if p['self'] else []) + (['已排除'] if p['dropped'] else []) + p['flags']
        if p['ref_names']:
            note.append('被引用时叫：' + '、'.join(p['ref_names']))
        al = '、'.join(p['aliases'][:6]) + ('…' if len(p['aliases']) > 6 else '')
        mx = '/'.join('—' if p[k] is None else str(p[k]) for k in ('quoted', 'followed', 'named'))
        L.append(f'| {p["no"]} | {p["name"]} | {al} | {gs} | {p["months"]} | {p["first"][:10]} ~ {p["last"][:10]} | {mx} | '
                 f'{"—" if p["score"] is None else p["score"]} | {p["level"]} | {p["current"]} | {"；".join(note)} |')
    hidden = [p for p in people if p not in shown]
    if hidden:
        L += ['', f'另有 {len(hidden)} 位路人（合计 {sum(p["msgs"] for p in hidden)} 条）没列出，见 work/roster.json。']
    if not any(p['self'] for p in people):
        L += ['', '**没有自动认出作者本人**（txt/csv/qq/telegram 导出不带“本人”标记）：请告诉我哪个编号是你（--me）。']
    if out['suggestions']:
        L += ['', '## 可能是同一个人（没有自动合并，请确认）', '']
        for s in out['suggestions']:
            pa, pb = people[[p['no'] for p in people].index(s['a'])], people[[p['no'] for p in people].index(s['b'])]
            L.append(f'- {s["a"]} 号 {pa["name"]} ↔ {s["b"]} 号 {pb["name"]}：' + '；'.join(dict.fromkeys(s['why']))
                     + (f'（{s["note"]}）' if s['note'] else '') + f' → 是同一人就说「合并 {s["a"]}={s["b"]}」')
    if conflicts:
        L += ['', '## 可能是两个人用了同一个名字', '']
        for c in out['conflicts']:
            p = people[[x['no'] for x in people].index(c['no'])]
            L.append(f'- {c["no"]} 号 {p["name"]}：在「{c["group"]}」里有 {c["accounts"]} 个账号同期都在说话 → 是不同的人就说「拆开 {c["no"]}」')
    core_sug = [p['no'] for p in people if p['level'] == '核心' and not p['dropped']]
    L += ['', '## 请用一句话回复', '',
          f'例如（编号仅示意）：「核心 {",".join(map(str, core_sug)) or "1,2,3"}；合并 3=7；5 叫大爷；我是 4；去掉 11」。'
          '没说成员就按推荐（核心 + 推荐为成员的人 + 作者本人）。我会换成：', '',
          '```', f'python3 <skill>/scripts/roster.py --project <dir> apply --core {",".join(map(str, core_sug)) or "1,2,3"} '
          '[--members auto|3,4] [--merge "3=7;4=9"] [--rename 5=大爷,6=二哥] [--me 4] [--drop 11] [--split 9]', '```', '',
          '外号、性别、关系不从名字推断，接下来单独问。']
    (a.work / 'roster.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    return out


# ---------------- apply ----------------
def rename_pairs(specs):
    """--rename 的值 → [(编号或称呼, 新称呼)]。一个值里可用逗号/顿号/分号分隔多对（1=芳姐,2=小周），也可写多次。
    格式不对（某段没有 =、有两个 =、新称呼为空）直接报错退出，不写 config。"""
    out = []
    for spec in specs:
        for one in re.split(r'[,，、;；]', spec):
            one = one.strip()
            if not one:
                continue
            if one.count('=') != 1:
                sys.exit(f'--rename 写成 2=新称呼，多人用逗号隔开（1=芳姐,2=小周）或写多次 --rename；'
                         f'新称呼里不能有逗号、顿号、分号、等号：{spec!r}')
            no, new = (x.strip() for x in one.split('=', 1))
            if not no or not new:
                sys.exit(f'--rename 等号两边都不能为空：{spec!r}')
            out.append((no, new))
    return out


def apply(D, a):
    base = D.default_partition()
    ents, _, _ = describe(D, base, min_msgs=a.min_msgs)
    N = number(D, ents)
    R = lambda no: resolve(D, ents, N, no)  # noqa: E731
    owners = collections.defaultdict(set)
    for g, e in ents.items():
        for n in {e['name']} | set(e['raw']):
            owners[n].add(N[g])
    LOOKUP.update({n: next(iter(v)) for n, v in owners.items() if len(v) == 1})
    LOOKUP.update({e['name']: N[g] for g, e in ents.items()})  # 名单上的称呼唯一（重名已加（2）），优先按它认
    AMBIG.update({n: sorted(v) for n, v in owners.items() if len(v) > 1 and n not in LOOKUP})
    part = dict(base)
    renames, split_names, touched = {}, {}, set()
    newg = max(part.values(), default=0) + 1

    def move(src, dst):
        for h, g in part.items():
            if g == src:
                part[h] = dst

    for spec in a.merge:
        for one in re.split(r'[;；]', spec):
            if not one.strip():
                continue
            if one.count('=') != 1:
                sys.exit(f'--merge 写成 3=7,8，多组用分号隔开（3=7,8;4=9）或写多次 --merge：{one}')
            t, srcs = one.split('=', 1)
            gt = part_of(part, ents, R(single(t, '--merge 等号左边')))
            for s in nums(srcs):
                gs = part_of(part, ents, R(s))
                if gs != gt:
                    move(gs, gt)
            touched.add(gt)
    if a.me:
        gm = R(single(a.me, '--me'))
        selfg = next((g for g, e in ents.items() if e['self']), None)
        if selfg is not None and part_of(part, ents, selfg) != part_of(part, ents, gm):
            move(part_of(part, ents, selfg), part_of(part, ents, gm))
        touched.add(part_of(part, ents, gm))
    for spec in a.split:
        for no in nums(spec):
            g = R(no)
            cur = part_of(part, ents, g)
            mates = [h for h, x in part.items() if x == cur]
            if len(mates) < 2:
                print(f'{no} 号只有一个账号/名字，不用拆（跳过）')
                continue
            for h in mates:
                part[h] = newg
                split_names[newg] = ents[g]['hlast'][h][1] if h in ents[g]['hlast'] else h[2:]
                touched.add(newg)
                newg += 1
    for no, new in rename_pairs(a.rename):
        renames[part_of(part, ents, R(single(no, '--rename 等号左边')))] = new
    # 新分组方案下的人
    after, _, _ = describe(D, part, renames={**split_names, **renames}, min_msgs=a.min_msgs)
    old_name = {}  # 旧称呼 → 新称呼（rename、merge 用；被拆开的人按它第一个句柄所在的那一份）
    for g, e in ents.items():
        ng = part_of(part, ents, g)
        if e['name'] != after[ng]['name']:
            old_name[e['name']] = after[ng]['name']
    me_g = next((g for g, e in after.items() if e['self']), None)
    if a.me:
        me_g = part_of(part, ents, R(single(a.me, '--me')))

    cfg = D.raw_cfg
    aliases = dict(cfg.get('aliases') or {})
    # 改名：已有别名和名单跟着改
    for k, v in list(aliases.items()):
        if v in old_name:
            aliases[k] = old_name[v]
    me_name = after[me_g]['name'] if me_g is not None else cfg.get('me')

    def remap(xs):
        return list(dict.fromkeys(old_name.get(x, x) for x in xs or []))
    for key in ('members', 'people', 'core', 'deep_read'):
        if cfg.get(key):
            cfg[key] = remap(cfg[key])
    if (cfg.get('stats') or {}).get('core'):
        cfg['stats']['core'] = remap(cfg['stats']['core'])
    for key in ('gender', 'nicknames'):
        if cfg.get(key):
            cfg[key] = {old_name.get(k, k): v for k, v in cfg[key].items()}

    # 选择
    pick = lambda xs: [part_of(part, ents, R(n)) for n in xs]  # noqa: E731
    dropped_g = set(pick(nums(a.drop))) if a.drop else set()
    for g in dropped_g:
        D.dropped |= after[g]['handles']
    if a.core is not None:
        core_g = list(dict.fromkeys(pick(nums(a.core))))
        for g in core_g:
            D.dropped -= after[g]['handles']
        cfg['core'] = [after[g]['name'] for g in core_g]
    core_names = list(cfg.get('core') or [])
    is_dropped = lambda g: bool(after[g]['handles'] & D.dropped)  # noqa: E731
    if a.members not in (None, 'auto'):
        mem = core_names + [after[g]['name'] for g in pick(nums(a.members))]
    elif a.members == 'auto' or not cfg.get('members'):
        order = sorted(after, key=lambda g: (LEVELS.index(after[g]['level']), -(after[g]['score'] or -1), -after[g]['msgs']))
        mem = core_names + [after[g]['name'] for g in order if after[g]['level'] != '路人' and not is_dropped(g)]
    else:
        mem = list(cfg['members']) + core_names  # 已有名单保留原顺序，核心人物补在后面
    if me_name and me_g is not None and not is_dropped(me_g):
        mem.append(me_name)
    drop_names = {after[g]['name'] for g in dropped_g}
    cfg['members'] = [x for x in dict.fromkeys(mem) if x not in drop_names]
    for key in ('core', 'people'):
        if cfg.get(key):
            cfg[key] = [x for x in cfg[key] if x not in drop_names]
    if me_name and me_g is not None:
        cfg['me'] = me_name

    # 别名：要统计的人、动过的人、按账号合并过的人，把全部曾用名（和被引用时的称呼）指向称呼；有歧义的名字改用账号
    chosen = set(cfg['members']) | set(cfg.get('core') or [])
    owner = collections.defaultdict(set)
    for g, e in after.items():
        for n in set(e['raw']) | set(e['ref_names']) | (set(e['s']) - {ME}):
            owner[n].add(g)
    for g, e in after.items():
        multi = len((set(e['s']) - {ME}) | set(e['raw'])) > 1
        if not (e['name'] in chosen or g in touched or g in split_names or g in renames.keys() or multi or g == me_g):
            continue
        ambiguous = False
        for n in sorted(set(e['raw']) | set(e['ref_names']) | (set(e['s']) - {ME}) | {k for k, v in old_name.items() if v == e['name']}):
            if n == e['name'] and aliases.get(n, n) != n and len(owner[n] - {g}) == 0:
                del aliases[n]  # 自己的称呼不能再指向别人（拆开之前写过的别名）
            if n in GENERIC or n == e['name'] or re.sub(r'（\d+）$', '', n) == e['name']:
                continue  # 重名加的（2）后缀只是名单里的区分，合并回来后不用当别名
            if len(owner[n] - {g}) == 0:
                aliases[n] = e['name']
            else:
                ambiguous = True
                if aliases.get(n) == e['name']:
                    del aliases[n]
        if ambiguous or g in split_names:
            for u in sorted(e['uids']):
                aliases[u.split(':', 1)[1]] = e['name']
    if aliases:
        cfg['aliases'] = aliases
    (D.a.project / 'chronicle.config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # 编号：新分组的人沿用编号
    D.prev_ids = {**D.prev_ids, **{no: sorted(ents[g]['handles']) for g, no in N.items()}}
    D.roster_file.write_text(json.dumps({'ids': {str(k): v for k, v in D.prev_ids.items()}, 'dropped': sorted(D.dropped)},
                                        ensure_ascii=False), encoding='utf-8')
    print(f'已写回 config：core {len(cfg.get("core") or [])} 人，members {len(cfg["members"])} 人'
          + (f'，作者本人 {cfg["me"]}' if cfg.get('me') else '') + f'，aliases {len(aliases)} 条')
    sys.stdout.flush()
    r = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'ingest.py'), '--project', str(D.a.project)],
                       stdout=subprocess.DEVNULL)
    if r.returncode:
        sys.exit('重跑 ingest 失败')


def part_of(part, ents, g):
    """原来的组号 g → 当前分组方案里的组号（g 的任一句柄所在）。"""
    return part[next(iter(sorted(ents[g]['handles'])))]


def build(a):
    D = Data(a)
    ents, sugs, conflicts = describe(D, D.default_partition(), min_msgs=a.min_msgs)
    N = number(D, ents)
    out = write(D, ents, sugs, conflicts, N, a.top)
    lv = collections.Counter(p['level'] for p in out['people'])
    cur = collections.Counter(p['current'] for p in out['people'])
    chosen = f'当前已选：核心 {cur["核心"]}、成员 {cur["成员"] + cur["核心"]}（含核心）；' if a.cfg.get('core') else ''
    print(f'{len(out["people"])} 人。{chosen}推荐：核心 {lv["核心"]}、成员 {lv["成员"]}、路人 {lv["路人"]}；'
          f'可能同一人 {len(out["suggestions"])} 组，同名多账号 {len(out["conflicts"])} 处 → {a.work / "roster.md"}')


def main():
    a = args(__doc__, extra)
    if a.cmd == 'apply':
        apply(Data(a), a)
        a = args(__doc__, extra)  # 重新读 config
    build(a)


if __name__ == '__main__':
    main()
