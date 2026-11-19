"""分享形态（卡片 / 年度报告）共用的小工具：读统计、读事件、挑年度十大、核对原话、Playwright 截图。不单独运行。"""
import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LIST_ITEM, body, display, is_text, sender_key  # noqa: E402
from verify_citations import STRIP  # noqa: E402,F401  引语出处标注 <!--k:…-->，读人物志原文时去掉

LAUGH = re.compile(r'^(?:[哈呵嘿嘻h]+|2333+|笑死(?:我了)?|hhh+|lol|lmao|xd)[~～!！。.]*$', re.I)
DECOR = re.compile(r'\[[^\]]{1,6}\]|[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]')  # [捂脸] 这类内联表情、emoji


def parse_stats(path):
    """解析 person_stats.py 写的 work/stats/<人>.md。返回 {total, hours, phrases[(词, 次)], near[(人, 次)]}。"""
    txt = Path(path).read_text(encoding='utf-8')
    out = {'total': 0, 'hours': collections.Counter(), 'phrases': [], 'near': []}
    m = re.search(r'消息总数 (\d+)', txt)
    out['total'] = int(m.group(1)) if m else 0
    m = re.search(r'按小时：(.*)', txt)
    if m:
        out['hours'] = collections.Counter({int(h): int(n) for h, n in re.findall(r'(\d+)点:(\d+)', m.group(1))})
    m = re.search(r'紧挨着说话最多的人：(.*)', txt)
    if m:
        out['near'] = [(x, int(n)) for x, n in re.findall(r'([^、(]+)\((\d+)\)', m.group(1))]
    m = re.search(r'## 常发短句[^\n]*\n(.*)', txt)
    if m:
        for item in m.group(1).split(' | '):
            if '×' in item:
                w, n = item.rsplit('×', 1)
                if n.isdigit():
                    out['phrases'].append((w.strip(), int(n)))
    return out


def _short(m, max_len):
    """短句候选：(原文, 去掉表情后的核心)；不是短文字消息就返回 None。"""
    if not is_text(m):
        return None
    t = body(m['c']).strip()
    if not t or len(t) > max_len or '\n' in t:
        return None
    return t, DECOR.sub('', t).strip()


def catchphrases(msgs, k=3, max_len=8, min_months=3, min_uses=5, names=()):
    """口头禅：≤max_len 字、在 ≥min_months 个不同月份出现、共被用 ≥min_uses 次的短句，按次数取前 k 个。
    排除纯笑声/纯表情（笑声另见 favorite_laugh）、问句（「几点到？」这类一次性问句不是口头禅）、
    接龙行（「1. 某某」）、单字、纯称呼（names 里的名字，叫人不是口头禅）——与 build_stats 同一口径。msgs = 此人的消息。"""
    uses, months = collections.Counter(), collections.defaultdict(set)
    for m in msgs:
        x = _short(m, max_len)
        if not x:
            continue
        t, core = x
        if not re.search(r'[\w一-鿿]', core) or LAUGH.match(core) or re.search(r'[?？]|吗$', core):
            continue
        if len(core) < 2 or LIST_ITEM.match(core) or core in names:
            continue
        uses[t] += 1
        months[t].add(m['t'][:7])
    return [w for w, n in uses.most_common() if n >= min_uses and len(months[w]) >= min_months][:k]


def favorite_laugh(msgs, least=5):
    """最爱的笑法：最常用的那种纯笑声（哈哈哈 / hhh / 笑死…），用过 ≥least 次才算。"""
    c = collections.Counter(x[1] for m in msgs if (x := _short(m, 12)) and LAUGH.match(x[1]))
    return c.most_common(1)[0][0] if c and c.most_common(1)[0][1] >= least else None


def metrics_row(proj, label):
    """读 work/metrics.md 某一行，返回 {人: 值}（不含「全群」列）；没有文件或这行就返回 {}。"""
    f = Path(proj) / 'work/metrics.md'
    if not f.exists():
        return {}
    rows = [r.strip().strip('|').split('|') for r in f.read_text(encoding='utf-8').splitlines() if r.startswith('|')]
    if not rows:
        return {}
    head = [c.strip() for c in rows[0]]
    for r in rows[2:]:
        cells = [c.strip() for c in r]
        if cells and cells[0] == label:
            return {h: v for h, v in zip(head[1:], cells[1:]) if h != '全群'}
    return {}


def hour_label(h):
    seg = '凌晨' if h < 6 else '早上' if h < 9 else '上午' if h < 12 else '中午' if h < 14 else '下午' if h < 18 else '晚上'
    h12 = h if h <= 12 else h - 12
    return f'{seg} {h12} 点'


def group_age(t0, t1):
    """'YYYY-MM-DD…' 两个时间 → '3 年 2 个月' / '5 个月' / '20 天'（按天数折算，满一年的 365 天记作 1 年）。"""
    days = (date.fromisoformat(t1[:10]) - date.fromisoformat(t0[:10])).days + 1
    if days < 60:
        return f'{days} 天'
    y, mo = divmod(round(days / 30.44), 12)
    if not y:
        return f'{mo} 个月'
    return f'{y} 年' + (f' {mo} 个月' if mo else '')


def load_events(proj, cfg):
    """读 work/stable/*.json → {id: 事件}，id = 'YYYY-MM-序号'（同 build_chronicle / 修订清单的 E: 键）。people 换成显示名。"""
    evs = {}
    for f in sorted((Path(proj) / 'work/stable').glob('*.json')):
        mo = json.loads(f.read_text(encoding='utf-8'))
        for i, e in enumerate(mo.get('events', [])):
            evs[f"{mo['month']}-{i}"] = {**e, 'id': f"{mo['month']}-{i}", 'heat': int(e.get('heat', 1)),
                                         'people': [display(cfg, p) for p in e.get('people', [])]}
    return evs


def top_events(proj, evs, year):
    """某个自然年的年度十大：有 work/top10.json 就按它（取该年的键），否则按 热度 → 引用数 → 日期 自动挑。返回 [(事件, 理由)]。"""
    f = Path(proj) / 'work/top10.json'
    if f.exists():
        picks = json.loads(f.read_text(encoding='utf-8')).get(str(year)) or []
        rows = [(evs[p['id'].removeprefix('E:')], p.get('reason', '')) for p in picks if p['id'].removeprefix('E:') in evs]
        if rows:
            return rows
    cand = [e for e in evs.values() if e['date'][:4] == str(year)]
    cand.sort(key=lambda e: (-e['heat'], -len(e.get('refs', [])), e['date']))
    return [(e, e.get('summary', '')) for e in cand[:10]]


def verified_quote(cfg, allm, person, text, override=None):
    """代表性原话：override（config 里手填的）优先；否则取人物志里第一句「…」引语（6–80 字，不同的字少于 4 个的往后排），
    且必须是此人某条消息的原文片段——核对不上的不用（免得把别人的话安到 TA 头上）。返回 (原话, 日期) 或 None。"""
    s = sender_key(cfg, person)
    flat = lambda x: re.sub(r'\s+', '', x)  # noqa: E731  原文里的换行在人物志里常被合并
    mine = [(flat(body(m['c'])), m['t'][:10]) for m in allm if m['s'] == s]
    cands = re.findall(r'「([^」]{6,80})」', STRIP.sub('', text or ''))
    cands.sort(key=lambda q: len(set(q)) < 4)  # 「哈哈哈哈哈哈」这类排到后面
    for q in ([override] if override else []) + cands:
        for b, d in mine:
            if flat(q) in b:
                return q, d
        if q == override:
            print(f'  {person}：config 里的原话核对不上 TA 的任何一条消息，改用人物志里的引语')
    return None


def screenshot(jobs, width, height):
    """jobs=[(html 路径, png 路径)]。用 Python Playwright 截图；没装就返回 False 并提示。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('没装 Playwright，只出 HTML（要 PNG：pip install playwright && python3 -m playwright install chromium）')
        return False
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:  # 没下载自带浏览器时，退到系统装的 Chrome
            try:
                browser = p.chromium.launch(channel='chrome')
            except Exception as e:
                print(f'Playwright 启动浏览器失败（{e.__class__.__name__}），只出 HTML。试试 python3 -m playwright install chromium')
                return False
        page = browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
        for src, dst in jobs:
            page.goto(Path(src).resolve().as_uri())
            page.evaluate('document.fonts.ready')
            page.wait_for_timeout(300)
            page.screenshot(path=str(dst), clip={'x': 0, 'y': 0, 'width': width, 'height': height})
        browser.close()
    return True
