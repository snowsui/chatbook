"""流程编排：在项目目录的 work/state.json 里记每个阶段、每个任务单元（分段/月份/人）的进度，跨会话接着干。

用法：
  python3 scripts/pipeline.py --project <dir> status                 进度表 + 下一步建议
  python3 scripts/pipeline.py --project <dir> next [--limit 8] [--peek] [--batch-lines 1000]
        列出下一批可派的任务（子任务数受 --limit 并发上限约束，已在 doing 的也占名额）：
        任务 id、用哪份 prompt、填说明的完整命令、模型建议 cheap/strong、产出路径；
        列出的任务记为 doing、尝试次数 +1（--peek 只看不记）。
        read 阶段把相邻的短分段合成一批派给一个子任务（合计不超过 --batch-lines 行，默认 1000；0 = 不合批，
        一段一个任务）：一条 fill_prompt --files 带多个分段，判定仍按每个分段各自的产出。补读剩余行的分段不合批。
  python3 scripts/pipeline.py --project <dir> mark <任务> done|failed [--note 说明]
  python3 scripts/pipeline.py --project <dir> reset <任务或阶段>      回到 todo、尝试次数清零

自动判定：每次运行都会检查产出文件——产出存在且通过机检就自动标 done（不用手动 mark）；
产出存在但机检不过 → failed（附原因）；done 的产出被删了或上游更新了 → 回到 todo。
手动 `mark done` 的任务不再自动改（用于确实没法机检、你已人工确认的情况）。
reset 只清状态；产出文件还在且机检通过的话，下次运行又会自动标 done——要重做就先删/挪走产出。

增量更新（incremental.py）：新月份的分段照常出现在 read 阶段；尾部增量（<月>_tail_p<i>）不进 read，
由 incremental.py 调本脚本的 register() 登记成 incremental 阶段的任务（extract:<分段> 用 01 抽事件 →
part_events/<分段>.json；merge-tail:<月> 跑 incremental.py --merge-tail），这些任务跨运行保留、同样自动判定。

档位（config.tier，缺省 standard；--tier 可临时覆盖）：
  lite      只做大事记：read 用 prompts/01（便宜模型抽事件）
  standard  大事记 + 人物志 + 一轮验证：read 用 prompts/00 统一阅读（事件 + 人物证据一次读完）、
            统计与日常基线、小传（带引语出处标注，verify_citations 机检）、总编终审
  deep      全流程：再加人物模型、独立审稿、盲测、一轮修订、小传回修、群像总览
可选：config.deep_read = ["发言极多的人"]，为这些人另做专人深读（prompts/07，按人切块逐行读），写作/建模时一起读。
阶段顺序与依赖写死在 STAGES 里（先日常 person-stats/baseline 再写作建模）；所有中间产物都在项目目录 work/、out/ 下。
pipeline 只管上面这些阶段；小剧场、数据页、本人确认、分享卡片、站点打包、增量、群聊戏按各自文档手动跑。
"""
import json
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, safe  # noqa: E402

SK = Path(__file__).resolve().parent
ALL, SD, D = ('lite', 'standard', 'deep'), ('standard', 'deep'), ('deep',)
MAX_TRY = 3

# name, kind(script/llm), unit(once/chunk/month/person/block), prompt, model, tiers, deps, 说明
STAGES = [
    dict(name='ingest', kind='script', unit='once', tiers=ALL, deps=[], desc='导入与标准化 → work/all.json'),
    dict(name='split', kind='script', unit='once', tiers=ALL, deps=['ingest'], desc='按月切分段 → work/chunks/'),
    dict(name='read', kind='llm', unit='chunk', prompt='00', model='cheap', tiers=ALL, deps=['split'],
         desc='逐行阅读（standard/deep 用 00 统一阅读：事件+人物证据；lite 用 01 只抽事件）'),
    dict(name='collect', kind='script', unit='once', tiers=SD, deps=['read'], desc='卡片 → 事件文件 + 每人 evidence.md（核对 ID/说话人/原话）'),
    dict(name='merge', kind='llm', unit='month', prompt='02', model='cheap', tiers=ALL, deps=['read', 'collect'], desc='多段月份合并去重'),
    dict(name='check', kind='script', unit='once', tiers=ALL, deps=['merge'], desc='事件机检（无未处理警告才算过；合理的可 --allow 标记保留）'),
    dict(name='freeze', kind='script', unit='once', tiers=ALL, deps=['check'], desc='refs 换稳定键 → work/stable/'),
    dict(name='chronicle', kind='script', unit='once', tiers=ALL, deps=['freeze'], desc='大事记页面 → out/chronicle.html'),
    dict(name='person-stats', kind='script', unit='once', tiers=SD, deps=['ingest'], desc='逐人切块、统计、metrics、turnmix（日常口径）'),
    dict(name='baseline', kind='llm', unit='person', prompt='13', model='cheap', tiers=SD, deps=['person-stats'], desc='随机 500 条日常基线标注'),
    dict(name='deepread', kind='llm', unit='block', prompt='07', model='cheap', tiers=SD, deps=['person-stats'], desc='可选：专人深读（config.deep_read）'),
    dict(name='portraits', kind='llm', unit='person', prompt='08', model='strong', tiers=SD,
         deps=['collect', 'person-stats', 'baseline', 'deepread'], desc='人物小传（引语带出处标注）'),
    dict(name='personas', kind='llm', unit='person', prompt='11', model='strong', tiers=D,
         deps=['collect', 'person-stats', 'baseline', 'deepread'], desc='人物模型（先日常后高光）'),
    dict(name='review', kind='llm', unit='person', prompt='12', model='strong', tiers=D, deps=['personas'], desc='人物模型独立审稿'),
    dict(name='blind', kind='llm', unit='person', prompt='15', model='cheap', tiers=D, deps=['personas'], desc='盲测第 1 轮'),
    dict(name='revise', kind='llm', unit='person', prompt='14', model='strong', tiers=D, deps=['review', 'blind'], desc='人物模型修订第 1 轮'),
    dict(name='factfix', kind='llm', unit='person', prompt='10', model='strong', tiers=D, deps=['revise', 'portraits'], desc='用模型核查结果回修小传'),
    dict(name='overview', kind='llm', unit='once', prompt='16', model='strong', tiers=D, deps=['revise'], desc='群像总览'),
    dict(name='editor', kind='llm', unit='once', prompt='09', model='strong', tiers=SD, deps=['portraits', 'factfix'], desc='小传总编终审'),
    dict(name='build', kind='script', unit='once', tiers=SD, deps=['editor', 'chronicle'], desc='人物志页面 → out/people.html'),
]
BY = {s['name']: s for s in STAGES}
# 增量更新登记的任务（不由文件推导，跨运行保留；见 register）
BY['incremental'] = dict(name='incremental', kind='llm', unit='extra', prompt='01', model='cheap', tiers=ALL, deps=['split'],
                         desc='增量更新：尾部分段抽事件（01）→ merge-tail 并进 stable')
INC_KIND = {'extract': 'llm', 'merge-tail': 'script'}
RENAMED = {'stats': 'person-stats'}  # 早期阶段名 → 现名（state.json 与 reset 照样认）
MODEL = {'cheap': '便宜模型（如 Claude Sonnet / Haiku）', 'strong': '强模型（如 Claude Opus）'}


def tier_of(cfg, override=None):
    t = override or cfg.get('tier') or 'standard'
    if t not in ALL:
        sys.exit(f'config.tier 应为 lite/standard/deep，现在是 {t!r}')
    return t


def enabled(cfg, tier):
    """本档位启用的阶段名（按默认顺序）。"""
    return [s['name'] for s in STAGES if tier in s['tiers'] and (s['name'] != 'deepread' or cfg.get('deep_read'))]


# ---------------- 任务单元 ----------------

def chunk_stems(P):
    """read 阶段的分段（增量尾部 <月>_tail_p<i> 不在内，走 incremental 任务）。"""
    return sorted(f.stem for f in (P / 'work/chunks').glob('*.txt') if '_tail_' not in f.stem)


def multi_months(P):
    parts = {}
    for c in chunk_stems(P):
        parts.setdefault(c.rsplit('_p', 1)[0], []).append(c)
    return sorted(m for m, cs in parts.items() if len(cs) > 1)


def units(P, cfg, st):
    u = st['unit']
    if st['name'] == 'overview' and not units(P, cfg, BY['personas']):
        return []
    if u == 'once':
        return [None]
    if u == 'chunk':
        return chunk_stems(P)
    if u == 'month':
        return multi_months(P)
    if u == 'person':
        return list(cfg.get('people') or [])
    if u == 'block':
        return [f'{p}/{f.stem}' for p in cfg.get('deep_read') or []
                for f in sorted((P / 'work/people' / safe(p) / 'chunks').glob('*.txt'))]
    return []


def tid(stage, unit):
    return stage if unit is None else f'{stage}:{unit}'


# ---------------- 产出与机检 ----------------

def mtime(p):
    return p.stat().st_mtime if p.exists() else 0


def newest(paths):
    return max((mtime(p) for p in paths), default=0)


class Ctx:
    """一次运行内缓存 all.json，机检引语时用。"""
    def __init__(self, P, cfg):
        self.P, self.cfg, self._all = P, cfg, None

    def allm(self):
        if self._all is None:
            self._all = json.loads((self.P / 'work/all.json').read_text(encoding='utf-8'))
        return self._all


def cite_check(ctx, person, md):
    from verify_citations import verify  # noqa: E402
    r = verify(ctx.cfg, ctx.allm(), person, md.read_text(encoding='utf-8'))
    if r['errors'] or r['unmarked']:
        return False, (f'引语机检：问题 {len(r["errors"])}、未标注 {len(r["unmarked"])}——跑 verify_citations.py --person {person} '
                       f'--md {md.relative_to(ctx.P)} 看 work/review/{safe(person)}-citations.md')
    return True, f'引语 {len(r["cited"])} 条全部核对通过'


def outputs(P, cfg, tier, stage, unit):
    """该任务的产出路径（展示用 + 机检用）。"""
    w, o = P / 'work', P / 'out'
    p = safe(unit) if unit and stage not in ('read', 'merge', 'deepread') else None
    if stage == 'read':
        if tier == 'lite':
            mon = unit.rsplit('_p', 1)[0]
            return [w / 'part_events' / f'{unit}.json' if mon in multi_months(P) else w / 'events' / f'{mon}.json']
        return [w / 'cards' / f'{unit}.json']
    if stage == 'deepread':
        person, blk = unit.split('/')
        return [w / 'people' / safe(person) / 'cards' / f'{blk}.md']
    return {
        'ingest': [w / 'all.json'], 'split': [w / 'chunks'],
        'collect': [w / 'people' / safe(x) / 'evidence.md' for x in cfg.get('people') or []],
        'merge': [w / 'events' / f'{unit}.json'], 'check': [w / 'check.txt'], 'freeze': [w / 'stable'],
        'chronicle': [o / 'chronicle.html'],
        'person-stats': [w / 'metrics.md', w / 'turnmix.md'] + [w / 'stats' / f'{safe(x)}.md' for x in cfg.get('people') or []],
        'baseline': [w / 'base' / f'{p}.md'], 'portraits': [o / 'portraits' / f'{p}.md'], 'personas': [o / 'personas' / f'{p}.md'],
        'review': [w / 'review' / f'{p}.md'], 'blind': [w / 'test' / f'{p}-r1.md'],
        'revise': [o / 'personas' / '.v1' / f'{p}.md', o / 'personas' / f'{p}.md'],
        'factfix': [o / 'portraits.bak' / f'{p}.md', o / 'portraits' / f'{p}.md'],
        'overview': [o / 'personas' / '00-群像总览.md'], 'editor': [w / 'review' / 'portraits-editor.md'], 'build': [o / 'people.html'],
    }[stage]


def inc_outputs(P, rec, unit):
    pe = P / 'work/part_events'
    if rec.get('step') == 'extract':
        return [pe / f'{unit}.json']
    return [P / 'work/stable' / f'{unit}.json']


def inc_check(P, rec, unit):
    pe = P / 'work/part_events'
    if rec.get('step') == 'extract':
        if (pe / f'{unit}.json').exists() or (pe / 'merged' / f'{unit}.json').exists():
            return True, ''
        return None, ''
    if list(pe.glob(f'{unit}_tail_p*.json')):
        return None, ''
    return (True, '') if list((pe / 'merged').glob(f'{unit}_tail_p*.json')) else (None, '')


def extra_cards(P, unit):
    """补读卡片：<分段>-b.json、-c.json…（fill_prompt --from-line 派的，只读剩余行）。"""
    return sorted((P / 'work/cards').glob(f'{unit}-[b-z].json'))


def read_progress(P, unit):
    """一个分段连续读到了第几行：原卡的 read_to，补读卡从 from 行接上就往后延。→ (读到, 总行数)。"""
    try:
        d = json.loads((P / 'work/cards' / f'{unit}.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 0, 0
    lines, got = d.get('lines') or 0, d.get('read_to') or 0
    for f in extra_cards(P, unit):
        try:
            x = json.loads(f.read_text(encoding='utf-8'))
        except ValueError:
            continue
        if (x.get('from') or 1) <= got + 1:
            got = max(got, x.get('read_to') or 0)
    return got, lines


def check(ctx, tier, stage, unit):
    """(True, 说明) 通过；(False, 原因) 产出在但不合格；(None, '') 还没产出。"""
    P, cfg = ctx.P, ctx.cfg
    outs = outputs(P, cfg, tier, stage, unit)
    if not outs:  # collect 按核心人物出产出，config 还没 core / people 时为空
        return False, '还没有核心人物（core / people）：先跑 roster.py apply 选核心人物'
    first = outs[0]
    if stage in ('split', 'freeze'):
        if not first.is_dir() or not any(first.iterdir()):
            return None, ''
        if stage == 'freeze':
            miss = [f.name for f in (P / 'work/events').glob('*.json') if not (first / f.name).exists()]
            return (False, f'{len(miss)} 个月还没冻结') if miss else (True, '')
        return True, ''
    if not first.exists():
        return None, ''
    if stage == 'read' and tier != 'lite':
        try:
            d = json.loads(first.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            return False, f'JSON 不合法：{e}'
        if not isinstance(d.get('events'), list) or not isinstance(d.get('people'), dict):
            return False, '缺 events 或 people'
        got, lines = read_progress(P, unit)
        if lines and got < lines:
            return False, f'没读完（读到 {got}/{lines} 行），补派第 {got + 1} 行起的剩余行（fill_prompt --from-line {got + 1}）'
        return True, f'{len(d["events"])} 事件，{sum(len(v.get("items") or []) for v in d["people"].values())} 条证据'
    if stage == 'collect':
        if not all(p.exists() for p in outs):
            return None, ''
        if newest(outs[:1]) < newest((P / 'work/cards').glob('*.json')):
            return None, '卡片有更新，重跑 collect'
        return True, ''
    if stage == 'check':
        if mtime(first) < max(newest((P / 'work/events').glob('*.json')), mtime(P / 'work/check_allow.json')):
            return None, '事件或保留标记有更新，重跑机检'
        t = first.read_text(encoding='utf-8')
        m = re.search(r'未处理 (\d+) 条', t) or re.search(r'警告 (\d+) 条', t)
        if m and m.group(1) == '0':
            k = re.search(r'已确认保留 (\d+) 条', t)
            return True, '无未处理警告' + (f'（已确认保留 {k.group(1)} 条）' if k and k.group(1) != '0' else '')
        return False, (f'机检 {m.group(1) if m else "?"} 条未处理警告，见 work/check.txt：还没冻结，直接改 work/events/<月>.json '
                       '或交回抽取/合并子任务；看过确实合理的用 check_events.py --allow <键> --rule <规则> --note 理由 标记保留')
    if stage == 'chronicle' and mtime(first) < newest((P / 'work/stable').glob('*.json')):
        return None, 'stable 有更新，重新构建'
    if stage == 'build' and mtime(first) < newest((P / 'out/portraits').glob('*.md')):
        return None, '小传有更新，重新构建'
    if stage == 'person-stats' and not all(p.exists() for p in outs):
        return None, ''
    if stage in ('revise', 'factfix'):
        if mtime(outs[1]) <= mtime(first):
            return None, '已备份，正文还没改'
        return cite_check(ctx, unit, outs[1])
    if stage in ('portraits', 'personas'):
        return cite_check(ctx, unit, first)
    return True, ''


# ---------------- 命令 ----------------

def chunk_lines(P, unit):
    try:
        with open(P / 'work/chunks' / f'{unit}.txt', encoding='utf-8') as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def batches(P, tier, ids, target):
    """read 任务 → 批次：相邻短分段合计不超过 target 行的合成一批；长分段、补读中的分段单独一批。"""
    out, cur, n = [], [], 0
    for t in ids:
        u = t.split(':', 1)[1]
        k = chunk_lines(P, u)
        if target <= 0 or k >= target or (tier != 'lite' and read_progress(P, u)[0] > 0):
            out.append([t])
            continue
        if cur and n + k > target:
            out.append(cur)
            cur, n = [], 0
        cur.append(t)
        n += k
    if cur:
        out.append(cur)
    return out


def commands(P, cfg, tier, stage, unit):
    q = shlex.quote
    py, proj = 'python3', f'--project {q(str(P))}'
    s = lambda name, extra='': f'{py} {q(str(SK / name))} {proj}{extra}'  # noqa: E731

    def fill(prompt, extra, tag=None):
        out = 'work/prompts/' + re.sub(r'[:/]', '-', tag or tid(stage, unit)) + '.md'
        return f'{py} {q(str(SK / "fill_prompt.py"))} {proj} --prompt {prompt}{extra} --out {q(out)}'
    if stage == 'incremental':
        step, u = unit.split(':', 1)
        return [fill('01', f' --files {q(u + ".txt")}', unit)] if step == 'extract' else [s('incremental.py', ' --merge-tail')]
    if stage == 'read' and isinstance(unit, list):  # 一批相邻短分段
        tag = f'read:{unit[0]}--{unit[-1]}'
        files = ' '.join(q(u + '.txt') for u in unit)
        if tier == 'lite':
            return [fill('01', f' --files {files}', tag)]
        return [fill('00', f' --files {files} --set {q("people=" + "、".join(cfg.get("people") or []))}', tag)]
    who = f' --person {q(unit)}' if unit else ''
    if stage == 'read' and tier != 'lite':
        got, lines = read_progress(P, unit)
        more = f' --from-line {got + 1}' if lines and 0 < got < lines else ''
        return [fill('00', f' --files {q(unit + ".txt")}{more} --set {q("people=" + "、".join(cfg.get("people") or []))}')]
    return {
        'ingest': lambda: [s('ingest.py')],
        'split': lambda: [s('split_chunks.py')],
        'read': lambda: [fill('01', f' --files {q(unit + ".txt")}')],
        'collect': lambda: [s('collect_evidence.py')],
        'merge': lambda: [fill('02', f' --months {q(unit)}')],
        'check': lambda: [s('check_events.py', f' --dir events > {q(str(P / "work/check.txt"))}')],
        'freeze': lambda: [s('freeze.py')],
        'chronicle': lambda: [s('build_chronicle.py')],
        'person-stats': lambda: [s('person_chunks.py'), s('person_stats.py'), s('metrics.py'), s('turnmix.py')],
        'baseline': lambda: [s('baseline_sample.py', who), fill('13', who)],
        'deepread': lambda: [fill('07', f' --person {q(unit.split("/")[0])}')],
        'portraits': lambda: [fill('08', who)],
        'personas': lambda: [fill('11', who)],
        'review': lambda: [fill('12', who)],
        'blind': lambda: [s('holdout.py', who), fill('15', who + ' --round 1')],
        'revise': lambda: [fill('14', who + ' --round 1')],
        'factfix': lambda: [fill('10', who)],
        'overview': lambda: [fill('16', '')],
        'editor': lambda: [fill('09', '')],
        'build': lambda: [s('build_portraits.py')],
    }[stage]()


# ---------------- 状态 ----------------

def load_state(P):
    f = P / 'work/state.json'
    st = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {'tasks': {}}
    for old, new in RENAMED.items():
        if old in st.get('tasks', {}):
            st['tasks'][new] = dict(st['tasks'].pop(old), stage=new)
    return st


def register(P, cfg, new, tier=None):
    """增量更新等外部脚本登记任务：new = [{id: 'extract:<分段>'|'merge-tail:<月>', step, prompt?, files?, months?}]。
    已有同 id 的不重复登记。登记后同步一次（顺带把新出现的分段排进 read 阶段），返回 state。"""
    st = load_state(P)
    tasks = st.setdefault('tasks', {})
    stamp = now()
    for t in new:
        if t['id'] not in tasks:
            tasks[t['id']] = {**{k: v for k, v in t.items() if k != 'id'}, 'stage': 'incremental', 'status': 'todo',
                              'attempts': 0, 'source': 'incremental', 'added': stamp}
    save_state(P, st)
    st, _ = sync(P, cfg, tier_of(cfg, tier))
    save_state(P, st)
    return st


def save_state(P, st):
    f = P / 'work/state.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def sync(P, cfg, tier):
    """按当前文件重算任务表，合并旧状态，做自动判定。返回 (state, {阶段: [任务 id]})。"""
    st = load_state(P)
    old = st.get('tasks') or {}
    ctx = Ctx(P, cfg)
    tasks, by_stage = {}, {}
    for name in enabled(cfg, tier):
        stg = BY[name]
        ids = []
        for u in units(P, cfg, stg):
            t = tid(name, u)
            rec = dict(old.get(t) or {'stage': name, 'status': 'todo', 'attempts': 0})
            rec['out'] = [str(p.relative_to(P)) for p in outputs(P, cfg, tier, name, u)]
            if not rec.get('manual'):
                ok, note = check(ctx, tier, name, u)
                prev = rec['status']
                if ok is True:
                    rec['status'] = 'done'
                elif ok is False:
                    rec['status'] = 'failed'
                elif prev == 'done':
                    rec['status'] = 'todo'
                if note or ok is not None or prev != rec['status']:
                    rec['note'] = note
                if prev != rec['status']:
                    rec['updated'] = now()
            tasks[t] = rec
            ids.append(t)
        by_stage[name] = ids
    inc = []
    for t, rec in old.items():
        if rec.get('source') != 'incremental' or t in tasks:
            continue
        rec = dict(rec)
        u = t.split(':', 1)[1]
        rec['out'] = [str(p.relative_to(P)) for p in inc_outputs(P, rec, u)]
        if not rec.get('manual'):
            ok, _ = inc_check(P, rec, u)
            prev = rec['status']
            if ok:
                rec['status'] = 'done'
            elif prev == 'done':
                rec['status'] = 'todo'
            if prev != rec['status']:
                rec['updated'] = now()
        tasks[t] = rec
        inc.append(t)
    if inc:
        by_stage['incremental'] = inc
    st.pop('blocked', None)  # 早期版本的阶段拦截记录，已不用
    st.update(tier=tier, tasks=tasks, stages={n: stage_status(tasks, ids) for n, ids in by_stage.items()}, synced=now())
    return st, by_stage


def stage_status(tasks, ids):
    ss = [tasks[t]['status'] for t in ids]
    if not ss:
        return 'empty'
    if all(s == 'done' for s in ss):
        return 'done'
    return 'failed' if 'failed' in ss else ('doing' if any(s in ('doing', 'done') for s in ss) else 'todo')


def ready(st, by_stage, name):
    """依赖都完成（未启用的依赖忽略；没有单元的阶段要等它的上游完成才算空完成）。"""
    for d in BY[name]['deps']:
        if d not in by_stage:
            continue
        if not by_stage[d]:
            if not ready(st, by_stage, d):
                return False
            continue
        if st['stages'][d] != 'done':
            return False
    return True


# ---------------- 命令行 ----------------

def cmd_status(P, cfg, tier, st, by_stage):
    print(f'项目 {P}  档位 {tier}  （work/state.json，{st["synced"]}）\n')
    print('| 阶段 | 类型 | 模型 | 依赖 | todo | doing | done | failed | 状态 |')
    print('|---|---|---|---|---|---|---|---|---|')
    for name, ids in by_stage.items():
        s = BY[name]
        c = {k: sum(st['tasks'][t]['status'] == k for t in ids) for k in ('todo', 'doing', 'done', 'failed')}
        state = st['stages'][name]
        if state == 'empty':
            state = '无任务（已满足）' if ready(st, by_stage, name) else '待上游产出'
        elif state != 'done' and not ready(st, by_stage, name):
            state = '等依赖'
        deps = '、'.join(d for d in s['deps'] if d in by_stage) or '—'
        print(f'| {name} | {"脚本" if s["kind"] == "script" else "子任务"} | {s.get("model", "—")} | {deps} | '
              f'{c["todo"]} | {c["doing"]} | {c["done"]} | {c["failed"]} | {state} |')
    bad = [(t, r) for t, r in st['tasks'].items() if r['status'] == 'failed']
    if bad:
        print('\n失败/不合格：')
        for t, r in bad:
            print(f'  - {t}（尝试 {r.get("attempts", 0)} 次{"，已达上限需人工" if r.get("attempts", 0) >= MAX_TRY else ""}）：{r.get("note", "")}')
    doing = [t for t, r in st['tasks'].items() if r['status'] == 'doing']
    if doing:
        print(f'\n进行中：{"、".join(doing[:20])}{" …" if len(doing) > 20 else ""}')
    rd = [n for n in by_stage if st['stages'][n] not in ('done',) and by_stage[n] and ready(st, by_stage, n)]
    print('\n下一步：' + (f'可派阶段 {"、".join(rd)}——运行 `python3 {shlex.quote(str(SK / "pipeline.py"))} --project {shlex.quote(str(P))} next --limit 8`'
                         if rd else ('全部完成。' if all(st['stages'][n] in ('done', 'empty') for n in by_stage) else '等进行中的任务回来（产出写好后再跑 status 会自动标 done）。')))


def kind_of(t, r):
    return INC_KIND.get(r.get('step'), 'llm') if r.get('stage') == 'incremental' else BY[r['stage']]['kind']


def cmd_next(P, cfg, tier, st, by_stage, limit, peek, batch_lines=1000):
    tasks = st['tasks']
    slots = limit - sum(1 for t, r in tasks.items() if r['status'] == 'doing' and kind_of(t, r) == 'llm')
    picked, held = [], []
    for name, ids in by_stage.items():
        if not ids or not ready(st, by_stage, name):
            continue
        elig = []
        for t in ids:
            r = tasks[t]
            if r['status'] not in ('todo', 'failed'):
                continue
            if r.get('attempts', 0) >= MAX_TRY:
                held.append(t)
                continue
            if t.startswith('merge-tail:') and any(x.startswith(f'extract:{t[11:]}_tail_') and tasks[x]['status'] != 'done'
                                                   for x in ids):
                continue
            elig.append(t)
        for g in (batches(P, tier, elig, batch_lines) if name == 'read' else [[t] for t in elig]):
            if kind_of(g[0], tasks[g[0]]) == 'llm':
                if slots <= 0:
                    continue
                slots -= 1
            picked.append(g)
    if not picked:
        print('现在没有可派的任务。' + (f'已达尝试上限、需人工处理：{"、".join(held)}' if held else '') + '（`status` 看详情）')
        return
    for g in picked:
        t = g[0]
        r = tasks[t]
        name = r['stage']
        unit = t.split(':', 1)[1] if ':' in t else None
        s = BY[name]
        k = kind_of(t, r)
        prompt = ('01' if tier == 'lite' else '00') if name == 'read' else (s.get('prompt') if k == 'llm' else None)
        units_ = [x.split(':', 1)[1] for x in g] if len(g) > 1 else []
        head = t if len(g) == 1 else f'{t} … {g[-1]}（{len(g)} 段合一批，共 {sum(chunk_lines(P, u) for u in units_)} 行）'
        print(f'## {head}  [{"脚本，主控直接跑" if k == "script" else "子任务 · " + MODEL[s["model"]]}]  {s["desc"]}')
        if prompt:
            print(f'- prompt：prompts/{prompt}-*.md')
        print('- 命令：')
        for c in commands(P, cfg, tier, name, units_ if len(g) > 1 else (t if name == 'incremental' else unit)):
            print(f'    {c}')
        if k == 'llm':
            tag = re.sub(r'[:/]', '-', t if len(g) == 1 else f'read:{units_[0]}--{units_[-1]}')
            print(f'  然后派一个子任务：说明里给 {P / "work/prompts" / (tag + ".md")} 的绝对路径，让它先用 Read 读完全文再照做'
                  + (f'（说明末尾注明块号 {unit.split("/")[1]}）' if name == 'deepread' else ''))
        print(f'- 产出：{"、".join(o for x in g for o in tasks[x]["out"])}')
        for x in g:
            if tasks[x].get('status') == 'failed' and tasks[x].get('note'):
                print(f'- 上次不合格（{x}）：{tasks[x]["note"]}')
        print()
        if not peek:
            for x in g:
                tasks[x].update(status='doing', attempts=tasks[x].get('attempts', 0) + 1, updated=now())
    if held:
        print(f'已达尝试上限、需人工处理：{"、".join(held)}')
    if not peek:
        print(f'以上已记为 doing。产出写好后跑 `status`/`next` 会自动判定；判定不了的用 `mark <任务> done`。')


def main():
    a = args(__doc__, lambda p: (p.add_argument('cmd', choices=['status', 'next', 'mark', 'reset']),
                                 p.add_argument('rest', nargs='*', help='mark: <任务> done|failed；reset: <任务或阶段>'),
                                 p.add_argument('--limit', type=int, default=8, help='next：子任务并发上限（含进行中的），默认 8'),
                                 p.add_argument('--peek', action='store_true', help='next：只列出，不记 doing'),
                                 p.add_argument('--batch-lines', type=int, default=1000,
                                                help='next：read 阶段相邻短分段合批的行数上限，默认 1000；0 = 一段一个任务'),
                                 p.add_argument('--note', default='', help='mark：备注'),
                                 p.add_argument('--tier', choices=ALL, help='临时覆盖 config.tier')))
    P, cfg = a.project, a.cfg
    tier = tier_of(cfg, a.tier)
    st, by_stage = sync(P, cfg, tier)
    if a.cmd == 'status':
        cmd_status(P, cfg, tier, st, by_stage)
    elif a.cmd == 'next':
        cmd_next(P, cfg, tier, st, by_stage, a.limit, a.peek, a.batch_lines)
    elif a.cmd == 'mark':
        if len(a.rest) != 2 or a.rest[1] not in ('done', 'failed'):
            sys.exit('用法：mark <任务> done|failed')
        t, s = a.rest
        t = RENAMED.get(t, t)
        if t not in st['tasks']:
            sys.exit(f'没有任务 {t}（`status` 看阶段；任务 id 形如 read:2023-01_p1、portraits:张三）')
        st['tasks'][t].update(status=s, manual=(s == 'done'), note=a.note or st['tasks'][t].get('note', ''), updated=now())
        print(f'{t} → {s}')
    elif a.cmd == 'reset':
        if len(a.rest) != 1:
            sys.exit('用法：reset <任务或阶段>')
        x = RENAMED.get(a.rest[0], a.rest[0])
        hit = [t for t in st['tasks'] if t == x or st['tasks'][t]['stage'] == x]
        if not hit:
            sys.exit(f'没有任务或阶段 {x}')
        for t in hit:
            st['tasks'][t].update(status='todo', attempts=0, manual=False, note='', updated=now())
        print(f'重置 {len(hit)} 个任务：{"、".join(hit[:10])}{" …" if len(hit) > 10 else ""}')
    st['stages'] = {n: stage_status(st['tasks'], ids) for n, ids in by_stage.items()}
    save_state(P, st)


if __name__ == '__main__':
    main()
