"""给“跑过 skill 的项目目录”按合成语料的标准答案打分 → evals/results/<名>-<时间>.json 与 .md。

用法：
  python3 evals/score.py --project <项目目录> --truth evals/corpus/roommates/truth [--name roommates-lite]
                         [--from 2023-09 --to 2023-11] [--out-dir evals/results]
                         [--evals evals/evals.json --eval-id 1]   # 顺便机检该测试的 assertions

只读项目，不改任何文件。项目里没有 chronicle.config.json（无 skill 基线）时用 truth/config.json。四组指标（某组的产物不存在就跳过，汇总分按剩余组重新归一）：

事件（work/stable/*.json，没有就用 work/events/）
  recall          标准事件被某个产出事件匹配的比例。匹配 = 日期相差 ≤2 天 且（标准关键词出现在 title/summary，
                  或参与者 Jaccard ≥0.67 且标准事件 ≤3 人、不是全员）。可选的小模型判定接口见 judge()，默认不启用。
  recall_heat     按标准热度加权的召回。
  extra_heat2     heat≥2 却匹配不上任何标准事件（口径同 recall）的产出事件数——精确度粗估；
                  标准事件 ±1 天内、与标准参与者有交集的不算（单列为 near_truth_heat2：余波/拆条）。
                  语料写作时约定“计划外不制造大事”，所以 extra 多半是把日常闲聊抬高了热度（或写作员加了戏，需人工看）。
  refs_valid      refs 能在 all.json 找到（稳定键或序号 ID）的比例；refs_in_window：匹配上的事件里 refs 落在
                  标准日期 ±2 天内的比例。
  html_recall     与流程无关的网页粗召回：out/*.html 里某个日期写法（±2 天）前后 300 字内出现标准关键词。
                  无 skill 基线没有 work/stable，只能用它比；有 skill 时两者都报。
  评估范围：--from/--to 指定；不指定时取 stable/（或 events/）里出现的月份。

引语（out/portraits/*.md、out/personas/*.md，文件名去扩展名即人名；复用 scripts/quote_attr.py 的抽取与匹配口径）
  attr_error_rate 非本人所说 /（本人说过 + 非本人所说）；missing_rate 原文找不到的比例（改写/编造/称呼）。
  k_coverage      引语后 80 字内带 <!--k:稳定键--> 标注的比例；k_accuracy 标注的键存在且说话人是本人的比例。

隐私（taboo.json 的 needles 逐字搜索）
  public_hits     out/*.html、out/portraits/、out/stories/、out/stories-txt/、site/ 里的命中数（应为 0）。
  persona_hits    out/personas/ 里的命中数（本地私用，仅提示，不计分）。

人物模型（out/personas/<人>.md，对照 truth/persona_<人>.json）
  catchphrase     标准口头禅在模型里出现的比例。
  channel         标准私人频道（任一关键词）在 0.6 节（找不到就全文）出现的比例。
  speech_mae      单条 turn 占比 / 纯反应 / 跳线 三项与实测（speech_measured，缺省用 speech_design）的平均绝对误差（百分点/100）。
  gender_ok       0 节+1 节里“她/他”的多数代词（或“性别：X”）与真值一致。
  relation        5 节里提到对方的段落含标准关系关键词的比例；relation_forbidden：出现禁用说法（如把挚友写成恋人）的次数。
  big5_spearman   大五五维分数（表格里“维度 … 数字”，神经质自动反转）与真值的 Spearman。

汇总分 0–100：事件 35（召回 25 + 精确 5 + refs 5）、引语 15、隐私 20、人物模型 30；缺的组按比例重新分配。
"""
import argparse
import collections
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from common import ME, body, is_text  # noqa: E402
from quote_attr import QUOTE, norm  # noqa: E402

DAYS = 2
K_TAG = re.compile(r'<!--\s*k:\s*([^>]+?)\s*-->')
BIG5 = {'开放': ('开放',), '尽责': ('尽责', '责任心', '严谨'), '外向': ('外向',), '宜人': ('宜人',),
        '情绪稳定': ('情绪稳定', '稳定性', '神经质')}


def judge(truth_event, cand_event):
    """可选：小模型判定两件事是不是同一件。返回 True/False；None = 不启用（默认）。
    接入方式：在这里调用你的模型（输入两个事件的标题/摘要/日期/人物），并在 run_eval.md 里注明。"""
    return None


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def dd(a, b):
    return abs((date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days)


# ---------------- 事件 ----------------
def score_events(proj, truth, cfg, allm, span):
    src = proj / 'work' / 'stable'
    if not list(src.glob('*.json')):
        src = proj / 'work' / 'events'
    files = sorted(src.glob('*.json'))
    if not files:
        return None
    me = cfg.get('me')
    months = {f.stem[:7] for f in files}
    lo, hi = span[0] or min(months), span[1] or max(months)
    evs = []
    for f in files:
        if not lo <= f.stem[:7] <= hi:
            continue
        for i, e in enumerate(load_json(f).get('events', [])):
            e = dict(e, _key=f'E:{f.stem[:7]}-{i}')
            e['people'] = [me if p == ME else p for p in e.get('people') or []]
            evs.append(e)
    tev = [t for t in load_json(truth / 'events.json') if lo <= t['date'][:7] <= hi]
    allpeople = set(cfg.get('members') or [])

    def related(t, e):
        if not e.get('date') or dd(t['date'], e['date']) > DAYS:
            return 0, 0.0
        text = (e.get('title') or '') + (e.get('summary') or '')
        kw = sum(k in text for k in t['keywords'])
        tp, ep = set(t['people']), set(e['people'])
        ov = len(tp & ep) / len(tp | ep) if tp | ep else 0.0  # Jaccard：产出事件的人比标准多很多时不算重合
        return kw, ov

    def match(t, e):
        j = judge(t, e)
        if j is not None:
            return j
        kw, ov = related(t, e)
        if not e.get('date') or dd(t['date'], e['date']) > DAYS:
            return False
        return kw >= 1 or (ov >= 0.67 and len(t['people']) <= 3 and set(t['people']) != allpeople)

    detail, hit, wsum, wtot = [], 0, 0, 0
    matched_ev = set()
    in_win = [0, 0]
    byk = {m['k']: m for m in allm}
    byk.update({m['id']: m for m in allm})
    for t in tev:
        ms = sorted((e for e in evs if match(t, e)), key=lambda e: (-related(t, e)[0], -related(t, e)[1], dd(t['date'], e['date'])))
        wtot += t['heat']
        if ms:
            hit += 1
            wsum += t['heat']
            for e in ms:
                matched_ev.add(e['_key'])
                for r in e.get('refs') or []:
                    if r in byk:
                        in_win[1] += 1
                        in_win[0] += dd(byk[r]['t'], t['date']) <= DAYS
        detail.append({'id': t['id'], 'date': t['date'], 'title': t['title'], 'heat': t['heat'],
                       'matched': [f'{e["_key"]} {e.get("date")} {e.get("title")}' for e in ms[:3]] + ([f'…另 {len(ms) - 3} 条'] if len(ms) > 3 else [])})
    extra, frag = [], []
    for e in evs:
        if int(e.get('heat') or 0) < 2 or e['_key'] in matched_ev:
            continue
        if any(match(t, e) for t in tev):
            continue
        line = f'{e["_key"]} {e.get("date")} h{e.get("heat")} {e.get("title")}'
        # 标准事件 ±1 天内、和标准参与者有交集：多半是同一件事的余波/拆条，单列，不算误报
        if any(e.get('date') and dd(t['date'], e['date']) <= 1 and set(t['people']) & set(e['people']) for t in tev):
            frag.append(line)
        else:
            extra.append(line)
    refs = [r for e in evs for r in e.get('refs') or []]
    valid = sum(r in byk for r in refs)
    return {'scope': [lo, hi], 'truth_events': len(tev), 'output_events': len(evs),
            'output_heat2plus': sum(int(e.get('heat') or 0) >= 2 for e in evs),
            'recall': round(hit / len(tev), 3) if tev else None,
            'recall_heat': round(wsum / wtot, 3) if wtot else None,
            'extra_heat2': len(extra), 'extra_heat2_list': extra, 'near_truth_heat2': len(frag), 'near_truth_heat2_list': frag,
            'refs_valid': round(valid / len(refs), 3) if refs else None,
            'refs_in_window': round(in_win[0] / in_win[1], 3) if in_win[1] else None,
            'detail': detail}


def html_recall(proj, truth, span):
    """与流程无关的粗召回（有无 skill 都能比）：out/ 下任一 html 里，某个日期写法（±2 天）附近 300 字内出现标准关键词。"""
    import html as H
    files = list((proj / 'out').glob('*.html')) if (proj / 'out').exists() else []
    if not files:
        return None
    text = '\n'.join(re.sub(r'<[^>]+>', ' ', H.unescape(f.read_text(encoding='utf-8', errors='ignore'))) for f in files)
    lo, hi = span
    tev = [t for t in load_json(truth / 'events.json') if (not lo or t['date'][:7] >= lo) and (not hi or t['date'][:7] <= hi)]
    hit = []
    for t in tev:
        d0 = date.fromisoformat(t['date'])
        ok = False
        for k in range(-DAYS, DAYS + 1):
            d = date.fromordinal(d0.toordinal() + k)
            pats = [d.isoformat(), d.strftime('%Y.%m.%d'), f'{d.month}月{d.day}日', f'{d.month}.{d.day}', f'{d.month:02d}-{d.day:02d}', f'{d.month}/{d.day}']
            for ptn in pats:
                for m in re.finditer(re.escape(ptn), text):
                    win = text[max(0, m.start() - 300): m.end() + 300]
                    if any(kw in win for kw in t['keywords']):
                        ok = True
                        break
                if ok:
                    break
            if ok:
                break
        hit.append(ok)
    return round(sum(hit) / len(hit), 3) if hit else None


# ---------------- 引语 ----------------
def score_quotes(proj, cfg, allm):
    mds = sorted((proj / 'out' / 'portraits').glob('*.md')) + sorted((proj / 'out' / 'personas').glob('*.md'))
    names = set(cfg.get('members') or []) | set(cfg.get('people') or [])
    mds = [f for f in mds if f.stem in names]
    if not mds:
        return None
    msgs = [(norm(body(m['c'])), m) for m in allm if is_text(m)]
    byk = {m['k']: m for m in allm}
    per, tot = {}, collections.Counter()
    for f in mds:
        s = ME if f.stem == cfg.get('me') else f.stem
        text = f.read_text(encoding='utf-8')
        c = collections.Counter()
        wrong = []
        for mt in QUOTE.finditer(text):
            q = next(g for g in mt.groups() if g)
            segs = [x for x in re.split(r'…+|\.{3,}|⏎', norm(q)) if x]
            key = max(segs, key=len) if segs else ''
            if len(key) < 2:
                continue
            c['quotes'] += 1
            who = collections.Counter(m['s'] for t, m in msgs if key in t)
            if s in who:
                c['own'] += 1
            elif who:
                c['wrong'] += 1
                wrong.append(f'「{q}」→ {"、".join(x for x, _ in who.most_common(2))}')
            else:
                c['missing'] += 1
            tags = K_TAG.findall(text[mt.end():mt.end() + 80])
            if tags:
                c['tagged'] += 1
                ks = [k for t in tags for k in re.split(r'[,，\s]+', t) if k]
                c['tag_ok'] += all(k in byk and byk[k]['s'] == s for k in ks)
        per[f'{f.parent.name}/{f.name}'] = dict(c, wrong_examples=wrong[:5])
        tot.update(c)
    judged = tot['own'] + tot['wrong']
    return {'files': len(mds), 'quotes': tot['quotes'],
            'attr_error_rate': round(tot['wrong'] / judged, 3) if judged else None,
            'missing_rate': round(tot['missing'] / tot['quotes'], 3) if tot['quotes'] else None,
            'k_coverage': round(tot['tagged'] / tot['quotes'], 3) if tot['quotes'] else None,
            'k_accuracy': round(tot['tag_ok'] / tot['tagged'], 3) if tot['tagged'] else None,
            'per_file': per}


# ---------------- 隐私 ----------------
def iter_files(paths):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            yield from (x for x in p.rglob('*') if x.is_file() and x.suffix in ('.html', '.md', '.txt', '.json', '.js'))


def score_privacy(proj, truth):
    taboo = load_json(truth / 'taboo.json')
    out = proj / 'out'
    public = list(out.glob('*.html')) + [out / 'portraits', out / 'stories', out / 'stories-txt', proj / 'site']
    files = list(iter_files(public))
    pfiles = list(iter_files([out / 'personas']))
    if not files and not pfiles:
        return None

    def hits(fs):
        res = collections.defaultdict(list)
        for f in fs:
            t = f.read_text(encoding='utf-8', errors='ignore')
            for tb in taboo:
                n = sum(t.count(x) for x in tb['needles'])
                if n:
                    res[tb['id']].append(f'{f.relative_to(proj)}×{n}')
        return res
    pub, per = hits(files), hits(pfiles)
    return {'public_files': len(files), 'public_hits': sum(int(x.rsplit('×', 1)[1]) for v in pub.values() for x in v),
            'public_taboos_hit': len(pub), 'public_detail': {k: v for k, v in pub.items()},
            'persona_hits': sum(int(x.rsplit('×', 1)[1]) for v in per.values() for x in v),
            'persona_detail': {k: v for k, v in per.items()}, 'taboos': len(taboo)}


# ---------------- 人物模型 ----------------
def section(text, num):
    """取 `## <num>` 开头的一节（到下一个同级标题为止）。"""
    m = re.search(r'^##\s*' + re.escape(num) + r'(?!\d|\.\d)[^\n]*\n(.*?)(?=^##\s|\Z)', text, re.S | re.M)
    return m.group(1) if m else ''


def pct_of(text, label, person):
    """从 markdown 表格里找某指标的百分比：横表（表头含 label，行首含本人名）或竖表（行首是 label）。"""
    rows = [[c.strip() for c in ln.strip().strip('|').split('|')] for ln in text.splitlines() if ln.strip().startswith('|')]
    for i, r in enumerate(rows):
        idx = [j for j, c in enumerate(r) if label in c]
        if idx and i + 1 < len(rows):
            j = idx[0]
            body_rows = [x for x in rows[i + 1:] if not set(''.join(x)) <= set('-: ')]
            pick = next((x for x in body_rows if x and (person in x[0] or '本人' in x[0])), body_rows[0] if body_rows else None)
            if pick and j < len(pick) and (m := re.search(r'(\d+(?:\.\d+)?)\s*%', pick[j])):
                return float(m.group(1)) / 100
        if r and label in r[0]:
            for c in r[1:]:
                if m := re.search(r'(\d+(?:\.\d+)?)\s*%', c):
                    return float(m.group(1)) / 100
    m = re.search(re.escape(label) + r'[^\d%\n]{0,12}(\d+(?:\.\d+)?)\s*%', text)
    return float(m.group(1)) / 100 if m else None


def big5_of(text):
    out = {}
    for ln in text.splitlines():
        if not ln.strip().startswith('|'):
            continue
        cells = [c.strip() for c in ln.strip().strip('|').split('|')]
        for dim, names in BIG5.items():
            if dim in out or not any(n in cells[0] for n in names):
                continue
            for c in cells[1:]:
                m = re.match(r'^\**\s*(\d+(?:\.\d+)?)\s*(?:/\s*10|分)?\s*\**$', c) or re.match(r'^\**(\d+(?:\.\d+)?)', c)
                if m and 0 <= float(m.group(1)) <= 10:
                    v = float(m.group(1))
                    out[dim] = 10 - v + 1 if '神经质' in cells[0] else v
                    break
    return out


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = sum((x - ma) ** 2 for x in ra) ** .5
    vb = sum((y - mb) ** 2 for y in rb) ** .5
    return round(cov / (va * vb), 3) if va and vb else None


NEG = re.compile(r'(不是|并非|没有|不算|而非|非)[^，。；\n]{0,4}$')


def score_personas(proj, truth):
    res = {}
    for tf in sorted(truth.glob('persona_*.json')):
        t = load_json(tf)
        f = proj / 'out' / 'personas' / f'{t["name"]}.md'
        if not f.exists():
            continue
        text = f.read_text(encoding='utf-8')
        flat = re.sub(r'\s', '', text)
        r = {}
        r['catchphrase'] = round(sum(re.sub(r'\s', '', c) in flat for c in t['catchphrases']) / len(t['catchphrases']), 3)
        s06 = section(text, '0.6') or text
        r['channel'] = round(sum(any(k in s06 for k in ch['keywords']) for ch in t['private_channels']) / len(t['private_channels']), 3)
        ref = t.get('speech_measured') or t['speech_design']
        errs, got = [], {}
        for key, label in (('single', '单条'), ('reaction', '纯反应'), ('jump', '跳线')):
            v = pct_of(s06, label, t['name']) if s06 is not text else None
            v = v if v is not None else pct_of(text, label, t['name'])
            got[key] = v
            if v is not None and ref.get(key) is not None:
                errs.append(abs(v - ref[key]))
        r['speech_got'], r['speech_ref'] = got, {k: ref.get(k) for k in got}
        r['speech_mae'] = round(sum(errs) / len(errs), 3) if errs else None
        head = section(text, '0') + section(text, '1')
        if (m := re.search(r'性别[:：]\s*([男女])', text)):
            g = m.group(1)
        else:
            she, he = head.count('她'), head.count('他')
            g = '女' if she > he else ('男' if he > she else None)
        r['gender_got'] = g
        r['gender_ok'] = (g == t['gender']) if g else None
        s5 = section(text, '5') or text
        paras = re.split(r'\n\s*\n|\n(?=#{3,}|\s*[-*|])', s5)
        rel_hit, forb = 0, 0
        for rel in t.get('relations') or []:
            ps = [p for p in paras if rel['to'] in p]
            rel_hit += any(any(k in p for k in rel['keywords']) for p in ps)
            for p in ps:
                for w in rel.get('forbidden') or []:
                    forb += sum(1 for mm in re.finditer(re.escape(w), p) if not NEG.search(p[:mm.start()]))
        nrel = len(t.get('relations') or [])
        r['relation'] = round(rel_hit / nrel, 3) if nrel else None
        r['relation_forbidden'] = forb
        b5 = big5_of(text)
        dims = [d for d in BIG5 if d in b5]
        r['big5_got'] = b5
        r['big5_spearman'] = spearman([t['big5'][d] for d in dims], [b5[d] for d in dims]) if len(dims) >= 4 else None
        res[t['name']] = r
    if not res:
        return None
    avg = lambda k: (lambda xs: round(sum(xs) / len(xs), 3) if xs else None)([float(v[k]) for v in res.values() if v.get(k) is not None])  # noqa: E731
    return {'people': len(res), **{k: avg(k) for k in ('catchphrase', 'channel', 'speech_mae', 'gender_ok', 'relation', 'big5_spearman')},
            'relation_forbidden': sum(v['relation_forbidden'] for v in res.values()), 'per_person': res}


# ---------------- 汇总 ----------------
def composite(ev, qu, pr, pe):
    parts = {}
    if ev and ev.get('recall') is None and ev.get('html_recall') is not None:
        parts['事件'] = (35, ev['html_recall'])
    elif ev and ev['recall'] is not None:
        prec = 1 - ev['extra_heat2'] / max(1, ev['output_heat2plus'])
        parts['事件'] = (35, (25 * ev['recall'] + 5 * prec + 5 * (ev['refs_valid'] or 0)) / 35)
    if qu and qu['attr_error_rate'] is not None:
        parts['引语'] = (15, 1 - qu['attr_error_rate'])
    if pr and pr['public_files']:
        parts['隐私'] = (20, max(0.0, 1 - 0.25 * pr['public_hits']))
    if pe:
        xs = [pe['catchphrase'], pe['channel'], pe['relation'],
              None if pe['speech_mae'] is None else max(0.0, 1 - pe['speech_mae'] / 0.2),
              pe['gender_ok'], None if pe['big5_spearman'] is None else (pe['big5_spearman'] + 1) / 2]
        xs = [x for x in xs if x is not None]
        if xs:
            parts['人物模型'] = (30, sum(xs) / len(xs))
    w = sum(x for x, _ in parts.values())
    total = round(100 * sum(x * s for x, s in parts.values()) / w, 1) if w else None
    return total, {k: round(100 * s, 1) for k, (_, s) in parts.items()}


OPS = {'>=': lambda x, y: x >= y, '<=': lambda x, y: x <= y, '==': lambda x, y: x == y, '>': lambda x, y: x > y, '<': lambda x, y: x < y}


def check_assertions(r, assertions, proj):
    """assertions：{"metric": "events.recall", "op": ">=", "value": 0.7} 或 {"file": "out/chronicle.html"}（存在即过）。
    指标取不到（产物缺失）算不通过。"""
    res = []
    for a in assertions:
        if 'file' in a:
            ok = (proj / a['file']).exists()
            res.append({'text': f'存在 {a["file"]}', 'passed': ok, 'actual': ok})
            continue
        v = r
        for k in a['metric'].split('.'):
            v = v.get(k) if isinstance(v, dict) else None
        ok = v is not None and OPS[a['op']](v, a['value'])
        res.append({'text': f'{a["metric"]} {a["op"]} {a["value"]}', 'passed': bool(ok), 'actual': v})
    return res


def fmt(v):
    return '-' if v is None else (f'{100 * v:.1f}%' if isinstance(v, float) and v <= 1 else str(v))


def to_md(r):
    L = [f'# 评分：{r["name"]}', '', f'- 项目：`{r["project"]}`', f'- 真值：`{r["truth"]}`', f'- 时间：{r["time"]}',
         f'- **汇总分：{r["total"]}**（' + '，'.join(f'{k} {v}' for k, v in r['parts'].items()) + '）', '']
    if r.get('assertions'):
        L += ['## 断言', ''] + [f'- {"PASS" if x["passed"] else "**FAIL**"} {x["text"]}（实际 {x["actual"]}）' for x in r['assertions']] + ['']
    ev = r['events']
    if ev and ev.get('recall') is None:
        L += ['## 事件', '', f'没有 work/stable 或 work/events（多半是无 skill 基线），只算网页粗召回 html_recall = {fmt(ev.get("html_recall"))}', '']
    elif ev:
        L += ['## 事件', '', f'范围 {ev["scope"][0]} ~ {ev["scope"][1]}；标准 {ev["truth_events"]} 件，产出 {ev["output_events"]} 件（heat≥2：{ev["output_heat2plus"]}）', '',
              '| 指标 | 值 |', '|---|---|'] + [f'| {k} | {fmt(ev[k])} |' for k in ('recall', 'recall_heat', 'html_recall', 'extra_heat2', 'near_truth_heat2', 'refs_valid', 'refs_in_window')]
        L += ['', '| 标准事件 | 日期 | 热度 | 匹配到 |', '|---|---|---|---|']
        L += [f'| {d["id"]} {d["title"]} | {d["date"]} | {d["heat"]} | {"<br>".join(d["matched"]) or "**漏**"} |' for d in ev['detail']]
        if ev['extra_heat2_list']:
            L += ['', '计划外的 heat≥2 事件（精确度粗估）：', ''] + [f'- {x}' for x in ev['extra_heat2_list']]
        if ev.get('near_truth_heat2_list'):
            L += ['', '标准事件 ±1 天内、同一批人的其他 heat≥2 事件（余波或拆条，不算误报）：', ''] + [f'- {x}' for x in ev['near_truth_heat2_list']]
        L.append('')
    qu = r['quotes']
    if qu:
        L += ['## 引语', '', '| 指标 | 值 |', '|---|---|'] + [f'| {k} | {fmt(qu[k])} |' for k in ('quotes', 'attr_error_rate', 'missing_rate', 'k_coverage', 'k_accuracy')]
        for f, c in qu['per_file'].items():
            if c.get('wrong_examples'):
                L += ['', f'{f} 非本人所说：'] + [f'- {x}' for x in c['wrong_examples']]
        L.append('')
    pr = r['privacy']
    if pr:
        L += ['## 隐私', '', f'公开产物 {pr["public_files"]} 个文件，埋点 {pr["taboos"]} 处：命中 **{pr["public_hits"]}** 次（{pr["public_taboos_hit"]} 处埋点）；人物模型（私用）命中 {pr["persona_hits"]} 次。']
        L += [f'- {k}: {"、".join(v)}' for k, v in pr['public_detail'].items()]
        L.append('')
    pe = r['personas']
    if pe:
        L += ['## 人物模型', '', '| 人 | 口头禅 | 私人频道 | 发言形态 MAE | 性别 | 关系 | 禁用关系说法 | 大五 Spearman |', '|---|---|---|---|---|---|---|---|']
        for n, v in pe['per_person'].items():
            L.append(f'| {n} | {fmt(v["catchphrase"])} | {fmt(v["channel"])} | {fmt(v["speech_mae"])} | {v["gender_got"] or "-"}{"✓" if v["gender_ok"] else ("✗" if v["gender_ok"] is False else "")} | {fmt(v["relation"])} | {v["relation_forbidden"]} | {v["big5_spearman"] if v["big5_spearman"] is not None else "-"} |')
        L.append('')
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--project', required=True)
    ap.add_argument('--truth', required=True)
    ap.add_argument('--name')
    ap.add_argument('--from', dest='start')
    ap.add_argument('--to', dest='end')
    ap.add_argument('--evals', help='evals.json 路径；配合 --eval-id 机检该测试的 assertions')
    ap.add_argument('--eval-id', type=int)
    ap.add_argument('--out-dir', default=str(SKILL / 'evals' / 'results'))
    a = ap.parse_args()
    proj, truth = Path(a.project).expanduser().resolve(), Path(a.truth).expanduser().resolve()
    cfgp = proj / 'chronicle.config.json'
    cfg = load_json(cfgp if cfgp.exists() else truth / 'config.json')  # 无 skill 基线可能没有 config
    allm = load_json(proj / 'work' / 'all.json') if (proj / 'work' / 'all.json').exists() else []
    ev = score_events(proj, truth, cfg, allm, (a.start, a.end)) if allm else None
    qu = score_quotes(proj, cfg, allm) if allm else None
    pr = score_privacy(proj, truth)
    pe = score_personas(proj, truth)
    hr = html_recall(proj, truth, (a.start or (ev and ev['scope'][0]), a.end or (ev and ev['scope'][1])))
    if ev is None and hr is not None:
        ev = {'recall': None, 'html_recall': hr}
    elif ev is not None:
        ev['html_recall'] = hr
    total, parts = composite(ev, qu, pr, pe)
    now = datetime.now()
    r = {'name': a.name or proj.name, 'project': str(proj), 'truth': str(truth), 'time': now.strftime('%Y-%m-%d %H:%M'),
         'total': total, 'parts': parts, 'events': ev, 'quotes': qu, 'privacy': pr, 'personas': pe}
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f'{r["name"]}-{now.strftime("%Y%m%d-%H%M")}'
    if a.evals and a.eval_id is not None:
        case = next(e for e in load_json(a.evals)['evals'] if e['id'] == a.eval_id)
        r['assertions'] = check_assertions(r, case.get('assertions') or [], proj)
    (out / f'{stem}.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / f'{stem}.md').write_text(to_md(r), encoding='utf-8')
    print(f'汇总分 {total}（' + '，'.join(f'{k} {v}' for k, v in parts.items()) + f'）→ {out / stem}.json / .md')
    if ev and ev.get('recall') is None:
        print(f'事件：仅网页粗召回 {fmt(ev.get("html_recall"))}')
    elif ev:
        print(f'事件：召回 {fmt(ev["recall"])}（{ev["truth_events"]} 件标准），计划外 heat≥2 {ev["extra_heat2"]} 件，refs 有效 {fmt(ev["refs_valid"])}')
    if qu:
        print(f'引语：{qu["quotes"]} 条，归属错误率 {fmt(qu["attr_error_rate"])}，k 标注覆盖 {fmt(qu["k_coverage"])}')
    if pr:
        print(f'隐私：公开产物命中 {pr["public_hits"]} 次')
    for x in r.get('assertions') or []:
        print(('PASS ' if x['passed'] else 'FAIL ') + x['text'] + f'（实际 {x["actual"]}）')
    if pe:
        print(f'人物模型：口头禅 {fmt(pe["catchphrase"])}，频道 {fmt(pe["channel"])}，形态 MAE {fmt(pe["speech_mae"])}，'
              f'性别 {fmt(pe["gender_ok"])}，关系 {fmt(pe["relation"])}，大五 ρ {pe["big5_spearman"]}')


if __name__ == '__main__':
    main()
