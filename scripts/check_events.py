"""机检事件 JSON（抽取/合并的产物）→ 打印逐条警告与汇总。冻结前跑一遍，把警告交回抽取/合并子任务或主控修。

用法：
  python3 scripts/check_events.py --project <dir> [--dir events part_events] [--only 2023-05 2023-06_p1] [--strict]
  python3 scripts/check_events.py --project <dir> --allow <事件键> --rule <规则> --note "为什么合理"   标记“已看过、保留”

--dir 默认 events 和 part_events（work/ 下）；也可写 stable（refs 已是稳定键，同样能查）或 cards（统一阅读 00 的卡片）。
--only 只查文件名以这些月份/分段开头的文件（子任务交稿前自检用；月份 2023-05 也会查到 events/2023-05.json）。
检查项（规则来自 prompts/01、02 与 CONTRACT.md）：
  字段齐全；title ≤14 字、summary ≤80 字、month_summary ≤30 字；category 合法；heat ∈ 1/2/3；
  refs 2–6 条、都存在于 all.json、都在本月、按时间排序；
  date 必须等于最早一条 ref 的日期（早于或晚于都报）；
  refs 跨度 >3 天：可能把隔几天重演的梗合成了一件（prompts/01「同一件事」的界定）；
  people 都在 config.members / people / aliases 里（作者本人写 config.me，不写 me）；groups 都是 config 里的群 label；
  代词与性别不符（启发式）：title/summary 的一句话里点到的人在 config.gender 里性别都相同，却用了相反性别的代词
    （男→“她”，女→“他”；英文 he/she 同理）；句里有性别没配的人、或有异性亲属/伴侣等称呼时不报。宁可少报。
    家属、伴侣等非成员写进 config.gender 也会参与判断（避免“老唐和小雨…她”误报）。
已看过、确实合理的警告（如两头各一条消息、拆开反而说不清的跨度）可以标记保留：--allow <事件键> --rule <规则>，
  写进 work/check_allow.json（事件键是警告里“键 X”那串——第一条 ref 的稳定键，冻结前后都认；规则写警告种类里的
  几个字即可，如 跨度、代词）。标过的警告单列“已确认保留”，不算“未处理”。字段缺失、refs 不存在/跨月、JSON 不合法等
  会让冻结或页面出错的不能标。
只报警告，不改文件；--strict 时有未处理的警告就以退出码 1 结束。pipeline 的 check 阶段要求“未处理 0 条”。
"""
import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ME, args, load_all, members  # noqa: E402

CATS = {'人生节点', '聚会出行', '群内热议', '名场面'}
FIELDS = ('date', 'title', 'summary', 'people', 'category', 'heat', 'refs', 'groups')
SPAN_DAYS = 3
LIMITS = {'zh': (14, 80, 30), 'en': (48, 240, 90)}  # title / summary / month_summary，按 config.lang
SOFT = ('title 超长', 'summary 超长', 'month_summary 超长', 'refs 数量', 'refs 未排序', 'date ≠ 最早引用', f'refs 跨度 >{SPAN_DAYS} 天',
        'people 写了 me', 'people 不认识', '代词与性别不符')  # 可以标“已确认保留”的警告种类
HARD = {'JSON 不合法', '缺字段', 'refs 不存在', 'refs 跨月', 'category 不合法', 'heat 不合法', 'groups 不认识'}  # 不能标“已确认”
ALLOW_FILE = 'check_allow.json'

# 性别代词：相反代词（排除“其他、吉他、他们、她们”这类）+ 句里出现就不报的异性称呼（多半指的是别人）
PRON = {
    'M': (re.compile(r'她(?!们)'), re.compile(r'\b(she|her|hers|herself)\b', re.I)),
    'F': (re.compile(r'(?<![其吉])他(?![们人俩乡日处])'), re.compile(r'\b(he|him|his|himself)\b', re.I)),
}
OTHERS = {
    'M': (re.compile(r'女|妈|母|姐|妹|妻|婆|媳|奶|姥|姨|嫂|闺|娘|妞'),
          re.compile(r'\b(girlfriend|wife|mom|mum|mother|sister|daughter|aunt|grandma|woman|girl|lady)s?\b', re.I)),
    'F': (re.compile(r'男|爸|父|哥|弟|夫|老公|爷|叔|伯|舅|儿子|小伙'),
          re.compile(r'\b(boyfriend|husband|dad|father|brother|son|uncle|grandpa|man|guy|boy)s?\b', re.I)),
}
SENT = re.compile(r'[。！？!?；;\n]|\.\s')


def extra(p):
    p.add_argument('--dir', nargs='*', default=['events', 'part_events'], help='work/ 下要检查的目录，默认 events part_events')
    p.add_argument('--only', nargs='*', default=[], help='只查这些月份/分段的文件（文件名前缀）')
    p.add_argument('--strict', action='store_true', help='有未处理的警告时退出码为 1')
    p.add_argument('--allow', metavar='事件键', help='把这个事件的某条警告标为已确认保留（写 work/check_allow.json）')
    p.add_argument('--rule', help='配合 --allow：警告种类（写其中几个字即可，如 跨度、代词）')
    p.add_argument('--note', default='', help='配合 --allow：为什么合理')


def days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def sex(g):
    g = str(g or '').strip().lower()
    if g[:1] == '男' or g in ('m', 'male', 'man', 'boy', 'he'):
        return 'M'
    if g[:1] == '女' or g in ('f', 'female', 'woman', 'girl', 'she'):
        return 'F'
    return None


def gender_names(cfg):
    """称呼 → (显示名, M/F/None)：config.gender 里的人（含家属等非成员）与全体成员；称呼含显示名、aliases、nicknames。"""
    gs = {p: sex(g) for p, g in (cfg.get('gender') or {}).items()}
    out = {}
    for p in set(gs) | set(cfg.get('members') or []) | set(cfg.get('core') or []) | set(cfg.get('people') or []):
        ns = {p} | {k for k, v in (cfg.get('aliases') or {}).items() if v == p} | set((cfg.get('nicknames') or {}).get(p, []))
        for n in ns:
            if len(n) >= 2 and not n.isdigit():
                out[n] = (p, gs.get(p))
    return out if any(g for _, g in out.values()) else {}


def gender_warnings(cfg, ev, names=None):
    """一个事件的 title/summary 里，一句话点到的人性别都已知且相同、却用了相反性别的代词 → [提示文字]。
    句里有性别没配的人、或有异性称呼（妈、女友、哥…，多半指别人）时不报。启发式，宁可少报。"""
    names = gender_names(cfg) if names is None else names
    if not names:
        return []
    pat = re.compile('|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)))
    out = []
    for field in ('title', 'summary'):
        for s in SENT.split(ev.get(field) or ''):
            who = {names[m.group(0)] for m in pat.finditer(s)}
            gs = {g for _, g in who}
            if not who or len(gs) != 1 or None in gs:
                continue
            g = gs.pop()
            rest = pat.sub('＃', s)
            zh, en = PRON[g]
            hit = zh.search(rest) or en.search(rest)
            if not hit or any(o.search(rest) for o in OTHERS[g]):
                continue
            ps = '、'.join(sorted({p for p, _ in who}))
            out.append(f'{field} 里「{s.strip()[:30]}」点到的 {ps} 在 config.gender 里是{"男" if g == "M" else "女"}，却用了“{hit.group(0)}”'
                       '（指的是别人就把那人写进 config.gender，或 --allow 标记保留）')
    return out


def load_allow(work):
    f = work / ALLOW_FILE
    try:
        return json.loads(f.read_text(encoding='utf-8')) if f.exists() else []
    except json.JSONDecodeError as e:
        sys.exit(f'{f} 不是合法 JSON：{e}')


def add_allow(a):
    if not a.rule:
        sys.exit('--allow 要配 --rule（警告种类里的几个字，如 跨度、代词）')
    hit = [k for k in SOFT if same(a.rule, k)]
    if not hit:
        hard = [k for k in HARD if same(a.rule, k)]
        sys.exit(f'「{a.rule}」' + ('这类警告会让冻结或页面出错，不能标为保留，请改事件文件' if hard else
                                    f'对不上可标记的警告种类（{"、".join(SOFT)}），写其中几个字'))
    rows = [r for r in load_allow(a.work) if not (r.get('event') == a.allow and r.get('rule') == a.rule)]
    rows.append({'event': a.allow, 'rule': a.rule, 'note': a.note})
    a.work.mkdir(parents=True, exist_ok=True)
    (a.work / ALLOW_FILE).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'已标记保留：事件 {a.allow} 的「{a.rule}」警告（{a.work / ALLOW_FILE}）')


def same(rule, kind):
    return bool(rule) and rule.replace(' ', '') in kind.replace(' ', '')


def picked(stem, only):
    return not only or any(stem == x or stem.startswith(x + '_') or stem.startswith(x + '-')
                           or (len(stem) == 7 and x[:7] == stem) for x in only)


def main():
    a = args(__doc__, extra)
    if a.allow:
        add_allow(a)
    cfg = a.cfg
    lt, ls, lm = LIMITS.get(cfg.get('lang') or 'zh', LIMITS['zh'])
    allm = load_all(a)
    msg = {m['id']: m for m in allm}
    msg.update({m['k']: m for m in allm})
    me = cfg.get('me')
    known = set(members(cfg, allm)) | set((cfg.get('aliases') or {}).values()) | ({me} if me else set())
    labels = {g['label'] for g in cfg.get('groups') or []}
    gnames = gender_names(cfg)
    allow = load_allow(a.work)
    kinds, ok_kinds = collections.Counter(), collections.Counter()
    nfile = nev = 0
    for d in a.dir:
        for f in sorted((a.work / d).glob('*.json')):
            if not picked(f.stem, a.only):
                continue
            nfile += 1
            warns, oks = [], []
            key = None

            def warn(kind, text):
                rule = next((r for r in allow if key and r.get('event') == key and same(r.get('rule'), kind)), None)
                if rule and kind in SOFT:
                    ok_kinds[kind] += 1
                    oks.append(f'{text}（已确认保留{"：" + rule["note"] if rule.get("note") else ""}）')
                else:
                    kinds[kind] += 1
                    warns.append(text)
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except json.JSONDecodeError as e:
                warn('JSON 不合法', f'JSON 不合法：{e}')
                print(f'\n{d}/{f.name}\n  - ' + '\n  - '.join(warns))
                continue
            mon = data.get('month') or f.stem[:7]
            if len(data.get('month_summary') or '') > lm:
                warn('month_summary 超长', f'month_summary {len(data["month_summary"])} 字（≤{lm}）')
            for i, e in enumerate(data.get('events') or []):
                nev += 1
                refs = e.get('refs') or []
                key = msg[refs[0]]['k'] if refs and refs[0] in msg else None
                tag = f'#{i} {e.get("date", "?")}「{e.get("title", "")}」' + (f'（键 {key}）' if key else '')
                miss = [k for k in FIELDS if k not in e]
                if miss:
                    warn('缺字段', f'{tag} 缺字段 {"/".join(miss)}')
                if len(e.get('title') or '') > lt:
                    warn('title 超长', f'{tag} title {len(e["title"])} 字（≤{lt}）')
                if len(e.get('summary') or '') > ls:
                    warn('summary 超长', f'{tag} summary {len(e["summary"])} 字（≤{ls}）')
                if 'category' in e and e['category'] not in CATS:
                    warn('category 不合法', f'{tag} category「{e["category"]}」不在 {"/".join(sorted(CATS))}')
                if 'heat' in e and e['heat'] not in (1, 2, 3):
                    warn('heat 不合法', f'{tag} heat={e["heat"]!r}（应为 1/2/3）')
                if not 2 <= len(refs) <= 6:
                    warn('refs 数量', f'{tag} refs {len(refs)} 条（应 2–6 条）')
                bad = [r for r in refs if r not in msg]
                if bad:
                    warn('refs 不存在', f'{tag} refs 在 all.json 里找不到：{"、".join(bad)}')
                ts = [msg[r]['t'] for r in refs if r in msg]
                other = [r for r in refs if r in msg and msg[r]['t'][:7] != mon]
                if other:
                    warn('refs 跨月', f'{tag} refs 不在 {mon}：{"、".join(other)}')
                if ts != sorted(ts):
                    warn('refs 未排序', f'{tag} refs 没按时间排序')
                if ts:
                    first, last = min(ts)[:10], max(ts)[:10]
                    if e.get('date') and e['date'] != first:
                        warn('date ≠ 最早引用', f'{tag} date 应为最早一条 ref 的日期 {first}')
                    if days(first, last) > SPAN_DAYS:
                        warn(f'refs 跨度 >{SPAN_DAYS} 天', f'{tag} refs 跨 {first} ~ {last}：同一场活动/连续讨论才算一件，隔几天重演的梗应各自成事件')
                ps = e.get('people') or []
                if ME in ps:
                    warn('people 写了 me', f'{tag} people 里写了 me，作者本人应写「{me}」')
                unknown = [p for p in ps if p != ME and p not in known]
                if unknown:
                    warn('people 不认识', f'{tag} people 不在 members/people/aliases 里：{"、".join(unknown)}（家属/外号？确认后补进 config）')
                gbad = [g for g in e.get('groups') or [] if g not in labels]
                if gbad:
                    warn('groups 不认识', f'{tag} groups 不是 config 里的群 label：{"、".join(gbad)}')
                for g in gender_warnings(cfg, e, gnames):
                    warn('代词与性别不符', f'{tag} {g}')
            key = None
            if warns or oks:
                print(f'\n{d}/{f.name}（{len(data.get("events") or [])} 个事件，{len(warns)} 条警告'
                      + (f'，{len(oks)} 条已确认保留' if oks else '') + '）'
                      + ''.join(f'\n  - {w}' for w in warns) + ''.join(f'\n  · {w}' for w in oks))
    total = sum(kinds.values()) + sum(ok_kinds.values())
    print(f'\n共检查 {nfile} 个文件、{nev} 个事件；警告 {total} 条，已确认保留 {sum(ok_kinds.values())} 条，'
          f'未处理 {sum(kinds.values())} 条' + ('：' + '，'.join(f'{k} {n}' for k, n in kinds.most_common()) if kinds else '。'))
    if kinds:
        print('修法：' + ('已冻结的（work/stable/）用 apply_fixes.py 修订清单改（E:月-序号，序号即上面的 #）。' if 'stable' in a.dir else
                         '还没冻结，直接改 ' + '、'.join(f'work/{x}/' for x in a.dir) + ' 里的事件文件，或把警告交回抽取/合并子任务。')
              + '看过确实合理的（如两头各一条消息、拆开反而说不清的跨度）可标记保留：'
              'check_events.py --allow <键> --rule <规则几个字> --note "理由"。')
    if a.strict and kinds:
        sys.exit(1)


if __name__ == '__main__':
    main()
