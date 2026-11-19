"""核对小传/人物模型里每句引语的出处标注 → work/review/<人>-citations.md（引语出处表 + 问题清单）。

用法：
  python3 scripts/verify_citations.py --project <dir> --person 张三 --md out/portraits/张三.md [--context 3] [--strict]

标注写法（紧跟在引语的右引号后面，中间只能有空白；Markdown 渲染时看不见，build 脚本会去掉）：
  「原话」<!--k:A:7000123-->                 本人说的（k = all.json 的稳定键，从 evidence.md 里抄）
  「第一句…第二句」<!--k:A:7000123,A:7000124-->   一句引语跨连发的几条消息：k 用逗号隔开
  「别人的话」<!--k:A:7000130@老周-->         别人说的（@ 后写说话人显示名；作者本人写 config.me）
  「外号/术语」<!--k:none-->                  引号里不是原话（称呼、梗名、书名），明确声明免查
检查：
  - 每个 k 都在 all.json 里（error：k 不存在）
  - k 那条消息的说话人 = 引语所指的人（缺省 --person，或 @ 后的人）（error：说话人不符）
  - 引语文本在这些消息里：忽略空白/标点/⏎，按 … / ... 切段，每段（≥2 字）都要找得到（error：原文不符）
  - 标注前面紧挨着没有引语（error：标注落空）
  - 没有标注的引语（引号内 ≥4 字）列出（warning：未标注）
报告同时是「引语出处表」：每条引语的日期时间、说话人、出处前后各 --context 条同群消息（供终审看语境：谁接的、是不是复读梗/玩笑/替别人配的台词）。
--strict：有 error 或未标注时退出码 1（pipeline 用它判定小传/模型能不能标 done）。
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, body, display, load_all, safe  # noqa: E402

QUOTE = re.compile(r'「([^「」\n]{2,120})」|“([^“”\n]{2,120})”|"([^"\n]{2,120})"')
MARK = re.compile(r'<!--k:([^>]*?)-->')
STRIP = re.compile(r'<!--k:[^>]*?-->')
PUNCT = re.compile(r'[\s⏎，。！？、,.!?~～：:；;"“”\'‘’（）()【】\[\]《》<>—\-·]')
SPLIT = re.compile(r'…+|\.{3,}|⏎|／|/')
UNMARKED_MIN = 4


def norm(t):
    return PUNCT.sub('', t)


def segments(q):
    return [s for s in (norm(x) for x in SPLIT.split(q)) if len(s) >= 2]


def quote_in(q, text):
    """引语 q（可含省略号）是否出自 text：每段都要出现在 text 里。没有可查的段（太短）视为通过。"""
    t = norm(text)
    return all(s in t for s in segments(q))


def canon(cfg, name):
    """引语所指的人 → 统一显示名（经 aliases 归一）。"""
    name = name.strip()
    return (cfg.get('aliases') or {}).get(name, name)


def scan(text):
    """返回 [(引语, 起, 止)] 与 [(标注内容, 起, 止)]，都按位置排序。"""
    quotes = [(next(g for g in m.groups() if g is not None), m.start(), m.end()) for m in QUOTE.finditer(STRIP.sub(lambda x: ' ' * len(x.group(0)), text))]
    marks = [(m.group(1).strip(), m.start(), m.end()) for m in MARK.finditer(text)]
    return quotes, marks


def verify(cfg, allm, person, text):
    """核对一段 markdown。返回 dict(cited=[...], errors=[...], unmarked=[...], skipped=n)。
    cited 每项：(引语, 所指的人, [msg...])；errors 每项：(类型, 引语, 说明)。"""
    byk = {m['k']: (i, m) for i, m in enumerate(allm)}
    quotes, marks = scan(text)
    used, cited, errors, skipped = set(), [], [], 0
    for spec, s, _ in marks:
        prev = [q for q in quotes if q[2] <= s and not text[q[2]:s].strip()]
        if not prev:
            errors.append(('标注落空', '', f'<!--k:{spec}--> 前面紧挨着没有引语'))
            continue
        q = prev[-1]
        used.add(q[1])
        if spec.lower() in ('none', '-', ''):
            skipped += 1
            continue
        keys, _, who = spec.partition('@')
        who = canon(cfg, who) if who else person
        msgs, bad = [], False
        for k in (x.strip() for x in keys.split(',') if x.strip()):
            if k not in byk:
                errors.append(('k 不存在', q[0], f'{k} 不在 all.json 里'))
                bad = True
                continue
            msgs.append(byk[k])
        if bad or not msgs:
            continue
        actual = sorted({display(cfg, m['s']) for _, m in msgs})
        if actual != [who]:
            errors.append(('说话人不符', q[0], f'标注说是 {who}，原文说话人是 {"、".join(actual)}（{msgs[0][1]["t"][:16]}）'))
        if not quote_in(q[0], ''.join(body(m['c']) for _, m in msgs)):
            errors.append(('原文不符', q[0], f'{msgs[0][1]["k"]} 的原文是：{msgs[0][1]["c"][:80]}'))
        cited.append((q[0], who, msgs))
    unmarked = [q[0] for q in quotes if q[1] not in used and len(norm(q[0])) >= UNMARKED_MIN]
    return dict(cited=cited, errors=errors, unmarked=unmarked, skipped=skipped)


def context(allm, i, n):
    g = allm[i]['g']
    before, after, j, k = [], [], i - 1, i + 1
    while j >= 0 and len(before) < n:
        if allm[j]['g'] == g:
            before.append(j)
        j -= 1
    while k < len(allm) and len(after) < n:
        if allm[k]['g'] == g:
            after.append(k)
        k += 1
    return before[::-1] + [i] + after


def report(cfg, allm, person, name, r, n):
    esc = lambda t: t.replace('|', '\\|')  # noqa: E731
    lines = [f'# {person} 引语出处核对：{name}', '',
             f'已标注 {len(r["cited"])} 条（另 {r["skipped"]} 条声明非原话）；问题 {len(r["errors"])} 条；未标注 {len(r["unmarked"])} 条。', '',
             '## 问题', '', '| 类型 | 引语 | 说明 |', '|---|---|---|']
    lines += [f'| {t} | {esc(q)} | {esc(d)} |' for t, q, d in r['errors']] or ['| （无） | | |']
    lines += ['', '## 未标注的引语（补上 <!--k:…-->；不是原话的写 <!--k:none-->）', '']
    lines += [f'- 「{q}」' for q in r['unmarked']] or ['- （无）']
    lines += ['', '## 出处表', '', '| 引语 | 时间 | 说话人 | k |', '|---|---|---|---|']
    lines += [f'| {esc(q)} | {ms[0][1]["t"][:16]} | {who} | {"、".join(m["k"] for _, m in ms)} |' for q, who, ms in r['cited']] or ['| （无） | | | |']
    if n > 0 and r['cited']:
        lines += ['', f'## 引语语境（出处前后各 {n} 条同群消息；► 为出处）', '']
        for q, who, ms in r['cited']:
            lines += [f'### 「{q}」', '```']
            for x in context(allm, ms[0][0], n):
                mm = allm[x]
                lines.append(f'{"►" if x == ms[0][0] else " "} {mm["t"][:16]} {display(cfg, mm["s"])}: {mm["c"][:100]}')
            lines += ['```', '']
    return '\n'.join(lines) + '\n'


def extra(p):
    p.add_argument('--person', required=True, help='这份 markdown 写的是谁（config 里的显示名）')
    p.add_argument('--md', required=True, help='小传/人物模型 markdown 路径')
    p.add_argument('--context', type=int, default=3, help='出处前后各取几条同群消息，默认 3，0=不输出')
    p.add_argument('--out', help='报告路径，默认 work/review/<人>-citations.md')
    p.add_argument('--strict', action='store_true', help='有问题或未标注时退出码 1')


def main():
    a = args(__doc__, extra)
    md = Path(a.md)
    if not md.is_absolute() and not md.exists():
        md = a.project / md
    allm = load_all(a)
    r = verify(a.cfg, allm, canon(a.cfg, a.person), md.read_text(encoding='utf-8'))
    out = Path(a.out) if a.out else a.work / 'review' / f'{safe(a.person)}-citations.md'
    if not out.is_absolute():
        out = a.project / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(a.cfg, allm, a.person, md.name, r, a.context), encoding='utf-8')
    for t, q, d in r['errors']:
        print(f'  ✗ {t}：「{q}」 {d}')
    for q in r['unmarked']:
        print(f'  ? 未标注：「{q}」')
    print(f'{a.person}: 已标注 {len(r["cited"])}，问题 {len(r["errors"])}，未标注 {len(r["unmarked"])} → {out}')
    if a.strict and (r['errors'] or r['unmarked']):
        sys.exit(1)


if __name__ == '__main__':
    main()
