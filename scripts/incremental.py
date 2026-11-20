"""增量更新：重新导出后，只为新增/变化的月份重做大事记，不动已冻结、已修订过的月份。

用法：
  python3 scripts/incremental.py --project <dir>                 # 重跑 ingest → 对比 → 为新增/变化月份准备分段 → 登记任务
  python3 scripts/incremental.py --project <dir> --skip-ingest   # all.json 已是最新时
  python3 scripts/incremental.py --project <dir> --dry-run       # 只报告，不写分段、不登记
  python3 scripts/incremental.py --project <dir> --merge-tail    # 尾部增量的事件抽完后：并进 stable/
  python3 scripts/incremental.py --project <dir> --commit        # 一轮做完后：把当前各月状态记为基线
  python3 scripts/incremental.py --project <dir> --stats 2024-01 # 写某月（或某年 2024）的群报统计 → work/digest/

基线 work/incremental.json 按“群 × 月”记，由 --commit 写入：
  {"version": 2, "updated": 记基线的时间,
   "groups": {群 key: {"label": 群名, "last": 该群整理到的最后一条消息时间,
                       "months": {月: {n 消息数, first, last 首末条时间, fp 稳定键指纹}}}}}
各群分开记，所以几个群各自同步到不同时间点、或中途新接入一个群，都只读各群自己的新增部分。
旧版基线（按月、各群混在一起）会自动换算成按群，下次 --commit 存成新版。
第一次在已有项目上用：先用做 stable/ 时的那份导出跑一次 --commit 建基线。没有基线时脚本只推测 stable/ 里最晚的那个月：
该月最晚的 ref 之后还有 ≥ --bootstrap-min 条文字消息才算“末尾有新增”（事件不一定覆盖到月底，所以可能误报），更早的月份视为完整。

月份分三类（stable/ 里有的月份逐群比对：某群旧消息没变、只多了新的 → 该群取新增；任何一个群的旧消息变了 → 整月 changed）：
  new      stable/ 里没有 → 整月照常 split_chunks（分段写 work/chunks/<月>_p<i>.txt），走 01 → 02 → check_events → freeze。
  tail     stable/ 里有、各群旧消息都没变、只是有群多了消息 → 只把新增消息（各群在自己的 last 之后；
           基线里这个月没有的群 = 新接入，取它本月全部）写成 work/chunks/<月>_tail_p<i>.txt，
           抽取结果进 part_events/<月>_tail_p<i>.json，再用 --merge-tail 追加到 stable/ 末尾
           （不重排，已有事件的下标不变，修订清单 E:月份-序号、top10.json 继续有效；页面按日期排序显示）。
  changed  stable/ 里有、但旧消息也变了（重新导出补了之前漏掉的消息、改了昵称归一等）→ 整月重新 split；
           重新冻结会覆盖该月的修订，脚本只打印做法，不自动删除 stable/ 文件。
work/state.json 存在时（项目用 pipeline.py 编排）通过 pipeline.register() 登记任务（同一格式）：
  新月份 / changed 月份的分段照常出现在 pipeline 的 read 阶段（自动推导，不另登记）；
  尾部分段登记为 incremental 阶段的 extract:<月>_tail_p<i>（01 抽事件）和 merge-tail:<月>（脚本），之后用 pipeline next 派。
state.json 不存在就只打印要跑的命令。
"""
import collections
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, display, kind, load_all  # noqa: E402

HERE = Path(__file__).resolve().parent
SKIP_LINE = ('[图片]', '[表情]')


def extra(p):
    p.add_argument('--skip-ingest', action='store_true', help='不重跑 ingest（all.json 已是最新）')
    p.add_argument('--dry-run', action='store_true', help='只报告，不写分段、不登记任务')
    p.add_argument('--max-chars', type=int, default=50000, help='每段最大字数，传给分段，默认 50000')
    p.add_argument('--bootstrap-min', type=int, default=10, help='没有基线时，尾部至少多少条文字消息才算有新增，默认 10')
    p.add_argument('--merge-tail', action='store_true', help='把 part_events/<月>_tail_*.json 并进 stable/')
    p.add_argument('--commit', action='store_true', help='把当前 all.json 的各月状态写成基线 work/incremental.json')
    p.add_argument('--stats', metavar='YYYY-MM|YYYY', help='写群报统计 → work/digest/<期>-stats.md')


def fp(keys):
    return hashlib.sha1('\n'.join(keys).encode('utf-8')).hexdigest()[:16]


def gkey(m):
    """群 key：稳定键 k 的前缀（A:123 → A）。群名可能改，key 不变。"""
    return m['k'].split(':', 1)[0]


def summarize(ms):
    return {'n': len(ms), 'first': ms[0]['t'], 'last': ms[-1]['t'], 'fp': fp([m['k'] for m in ms])}


def month_stats(allm):
    """返回 ({群 key: {月: 统计}}, {月: [消息]}, {群 key: 群名})。"""
    by = collections.defaultdict(list)
    byg = collections.defaultdict(lambda: collections.defaultdict(list))
    labels = {}
    for m in allm:
        by[m['t'][:7]].append(m)
        byg[gkey(m)][m['t'][:7]].append(m)
        labels[gkey(m)] = m['g']
    return {g: {mon: summarize(ms) for mon, ms in d.items()} for g, d in byg.items()}, by, labels


def load_json(p, default):
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else default


def stable_last_ref(a, mon, kt):
    d = load_json(a.work / 'stable' / f'{mon}.json', {'events': []})
    ts = [kt[r] for e in d['events'] for r in e.get('refs') or [] if r in kt]
    return max(ts) if ts else None


def load_base(a, by):
    """读基线 → {群 key: {月: 统计}}；没有基线返回 None。
    旧版基线（按月、各群混在一起）就地换算：该月 last 之前的消息条数和指纹对得上就按群拆开，对不上的月份不记（会判成 changed）。"""
    d = load_json(a.work / 'incremental.json', None)
    if d is None:
        return None
    if 'groups' in d:
        return {g: x['months'] for g, x in d['groups'].items()}
    out = collections.defaultdict(dict)
    for mon, b in d.get('months', {}).items():
        old = [m for m in by.get(mon, []) if m['t'] <= b['last']]
        if len(old) != b['n'] or fp([m['k'] for m in old]) != b['fp']:
            continue
        gs = collections.defaultdict(list)
        for m in old:
            gs[gkey(m)].append(m)
        for g, ms in gs.items():
            out[g][mon] = summarize(ms)
    print('提示：基线是旧版（各群混在一起），已按群换算；这一轮做完 --commit 会存成新版。')
    return dict(out)


def classify(a, allm):
    cur, by, labels = month_stats(allm)
    base = load_base(a, by)
    stable = {f.stem for f in (a.work / 'stable').glob('*.json')}
    kt = {m['k']: m['t'] for m in allm}
    plan = []  # (月份, 类别, {群 key: 截止时间，None = 该群本月全部}, 说明)
    if base is None:
        print('警告：没有基线 work/incremental.json，只推测 stable/ 最晚那个月的尾部新增（建议做完这一轮后跑 --commit）。')
    for mon in sorted(by):
        if mon not in stable:
            plan.append((mon, 'new', None, f'{len(by[mon])} 条'))
            continue
        if base is not None:
            if not any(mon in bg for bg in base.values()):
                plan.append((mon, 'changed', None, '有 stable 但基线里没有这个月'))
                continue
            cuts, notes, bad = {}, [], []
            for g in sorted(set(cur) | set(base)):
                c, b = cur.get(g, {}).get(mon), base.get(g, {}).get(mon)
                name = labels.get(g, g)
                if b == c:
                    continue
                if c is None:
                    bad.append(f'{name}：基线有 {b["n"]} 条，这次没有了')
                elif b is None:
                    cuts[g] = None
                    notes.append(f'{name}：新接入，本月 {c["n"]} 条')
                else:
                    old = [m for m in by[mon] if gkey(m) == g and m['t'] <= b['last']]
                    if len(old) == b['n'] and fp([m['k'] for m in old]) == b['fp']:
                        cuts[g] = b['last']
                        notes.append(f'{name}：旧 {b["n"]} 条不变，{b["last"]} 之后新增 {c["n"] - b["n"]} 条')
                    else:
                        bad.append(f'{name}：旧 {b["n"]} 条 → 现 {c["n"]} 条，旧消息也有变化')
            if bad:
                plan.append((mon, 'changed', None, '；'.join(bad)))
            elif cuts:
                plan.append((mon, 'tail', cuts, '；'.join(notes)))
        elif mon == max(stable):  # 没有基线：只推测 stable 里最晚的那个月（上次导出多半截在这个月中间），更早的月份视为完整
            last = stable_last_ref(a, mon, kt)
            if last is None:
                continue
            tail = [m for m in by[mon] if m['t'] > last and kind(m['c']) == '文字']
            if len(tail) >= a.bootstrap_min:
                plan.append((mon, 'tail', {g: last for g in cur if mon in cur[g]},
                             f'（推测）stable 最晚 ref {last} 之后有 {len(tail)} 条文字消息'))
    gone = sorted({mon for bg in (base or {}).values() for mon in bg} - set(by))
    for mon in gone:
        print(f'警告：{mon} 在基线里有、这次导出里没有了——导出不全？先别 commit。')
    return plan, by


def write_tail(a, mon, msgs, cuts):
    tail = [m for m in msgs if gkey(m) in cuts and (cuts[gkey(m)] is None or m['t'] > cuts[gkey(m)])]
    labels = {gkey(m): m['g'] for m in msgs}
    since = '、'.join(f'{labels[g]} 本月全部（新接入）' if c is None else f'{labels[g]} {c} 之后' for g, c in sorted(cuts.items()))
    lines = ['%s|%s|%s|%s: %s' % (m['id'], m['g'], m['t'][8:16], m['s'], m['c']) for m in tail if m['c'] not in SKIP_LINE]
    parts, cur, size = [], [], 0
    for line in lines:
        if size + len(line) > a.max_chars and cur:
            parts.append(cur)
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        parts.append(cur)
    names = []
    for i, p in enumerate(parts):
        name = f'{mon}_tail_p{i + 1}.txt'
        head = ('月份 %s（增量尾部 %d/%d，新消息：%s；%s 至 %s 日）。本月此前已整理，这里只有新增部分：%d 条消息，去掉纯图片/表情后 %d 行；'
                '本文件 %d 条（共 %d 行，含 3 行文件头）。\n'
                '输出写 work/part_events/%s.json（不要写 work/events/）；跨到旧消息的事件只写新增部分，旧部分已收过。\n\n') % (
            mon, i + 1, len(parts), since, p[0].split('|')[2][:2], p[-1].split('|')[2][:2], len(tail), len(lines),
            len(p), len(p) + 3, name[:-4])
        (a.work / 'chunks' / name).write_text(head + '\n'.join(p), encoding='utf-8')
        names.append(name)
    return names


def split_months(a, months):
    """调用 split_chunks 切 [min, max] 区间，再删掉不在目标里的月份（split_chunks 会先清空 chunks/）。"""
    if not months:
        return []
    subprocess.run([sys.executable, str(HERE / 'split_chunks.py'), '--project', str(a.project), '--max-chars',
                    str(a.max_chars), '--from', min(months), '--to', max(months)], check=True, stdout=subprocess.DEVNULL)
    keep = []
    for f in sorted((a.work / 'chunks').glob('*.txt')):
        if f.name[:7] in months and '_tail_' not in f.name:
            keep.append(f.name)
        elif f.name[:7] not in months:
            f.unlink()
    return keep


def register(a, tasks):
    """项目在用 pipeline 编排（有 work/state.json）时，用 pipeline 的接口登记任务。"""
    if not (a.work / 'state.json').exists():
        return False
    import pipeline  # noqa: E402
    pipeline.register(a.project, a.cfg, tasks)
    return True


def run_plan(a):
    if not a.skip_ingest:
        print('重跑 ingest …', flush=True)
        subprocess.run([sys.executable, str(HERE / 'ingest.py'), '--project', str(a.project)], check=True)
    allm = load_all(a)
    plan, by = classify(a, allm)
    if not plan:
        print('没有新增或变化的月份。')
        return
    print('\n| 月份 | 类别 | 说明 |\n|---|---|---|')
    for mon, cat, _, why in plan:
        print(f'| {mon} | {cat} | {why} |')
    if a.dry_run:
        return
    (a.work / 'chunks').mkdir(parents=True, exist_ok=True)
    full = [mon for mon, cat, _, _ in plan if cat in ('new', 'changed')]
    files = split_months(a, full)
    for mon, cat, cuts, _ in plan:
        if cat == 'tail':
            files += write_tail(a, mon, by[mon], cuts)
    files.sort()
    changed = [mon for mon, cat, _, _ in plan if cat == 'changed']
    tails = [mon for mon, cat, _, _ in plan if cat == 'tail']
    skill, proj = shlex.quote(str(HERE.parent)), shlex.quote(str(a.project))
    cmds = [f'# 1) 事件抽取（并行，每个子任务几个文件）：',
            f'python3 {skill}/scripts/fill_prompt.py --project {proj} --prompt 01 --files {" ".join(files)} --out work/prompts/01-inc.md',
            '# 2) 有多段的新月份用 02 合并；然后机检：',
            f'python3 {skill}/scripts/check_events.py --project {proj}',
            f'python3 {skill}/scripts/freeze.py --project {proj}   # 只冻结新月份（已有 stable 的会跳过）']
    if tails:
        cmds.append(f'python3 {skill}/scripts/incremental.py --project {proj} --merge-tail   # 尾部增量并进 stable：{"、".join(tails)}')
    if changed:
        cmds.append(f'# changed 月份（{"、".join(changed)}）：先把 work/stable/<月>.json 挪到 work/stable.bak/（修订会丢，'
                    '必要时对照旧文件重做修订），再跑 freeze。')
    cmds += [f'python3 {skill}/scripts/build_chronicle.py --project {proj}',
             f'python3 {skill}/scripts/incremental.py --project {proj} --commit   # 一轮做完后记基线',
             '# 可选：月报/年报',
             *[f'python3 {skill}/scripts/incremental.py --project {proj} --stats {m} && '
               f'python3 {skill}/scripts/fill_prompt.py --project {proj} --prompt 17-monthly --months {m} --out work/prompts/17-{m}.md'
               for m in sorted({mon for mon, _, _, _ in plan})]]
    print(f'\n已准备 {len(files)} 个分段 → {a.work / "chunks"}：{"、".join(files)}')
    tasks = [{'id': f'extract:{f[:-4]}', 'step': 'extract', 'prompt': '01', 'files': [f]} for f in files if '_tail_' in f]
    tasks += [{'id': f'merge-tail:{m}', 'step': 'merge-tail', 'months': [m]} for m in tails]
    if register(a, tasks):
        print(f'已登记进 {a.work / "state.json"}：尾部任务 {len(tasks)} 个；新月份分段在 read 阶段。'
              f'接下来用 pipeline.py --project {proj} status / next 派任务，全部做完后：')
        cmds = [c for c in cmds if '--commit' in c or c.startswith('# changed') or '月报' in c or '--stats' in c]
    print('\n接下来：\n' + '\n'.join(cmds))


def merge_tail(a):
    allm = load_all(a)
    idk = {m['id']: m['k'] for m in allm}
    pos = {m['k']: i for i, m in enumerate(allm)}
    parts = collections.defaultdict(list)
    for f in sorted((a.work / 'part_events').glob('*_tail_p*.json')):
        parts[f.name[:7]].append(f)
    if not parts:
        sys.exit('work/part_events/ 下没有 <月>_tail_p*.json')
    done_dir = a.work / 'part_events' / 'merged'
    for mon, fs in sorted(parts.items()):
        sp = a.work / 'stable' / f'{mon}.json'
        st = load_json(sp, None)
        if st is None:
            print(f'{mon}: stable 里没有这个月，跳过（新月份走正常 freeze）')
            continue
        old_n = len(st['events'])
        old_keys = {r for e in st['events'] for r in e.get('refs') or []}
        old_days = [datetime.strptime(e['date'], '%Y-%m-%d') for e in st['events'] if e.get('date')]
        added = miss = 0
        near = []
        for f in fs:
            d = json.loads(f.read_text(encoding='utf-8'))
            for e in d.get('events') or []:
                refs = e.get('refs') or []
                miss += sum(r not in idk for r in refs)
                e['refs'] = sorted((idk[r] for r in refs if r in idk), key=pos.get)
                if not e['refs'] or set(e['refs']) & old_keys:
                    continue
                st['events'].append(e)
                added += 1
                if e.get('date') and any(abs((datetime.strptime(e['date'], '%Y-%m-%d') - d).days) <= 3 for d in old_days):
                    near.append(e.get('title'))
        # 不重排：新接入的群可能带来比旧事件更早的事件，重排会让旧事件下标变（修订清单、top10.json 失效）；页面按日期排序显示
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
        done_dir.mkdir(parents=True, exist_ok=True)
        for f in fs:
            f.rename(done_dir / f.name)
        print(f'{mon}: 原 {old_n} 个事件 + 新增 {added} 个' + (f'，{miss} 个 ref 找不到已丢弃' if miss else '')
              + (f'；和某个旧事件相隔 3 天内的（可能是同一件，请人工看）：{"、".join(near)}' if near else '')
              + '；month_summary 未改，需要的话用 apply_fixes 改 M:' + mon)


def commit(a):
    allm = load_all(a)
    cur, by, labels = month_stats(allm)
    stable = {f.stem for f in (a.work / 'stable').glob('*.json')}
    base = load_base(a, by) or {}
    for mon in sorted(set(by) & stable):  # 这次导出里有的月份按当前状态重记（不在导出里的月份保留旧基线）
        for g in set(cur) | set(base):
            if mon in cur.get(g, {}):
                base.setdefault(g, {})[mon] = cur[g][mon]
            else:
                base.get(g, {}).pop(mon, None)
    groups = {g: {'label': labels.get(g, g), 'last': max(x['last'] for x in ms.values()), 'months': dict(sorted(ms.items()))}
              for g, ms in sorted(base.items()) if ms}
    out = {'version': 2, 'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'groups': groups}
    (a.work / 'incremental.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    missing = sorted(set(by) - stable)
    print(f'基线已更新 → {a.work / "incremental.json"}：'
          + '；'.join(f'{x["label"]} {len(x["months"])} 个月、整理到 {x["last"]}' for x in groups.values())
          + (f'；这些月份还没进 stable，未记入：{"、".join(missing)}' if missing else ''))
    left = sorted((a.work / 'part_events').glob('*_tail_p*.json'))
    if left:
        print('警告：part_events 里还有没并入的尾部增量：' + '、'.join(f.name for f in left))


def stats(a, period):
    cfg = a.cfg
    allm = load_all(a)
    ms = [m for m in allm if m['t'].startswith(period)]
    if not ms:
        sys.exit(f'{period} 没有消息')
    yearly = len(period) == 4
    if yearly:
        prev = str(int(period) - 1)
    else:
        y, mo = int(period[:4]), int(period[5:7])
        prev = '%04d-%02d' % ((y - 1, 12) if mo == 1 else (y, mo - 1))
    pn = sum(1 for m in allm if m['t'].startswith(prev))
    spk = collections.Counter(m['s'] for m in ms)
    days = collections.Counter(m['t'][:10] for m in ms)
    hours = collections.Counter(int(m['t'][11:13]) for m in ms)
    kinds = collections.Counter(kind(m['c']) for m in ms)
    night = sum(1 for m in ms if int(m['t'][11:13]) < 6)
    months = sorted({m['t'][:7] for m in ms})
    evs = []
    for mon in months:
        d = load_json(a.work / 'stable' / f'{mon}.json', None)
        if d:
            for i, e in enumerate(d['events']):
                evs.append((mon, i, e, d.get('month_summary', '')))
    pc = collections.Counter(p for _, _, e, _ in evs for p in e.get('people') or [])
    D = lambda s: display(cfg, s)  # noqa: E731
    lines = [f'# {period} 群报统计（只含计数，不含原文）', '',
             f'- 消息 {len(ms)} 条（上一期 {prev}：{pn} 条，{"+" if len(ms) >= pn else ""}{len(ms) - pn}），{len(spk)} 人发言，'
             f'活跃 {len(days)} 天',
             '- 发言最多：' + '、'.join(f'{D(s)} {n}' for s, n in spk.most_common(8)),
             '- 最热的几天：' + '、'.join(f'{d} {n} 条' for d, n in days.most_common(5)),
             f'- 最热的钟点：{hours.most_common(1)[0][0]} 点；凌晨 0–5 点 {night} 条',
             '- 消息类型：' + '、'.join(f'{k} {n}' for k, n in kinds.most_common(6)),
             f'- 大事记事件 {len(evs)} 个；出镜最多：' + ('、'.join(f'{p} {n}' for p, n in pc.most_common(6)) or '（无）')]
    if not evs:
        lines.append('- 注意：stable/ 里还没有这一期的事件，群报只能写统计；先做完大事记再写。')
    if yearly:
        mc = collections.Counter(m['t'][:7] for m in ms)
        lines += ['', '## 各月', '', '| 月份 | 消息数 | 事件数 | month_summary |', '|---|---|---|---|']
        for mon in months:
            ne = sum(1 for x in evs if x[0] == mon)
            summ = next((x[3] for x in evs if x[0] == mon), '')
            lines.append(f'| {mon} | {mc[mon]} | {ne} | {summ} |')
        lines += ['', '## 热度 3 的事件', ''] + [f'- E:{mon}-{i} {e.get("date")} {e.get("title")}' for mon, i, e, _ in evs
                                               if e.get('heat') == 3]
    out = a.work / 'digest'
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{period}-stats.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{period}: {len(ms)} 条、{len(evs)} 个事件 → {out / (period + "-stats.md")}')


def main():
    a = args(__doc__, extra)
    if a.merge_tail:
        merge_tail(a)
    elif a.commit:
        commit(a)
    elif a.stats:
        stats(a, a.stats)
    else:
        run_plan(a)


if __name__ == '__main__':
    main()
