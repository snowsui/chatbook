"""隐私闸门：公开页面（大事记 / 小剧场 / 人物志 / 数据页 / 登录版网站）构建时的隐私扫描。

build_chronicle / build_stories / build_portraits / build_stats / package_site 等会自动调用；默认只提醒不拦：
命中项全部作为警告打印（位置、上下文、id），照常写 work/privacy/last_scan.json，构建继续——是否发布由创作者决定。
想让闸门拦住构建时开严格模式：config 写 "privacy": {"strict": true}（所有构建脚本生效），或单独运行时加 --strict。
严格模式下「重点」类命中（下面标 ★ 的规则）会中止构建。也可以单独运行：

  python3 scripts/privacy_gate.py --project <dir>                     # 扫所有公开页面的输入（存在的才扫）
  python3 scripts/privacy_gate.py --project <dir> --target portraits  # 只扫一类：chronicle / stories / portraits / stats / digest
  python3 scripts/privacy_gate.py --project <dir> --scan a.md b.json  # 扫任意文件（所有规则都按公开页面口径）
  python3 scripts/privacy_gate.py --project <dir> --strict            # 严格模式：有重点命中就以退出码 1 结束
  python3 scripts/privacy_gate.py --project <dir> --allow 3f9a01c2bd --reason "误报"   # 标记已看过，之后不再列出
  python3 scripts/privacy_gate.py --project <dir> --add-blocked "用户删掉的那句话"     # 追加已删除素材清单
  python3 scripts/privacy_gate.py --project <dir> --list                               # 看规则来源与忽略记录

规则（详见 references/09-privacy.md）：
- ★ blocked：已删除素材清单 = config.blocked_snippets + work/privacy/blocked.txt（一行一条，# 开头是注释）。
  去掉空白与标点后做子串匹配；≥8 字的片段还做近似匹配（片段的二字组有 ≥70% 落在同一句里）。
- ★ sensitive：config.sensitive_words（本群敏感词）。
- ★ pii：手机号、身份证号、银行卡号（Luhn 校验）、邮箱、微信号/QQ 号、「密码是…」。
- realname：config.real_names（列表，或 {显示名: 真名/[真名…]}）；出现在小剧场里算 ★，其他页面是普通警告。
- ★ persona：公开页面的输入里引用 out/personas/ 下的文件，或出现人物模型的章节标题（大五人格、对照清单…）。
- ★ money / address：大事记（stable/ 事件、top10 理由）、人物志、月报年报（out/digest/*.md）里带数字的金额
  （28k、3万、500元、¥200）和门牌住址（3号楼、2单元、501室、某某路12号），config.public_detail 为 standard（缺省）时；
  public_detail=full 时降为下面的普通警告。小剧场是虚构，不查这两条。
- builtin：内置分层词表（健康/外貌体重/孕育/感情婚恋/家庭矛盾/金额/住址/证件账号/工作单位职级/醉酒），宽松匹配，普通警告。
闸门只认逐字或近似命中：换了说法的（“那件事”“你懂的”、打比方）机器认不出，要靠人看。
看过、确认无碍的命中可以 --allow 掉（记在 work/privacy/allowlist.json），之后不再列出，严格模式下也不再拦。
"""
import datetime
import hashlib
import json
import re
import shlex
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 去掉这些字符再匹配（宽松匹配：中间夹了空格、Markdown 记号、标点也算命中）
SKIP = set(' \t\r\n​‌‍﻿*_~`#>|"\'“”‘’「」『』《》〈〉()（）[]【】,，.。!！?？;；:：、…—-–·/\\')

# 工作变故（内置词表的「工作单位职级」与 build_stats 的展示敏感词共用）
WORK_CHANGE = r'裁员|被裁|被优化|辞职|裸辞|辞退|离职|跳槽|失业|待业|开除|降薪|降职|升职|绩效|赔偿|面试|offer|考公|考编|申论|行测|上岸'

# 内置分层词表（正则，作用在去掉空白标点后的文本上）。命中 = 警告。
BUILTIN = {
    '健康': r'住院|出院|手术|开刀|确诊|癌|肿瘤|化疗|抑郁|焦虑症|精神科|心理医生|吃药|病房|急诊|体检报告|复查|医院',
    '外貌体重': r'体重|减肥|长胖|胖了|发福|\d+斤|秃|发际线|颜值|整容',
    '孕育': r'怀孕|怀上|怀了|备孕|孕[期检]|产检|预产期|流产|坐月子|生娃|二胎|不孕|试管|接班人|下一代|添丁|有喜',
    '感情婚恋': r'离婚|分手|出轨|前任|前男友|前女友|相亲|单身|脱单|暧昧|表白|暗恋|追她|追他|约会|cp|嗑|官宣|小三',
    '家庭矛盾': r'吵架|冷战|婆婆|丈母娘|婆媳|闹掰|翻脸',
    '金额': r'\d+(?:\.\d+)?(?:万|千|w|k)(?:块|元)?|\d+(?:块|元|rmb)|￥\d|¥\d|工资|年薪|月薪|存款|房贷|车贷|借钱|欠钱|彩礼|首付',
    '住址': r'小区|\d+号楼|\d+栋|\d+单元|门牌|\d+室|路\d+号|住在',
    '证件账号': r'身份证|银行卡|卡号|账号|密码|手机号|电话号|车牌',
    '工作单位职级': r'公司|集团|单位|职级|总监|处长|科长|p\d|t\d|' + WORK_CHANGE,
    '醉酒': r'喝醉|喝多了|断片|吐了|宿醉',
}

# 带数字的金额、门牌住址（作用在去掉空白标点、小写后的文本上）：public_detail=standard 时公开的非虚构页面里算重点
MONEY = r'\d+(?:\.\d+)?(?:万|千|w|k)(?:块|元)?|\d+(?:块|元|rmb)|￥\d|¥\d'
ADDRESS = r'\d+号楼|\d+栋|\d+单元|\d+室|\d+弄|\d+号院|路\d+号|街\d+号|门牌号?\d+'

# 人物模型的章节标题 / 专有字样（出现在公开页面输入里 = 重点）
PERSONA_MARKS = r'out/personas|personas/|人物模型|大五人格|misbelief|发言类型分布|日常基线|私人频道|情境推演|盲区与偏差|对照清单|声音模型|价值排序|核心恐惧|表层与真性格|压力下显出'

PII = [  # (规则名, 正则, 作用在哪种文本上, 额外校验)
    ('手机号', r'(?<!\d)1[3-9]\d(?:[ -]?\d){8}(?!\d)', 'nfkc', None),
    ('身份证号', r'(?<![0-9A-Za-z])\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[0-9Xx](?![0-9A-Za-z])', 'nfkc', None),
    ('银行卡号', r'(?<!\d)\d(?:[ -]?\d){15,18}(?!\d)', 'nfkc', 'luhn'),
    ('邮箱', r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}', 'nfkc', None),
    ('微信号/QQ号', r'(?i)(?:微信号?|vx|wx|qq号?)\s*(?:号)?\s*(?:是|为|[:：])\s*[A-Za-z0-9_-]{5,20}|(?:微信号|qq号)\s*[A-Za-z0-9_-]{5,20}', 'nfkc', None),
    ('密码', r'密码\s*(?:是|为|[:：])\s*\S{3,}', 'nfkc', None),
]


def luhn(digits):
    s, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d > 4 else d * 2
        s += d
        alt = not alt
    return s % 10 == 0


def norm(text, strip=True):
    """逐字 NFKC + 小写；strip=True 时再去掉空白和标点。返回 (新文本, 每个新字符对应的原下标)。"""
    out, pos = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize('NFKC', ch).lower():
            if strip and (c in SKIP or c.isspace()):
                continue
            out.append(c)
            pos.append(i)
    return ''.join(out), pos


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)}


# ---------------- 规则 ----------------

def _read_lines(path):
    if not path.exists():
        return []
    return [x.strip() for x in path.read_text(encoding='utf-8').split('\n') if x.strip() and not x.strip().startswith('#')]


def blocked_list(proj, cfg):
    items = list(cfg.get('blocked_snippets') or []) + _read_lines(proj / 'work/privacy/blocked.txt')
    seen, out = set(), []
    for s in items:
        n = norm(s)[0]
        if n and n not in seen:
            seen.add(n)
            out.append(s)
    return out


def real_names(cfg):
    rn = cfg.get('real_names') or []
    if isinstance(rn, dict):
        vals = []
        for v in rn.values():
            vals += v if isinstance(v, list) else [v]
        rn = vals
    return [x for x in rn if x and len(x) >= 2]


class Rules:
    def __init__(self, proj, cfg):
        self.blocked = [(s, norm(s)[0]) for s in blocked_list(proj, cfg)]
        self.sensitive = [(w, norm(w)[0]) for w in cfg.get('sensitive_words') or [] if norm(w)[0]]
        self.real = [(w, norm(w)[0]) for w in real_names(cfg)]
        self.builtin = {k: re.compile(v) for k, v in BUILTIN.items()}
        self.money = re.compile(MONEY)
        self.address = re.compile(ADDRESS)
        self.persona = re.compile(PERSONA_MARKS)
        self.pii = [(n, re.compile(p), t, chk) for n, p, t, chk in PII]


def _ctx(text, a, b, width=14):
    left = text[max(0, a - width):a].replace('\n', ' ')
    right = text[b:b + width].replace('\n', ' ')
    return f'{"…" if a > width else ""}{left}【{text[a:b]}】{right}{"…" if b + width < len(text) else ""}'


def scan_text(rules, where, text, realname_block=False, builtin=True, excerpt=False, money_block=False):
    """扫一段文本（通常一行）。返回命中列表；severity = block（重点，严格模式下会拦）/ warn（普通警告）。
    excerpt=True：原文片段，只跑重点类规则。money_block=True：带数字的金额、门牌算重点（大事记、public_detail=standard）。"""
    hits = []
    n, pos = norm(text)
    k, kpos = norm(text, strip=False)

    def add(rule, sev, a, b, mapping, label=''):
        a0, b0 = mapping[a], mapping[b - 1] + 1
        match = text[a0:b0]
        win = norm(text[max(0, a0 - 15):b0 + 15])[0]
        hid = hashlib.sha1(f'{rule}|{norm(match)[0]}|{win}'.encode()).hexdigest()[:10]
        hits.append({'id': hid, 'rule': rule, 'severity': sev, 'label': label, 'match': match,
                     'where': where, 'col': a0 + 1, 'context': _ctx(text, a0, b0)})

    def find_all(needle, hay):
        i = hay.find(needle)
        while i >= 0:
            yield i, i + len(needle)
            i = hay.find(needle, i + 1)

    covered = set()
    for raw, s in rules.blocked:
        for a, b in find_all(s, n):
            add('blocked', 'block', a, b, pos, '已删除素材：' + raw[:30])
            covered.add(raw)
    if rules.blocked and len(n) >= 8:  # 近似：改了几个字又加回来的
        for sent in re.finditer(r'[^。！？!?；;\n]+', text):
            sn, sp = norm(sent.group())
            if len(sn) < 6:
                continue
            sg = bigrams(sn)
            for raw, s in rules.blocked:
                if raw in covered or len(s) < 8:
                    continue
                g = bigrams(s)
                if len(g & sg) / len(g) >= 0.7:
                    add('blocked~', 'block', 0, len(sn), [sent.start() + p for p in sp],
                        f'疑似改写后的已删除素材：{raw[:30]}')
                    covered.add(raw)
                    break
    for raw, s in rules.sensitive:
        for a, b in find_all(s, n):
            add('sensitive', 'block', a, b, pos, '本群敏感词：' + raw)
    for raw, s in rules.real:
        for a, b in find_all(s, n):
            add('realname', 'block' if realname_block else 'warn', a, b, pos, '真名：' + raw)
    for name, rx, _, chk in rules.pii:
        for m in rx.finditer(k):
            if chk == 'luhn':
                digits = re.sub(r'\D', '', m.group())
                if not 16 <= len(digits) <= 19 or not luhn(digits):
                    continue
            add('pii', 'block', m.start(), m.end(), kpos, name)
    if not excerpt:
        for m in rules.persona.finditer(k):
            add('persona', 'block', m.start(), m.end(), kpos, '人物模型内容（只能本地私用）')
    if money_block and not excerpt:
        for m in rules.money.finditer(n):
            add('money', 'block', m.start(), m.end(), pos, '具体金额（public_detail=standard，公开页面只写概括）')
        for m in rules.address.finditer(n):
            add('address', 'block', m.start(), m.end(), pos, '具体住址（public_detail=standard，公开页面不写门牌）')
    if builtin and not excerpt:
        for tier, rx in rules.builtin.items():
            for m in rx.finditer(n):
                if money_block and ((tier == '金额' and rules.money.fullmatch(m.group()))
                                    or (tier == '住址' and rules.address.fullmatch(m.group()))):
                    continue
                add('builtin', 'warn', m.start(), m.end(), pos, '内置词表·' + tier)
    return hits


# ---------------- 公开页面的输入 ----------------

def _md_units(path, rel):
    """按行；去掉引语出处标注 <!--k:…-->（不上页面，里面的长数字消息键会误判成卡号）。"""
    lines = path.read_text(encoding='utf-8').split('\n')
    return [(f'{rel}:{i}', t) for i, line in enumerate(lines, 1) if (t := re.sub(r'<!--k:[^>]*?-->', '', line)).strip()]


def _strings(obj, prefix=''):
    if isinstance(obj, str):
        yield prefix, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f'{prefix}.{k}' if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f'{prefix}[{i}]')


def units_for(proj, cfg, target):
    """返回 [(位置, 文本, 选项)]；选项 = {'realname_block':…, 'excerpt':…}。"""
    out, W, O = [], proj / 'work', proj / 'out'
    rel = lambda p: p.relative_to(proj).as_posix()
    pages_cfg = (cfg.get('pages') or {})
    if target == 'chronicle':
        mb = {'money_block': cfg.get('public_detail') != 'full'}
        stable = sorted((W / 'stable').glob('*.json'))
        refs = []
        for f in stable:
            mo = json.loads(f.read_text(encoding='utf-8'))
            if mo.get('month_summary'):
                out.append((f'{rel(f)} M:{mo.get("month")}.month_summary', mo['month_summary'], mb))
            for i, e in enumerate(mo.get('events', [])):
                for fld in ('title', 'summary', 'category'):
                    if e.get(fld):
                        out.append((f'{rel(f)} E:{mo.get("month")}-{i}.{fld}', e[fld], mb))
                refs += e.get('refs', [])
        top = W / 'top10.json'
        if top.exists():
            for y, rows in json.loads(top.read_text(encoding='utf-8')).items():
                for r in rows:
                    if r.get('reason'):
                        out.append((f'{rel(top)} {y} {r.get("id")}.reason', r['reason'], mb))
        for path, s in _strings({k: v for k, v in pages_cfg.items() if k in ('name', 'chronicle', 'tabs')}):
            out.append((f'config.pages.{path}', s, {}))
        out += _excerpt_units(proj, cfg, refs)
    elif target == 'stories':
        src = O / 'stories'
        for f in sorted(src.glob('*.md')):
            if f.name.startswith('_'):
                continue
            cast = f.name == 'CAST.md'  # 真名列不上页面，CAST 里不查真名
            out += [(w, t, {'realname_block': not cast, 'realname_skip': cast}) for w, t in _md_units(f, rel(f))]
        for path, s in _strings(pages_cfg.get('stories') or {}):
            out.append((f'config.pages.stories.{path}', s, {'realname_block': True}))
    elif target == 'portraits':
        mb = {'money_block': cfg.get('public_detail') != 'full'}
        for f in sorted((O / 'portraits').glob('*.md')):
            if not f.name.startswith('_'):
                out += [(w, t, mb) for w, t in _md_units(f, rel(f))]
        for path, s in _strings(pages_cfg.get('portraits') or {}):
            out.append((f'config.pages.portraits.{path}', s, {}))
    elif target == 'stats':  # 数据页：只有这些字会上页面（其余是数字）
        f = W / 'stats.json'
        if f.exists():
            d = json.loads(f.read_text(encoding='utf-8'))
            where = rel(f)
            out += [(f'{where} people[{i}]', p['n'], {}) for i, p in enumerate(d.get('people', []))]
            out += [(f'{where} repeat.phrases[{i}]', t, {}) for i, t in enumerate(d.get('repeat', {}).get('phrases', []))]
            for key in ('catch', 'laugh'):
                out += [(f'{where} {key}[{i}]', t, {}) for i, rows in (d.get(key) or {}).items() for t, _ in rows]
            out += [(f'{where} cloud', w, {}) for w, _ in d.get('cloud', [])]
        for path, s in _strings(pages_cfg.get('stats') or {}):
            out.append((f'config.pages.stats.{path}', s, {}))
    elif target == 'digest':  # 月报 / 年报正文：发群前扫
        mb = {'money_block': cfg.get('public_detail') != 'full'}
        for f in sorted((O / 'digest').glob('*.md')):
            out += [(w, t, mb) for w, t in _md_units(f, rel(f))]
    return out


def _excerpt_units(proj, cfg, refs):
    """大事记里会展示的聊天原文（config.pages.show_chat_groups 里的群，被引用消息前后各 3 条）。只跑重点类规则。"""
    show_cfg = (cfg.get('pages') or {}).get('show_chat_groups') or []
    allf = proj / 'work/all.json'
    if not show_cfg or not refs or not allf.exists():
        return []
    label_of = {g.get('key'): g.get('label') for g in cfg.get('groups', [])}
    show = {label_of.get(x, x) for x in show_cfg}
    allm = json.loads(allf.read_text(encoding='utf-8'))
    idx = {m['k']: i for i, m in enumerate(allm)}
    keep = set()
    for r in refs:
        p = idx.get(r)
        if p is None or allm[p]['g'] not in show:
            continue
        keep.add(p)
        for step in (-1, 1):
            n, i = 0, p
            while 0 <= i + step < len(allm) and n < 3:
                i += step
                if allm[i]['g'] == allm[p]['g']:
                    keep.add(i); n += 1
    return [(f'work/all.json {allm[i]["k"]}（大事记原文片段）', allm[i]['c'], {'excerpt': True}) for i in sorted(keep)]


def file_units(path):
    """--scan 的任意文件：json 取所有字符串；html 去掉 data: URI 与标签；其他按行。"""
    text = path.read_text(encoding='utf-8', errors='replace')
    if path.suffix == '.json':
        try:
            return [(f'{path}{(" " + p) if p else ""}', s) for p, s in _strings(json.loads(text))
                    if not re.fullmatch(r'[A-Za-z]{1,3}:[\w.-]+', s)]  # 跳过消息稳定键（refs 等），免得长数字误判卡号
        except json.JSONDecodeError:
            pass
    if path.suffix in ('.html', '.htm'):
        text = re.sub(r'data:[^\'")\s]+', '', text)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S)
        text = re.sub(r'<[^>]+>', '\n', text)
    return [(f'{path}:{i}', line) for i, line in enumerate(text.split('\n'), 1) if line.strip()]


# ---------------- 忽略记录 ----------------

def _priv(proj):
    d = proj / 'work/privacy'
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_allow(proj):
    f = proj / 'work/privacy/allowlist.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else []


# 这几类命中的原文本身就是具体内容（某句已删素材、某个敏感词/真名/号码），标记看过后按「规则 + 原文」认，
# 同一处原文出现在别的页面或别的输入里也不再列出；金额、住址、内置词表这类泛词仍按 id（含前后文）逐处认。
BY_MATCH = ('blocked', 'blocked~', 'sensitive', 'pii', 'realname', 'persona')


def is_allowed(h, allow_rows):
    ids = {a['id'] for a in allow_rows}
    pairs = {(a.get('rule'), norm(a.get('match') or '')[0]) for a in allow_rows if a.get('rule') in BY_MATCH and a.get('match')}
    return h['id'] in ids or (h['rule'] in BY_MATCH and (h['rule'], norm(h['match'])[0]) in pairs)


def run_scan(proj, cfg, units):
    """→ (未忽略的命中, 已忽略条数, 全部命中)。写 last_scan.json 由调用方（save_scan）做。"""
    rules = Rules(proj, cfg)
    allow_rows = load_allow(proj)
    hits = []
    for where, text, opt in units:
        hs = scan_text(rules, where, text, realname_block=opt.get('realname_block', False), excerpt=opt.get('excerpt', False),
                       money_block=opt.get('money_block', False))
        if opt.get('realname_skip'):
            hs = [h for h in hs if h['rule'] != 'realname']
        hits += hs
    live = [h for h in hits if not is_allowed(h, allow_rows)]
    return live, len(hits) - len(live), hits


def save_scan(proj, key, hits):
    """last_scan.json：顶层 at/target/hits 是本次结果；targets 按「脚本:口径」分开保存每类最近一次的命中，
    别的构建跑过也不会覆盖——--allow 在这里面找 id。"""
    f = _priv(proj) / 'last_scan.json'
    try:
        old = json.loads(f.read_text(encoding='utf-8')).get('targets') or {}
    except (OSError, ValueError, AttributeError):
        old = {}
    at = datetime.datetime.now().isoformat(timespec='seconds')
    old[key] = {'at': at, 'hits': hits}
    f.write_text(json.dumps({'at': at, 'target': key, 'hits': hits, 'targets': old}, ensure_ascii=False, indent=1), encoding='utf-8')


def scanned_hits(proj):
    """last_scan.json 里各口径保存过的全部命中 → {id: 命中}。"""
    f = proj / 'work/privacy/last_scan.json'
    try:
        d = json.loads(f.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    rows = list(d.get('hits') or []) + [h for t in (d.get('targets') or {}).values() for h in t.get('hits') or []]
    return {h['id']: h for h in rows}


def is_strict(cfg):
    """严格模式：config.privacy.strict = true 时，重点命中会中止构建。缺省只提醒。"""
    return bool((cfg.get('privacy') or {}).get('strict'))


def report(live, skipped, label, max_warn=None, strict=False):
    blocks = [h for h in live if h['severity'] == 'block']
    warns = [h for h in live if h['severity'] == 'warn']
    for title, rows in (('阻断' if strict else '警告·重点', blocks), ('警告', warns)):
        if not rows:
            continue
        print(f'\n[隐私闸门·{title}] {len(rows)} 处', file=sys.stderr)
        cap = max_warn if title == '警告' and max_warn is not None else len(rows)
        if len(rows) > cap:
            print(f'  （只列前 {cap} 处；全部见 work/privacy/last_scan.json，或单独运行 privacy_gate.py --project <dir>）', file=sys.stderr)
        for h in rows[:cap]:
            print(f'  {h["id"]}  {h["where"]}（第 {h["col"]} 字）  {h["label"] or h["rule"]}\n      {h["context"]}', file=sys.stderr)
    if strict:
        print(f'[隐私闸门·严格模式] {label}：阻断 {len(blocks)}，警告 {len(warns)}，已忽略 {skipped}', file=sys.stderr)
        if blocks:
            print('  处理办法：改掉原文后重跑；确属可以公开的，标记已看过：\n'
                  f'  python3 {shlex.quote(str(Path(__file__).resolve()))} --project <dir> --allow <id> [<id>…] --reason "为什么可以"；'
                  '或关掉严格模式（config.privacy.strict）', file=sys.stderr)
    elif live:
        print(f'[隐私闸门] {label}：疑似隐私问题 {len(live)} 处（重点 {len(blocks)}），已忽略 {skipped}。'
              '只提醒、构建照常继续，是否发布由你决定', file=sys.stderr)
    else:
        print(f'[隐私闸门] {label}：没有发现疑似隐私问题（已忽略 {skipped}）', file=sys.stderr)
    return blocks


def _html_hits(proj, cfg, paths):
    """已生成的页面再查一遍重点类（已删除素材、敏感词、引用 personas/）——手改过 html 也能发现。"""
    rules = Rules(proj, cfg)
    allow_rows = load_allow(proj)
    live = []
    for p in paths:
        for where, text in file_units(p):
            where = where.replace(str(proj) + '/', '')
            hs = [h for h in scan_text(rules, where, text, builtin=False, excerpt=True) if h['rule'] in ('blocked', 'blocked~', 'sensitive')]
            if 'personas/' in text:
                i = text.find('personas/')
                snip = text[max(0, i - 15):i + 40]  # 命中原文取引用处前后一段，--allow 时按它认
                hs.append({'id': hashlib.sha1(f'persona|{norm(snip)[0]}'.encode()).hexdigest()[:10], 'rule': 'persona',
                           'severity': 'block', 'label': '页面里引用了 personas/', 'match': snip, 'where': where,
                           'col': i + 1, 'context': text[:60]})
            live += [h for h in hs if not is_allowed(h, allow_rows)]
    return live


def review_note(proj):
    """回收过本人确认结果（collect_reviews.py）时，打一行汇总提醒；只提醒，不影响构建。"""
    d = proj / 'work/review/replies'
    parts = []
    for f in sorted(d.glob('*.json')) if d.exists() else []:
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
            if not isinstance(r, dict):
                raise ValueError('不是 JSON 对象')
        except (OSError, ValueError) as e:
            print(f'[本人确认·提醒] 跳过读不了的回收文件 {f.relative_to(proj)}（{e}），重跑 collect_reviews.py 可重新生成', file=sys.stderr)
            continue
        its = [x for x in r.get('items') or [] if x.get('kind') in ('portrait', 'event')]
        bits = [f'{n} 条标了{lab}' for v, lab in (('hide', '别公开'), ('wrong', '要改'))
                if (n := sum(x.get('v') == v for x in its))]
        if bits:
            parts.append(f'{r.get("person") or f.stem} 有 ' + '、'.join(bits))
    if parts:
        print('[本人确认·提醒] ' + '；'.join(parts) + '（详见 work/review/replies.md）', file=sys.stderr)


def enforce(proj, cfg, target, max_warn=15, texts=None, pages=None, strict=None):
    """build_* 脚本调用：target = chronicle / stories / portraits / stats / all（几类输入都扫）/ 列表（几类一起扫）/
    site（package_site 用：out/ 里已生成的页面对应的输入都扫，再把生成好的 html 查一遍重点类）。
    texts=[(位置, 文本)]：脚本自己拼出来的文案（口头禅、原话、卡片文字…），按公开页面口径一起扫。
    pages=[html 路径]：任意已生成的页面（build_locked 加密前），和 site 一样查重点类。
    缺省只打印警告、返回命中列表；strict（缺省取 config.privacy.strict）为真且有重点命中时中止。"""
    strict = is_strict(cfg) if strict is None else strict
    targets = ['chronicle', 'stories', 'portraits', 'stats', 'digest'] if target == 'all' else list(target) if isinstance(target, (list, tuple)) else [target]
    html = list(pages or [])
    if target == 'site':
        O = proj / 'out'
        targets = [t for t, f in (('chronicle', 'chronicle.html'), ('stories', 'stories.html'), ('portraits', 'people.html'),
                                  ('stats', 'stats.html')) if (O / f).exists()]
        html += [O / f for f in ('chronicle.html', 'stories.html', 'people.html', 'stats.html') if (O / f).exists()]
    label = target if isinstance(target, str) else '+'.join(target)
    units = [u for t in targets for u in units_for(proj, cfg, t)] + [(w, t, {}) for w, t in texts or [] if t]
    live, skipped, hits = run_scan(proj, cfg, units)
    html_live = _html_hits(proj, cfg, html)
    save_scan(proj, f'{Path(sys.argv[0]).stem}:{label}', hits + html_live)
    live += html_live
    if report(live, skipped, label, max_warn, strict) and strict:
        sys.exit(f'隐私闸门（严格模式）拦下了构建（{label}）。详情见上；命中清单在 {proj / "work/privacy/last_scan.json"}')
    return live


def allow(proj, ids, reason):
    hits = scanned_hits(proj)
    cur = load_allow(proj)
    have = {a['id'] for a in cur}
    now = datetime.datetime.now().isoformat(timespec='seconds')
    for i in ids:
        if i in have:
            print('已在忽略清单：', i); continue
        h = hits.get(i)
        if not h:
            print(f'提示：{i} 不在 last_scan.json 保存的扫描结果里，仍按 id 记录（确认 id 没抄错）')
            h = {}
        cur.append({'id': i, 'rule': h.get('rule', ''), 'label': h.get('label', ''), 'match': h.get('match', ''),
                    'where': h.get('where', ''), 'context': h.get('context', ''), 'reason': reason or '', 'at': now})
        print('已标记看过：', i, h.get('context', ''))
    (_priv(proj) / 'allowlist.json').write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding='utf-8')


def add_blocked(proj, snippets, note=''):
    """追加到 work/privacy/blocked.txt（已有的跳过）。返回实际新增的条数。"""
    f = _priv(proj) / 'blocked.txt'
    have = {norm(s)[0] for s in _read_lines(f)}
    new = [s.replace('\n', ' ').strip() for s in snippets if s.strip() and norm(s)[0] not in have]
    if new:
        head = '' if f.exists() else '# 已删除素材清单（追加式，一行一条；# 开头为注释）。公开页面里再出现这些内容，隐私闸门会提醒（严格模式下会拦）。\n'
        stamp = f'# {datetime.date.today()} {note}'.rstrip() + '\n'
        with f.open('a', encoding='utf-8') as fh:
            fh.write(head + stamp + ''.join(s + '\n' for s in new))
    return len(new)


def main():
    import common
    a = common.args(__doc__, lambda p: (
        p.add_argument('--target', choices=['chronicle', 'stories', 'portraits', 'stats', 'digest', 'all'], default='all'),
        p.add_argument('--scan', nargs='+', metavar='文件', help='扫描任意文件'),
        p.add_argument('--allow', nargs='+', metavar='id', help='标记已看过，之后不再列出（id 见扫描输出）'),
        p.add_argument('--reason', default='', help='理由（记录进 allowlist.json）'),
        p.add_argument('--strict', action='store_true', help='严格模式：有重点命中时退出码为 1'),
        p.add_argument('--add-blocked', nargs='+', metavar='片段', help='追加到已删除素材清单'),
        p.add_argument('--list', action='store_true', help='列出规则来源与忽略记录')))
    proj, cfg = a.project, a.cfg
    if a.add_blocked:
        print(f'已追加 {add_blocked(proj, a.add_blocked, "手动 --add-blocked")} 条 → {proj / "work/privacy/blocked.txt"}')
        return
    if a.allow:
        allow(proj, a.allow, a.reason)
        return
    if a.list:
        print('已删除素材清单：', *[f'  - {s}' for s in blocked_list(proj, cfg)] or ['  （无）'], sep='\n')
        print('本群敏感词：', '、'.join(cfg.get('sensitive_words') or []) or '（无）')
        print('真名：', '、'.join(real_names(cfg)) or '（无）')
        print('忽略记录：', *[f'  {x["id"]}  {x["label"]}  {x["context"]}  理由：{x["reason"]}' for x in load_allow(proj)] or ['  （无）'], sep='\n')
        return
    if a.scan:
        units = []
        for s in a.scan:
            p = Path(s).expanduser()
            if not p.is_absolute() and not p.exists():
                p = proj / s
            if not p.is_file():
                sys.exit(f'--scan：找不到文件 {s}')
            units += [(w, t, {'realname_block': True}) for w, t in file_units(p)]
        strict = a.strict or is_strict(cfg)
        live, skipped, hits = run_scan(proj, cfg, units)
        save_scan(proj, 'scan', hits)
        sys.exit(1 if report(live, skipped, '--scan', strict=strict) and strict else 0)
    enforce(proj, cfg, a.target, max_warn=None, strict=a.strict or is_strict(cfg))


if __name__ == '__main__':
    main()
