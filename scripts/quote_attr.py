"""核对人物模型/小传里的引语是不是本人说的 → work/attr/<人>.md。

用法：
  python3 scripts/quote_attr.py --project <dir> --person 张三 --md out/personas/张三.md

抽出 markdown 里所有引号内 4–40 字的片段（「」 “” "" 三种），按片段回 all.json 的文字消息里查实际说话人：
- 本人说过 → 通过
- 只有别人说过 → 「非本人所说」，列出实际说话人与一个出处
- 哪都找不到 → 「原文未找到」（可能是改写、编造，或者引号里本来就不是原话，如称呼/术语，需人工看）
匹配时忽略空白和 ⏎；引语里有省略号（… / ...）时按最长的一段去查。
“文字消息”含带配文的图片/链接（`[图片] 配文`）。
另附「引语语境」：每条找得到的引语取一处出处（优先本人说的那条），列出同群前后各 --context 条（默认 5），
供终审核对语境（谁接的话、是不是复读梗/玩笑/替别人配的台词）。--context 0 不输出。
"""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, body, display, is_text, load_all, safe, sender_key  # noqa: E402

QUOTE = re.compile(r'「([^「」]{4,40})」|“([^“”]{4,40})”|"([^"\n]{4,40})"')


def norm(t):
    return re.sub(r'\s|⏎', '', t)


def extra(p):
    p.add_argument('--person', required=True, help='这份 markdown 写的是谁（config 里的显示名）')
    p.add_argument('--md', required=True, help='人物模型/小传 markdown 路径')
    p.add_argument('--context', type=int, default=5, help='引语语境：出处前后各取几条同群消息，默认 5，0=不输出')


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    s = sender_key(cfg, a.person)
    md = Path(a.md)
    if not md.is_absolute() and not md.exists():
        md = a.project / md
    quotes = list(dict.fromkeys(next(g for g in m.groups() if g) for m in QUOTE.finditer(md.read_text(encoding='utf-8'))))
    allm = load_all(a)
    pos = {m['id']: i for i, m in enumerate(allm)}
    msgs = [(norm(body(m['c'])), m) for m in allm if is_text(m)]
    ok, wrong, missing = [], [], []
    where = {}  # 引语 → 一处出处（优先本人）
    for q in quotes:
        segs = [x for x in re.split(r'…+|\.{3,}|⏎', norm(q)) if x]
        key = max(segs, key=len) if segs else ''
        if len(key) < 2:
            continue
        hits = [m for t, m in msgs if key in t]
        who = collections.Counter(m['s'] for m in hits)
        if hits:
            mine = [m for m in hits if m['s'] == s]
            where[q] = ((mine or hits)[0], len(hits))
        if s in who:
            ok.append(q)
        elif hits:
            first = hits[0]
            wrong.append((q, '、'.join(f'{display(cfg, x)}×{n}' for x, n in who.most_common(3)), f'{first["t"][:16]} ‹{first["g"]}› {first["c"][:60]}'))
        else:
            missing.append(q)
    esc = lambda t: t.replace('|', '\\|')  # noqa: E731
    lines = [f'# {a.person} 引语核对：{md.name}', '',
             f'共 {len(quotes)} 条引语：本人说过 {len(ok)}，非本人所说 {len(wrong)}，原文未找到 {len(missing)}。', '',
             '## 非本人所说', '', '| 引语 | 实际说话人 | 出处 |', '|---|---|---|']
    lines += [f'| {esc(q)} | {esc(w)} | {esc(src)} |' for q, w, src in wrong] or ['| （无） | | |']
    lines += ['', '## 原文未找到', '', '| 引语 |', '|---|']
    lines += [f'| {esc(q)} |' for q in missing] or ['| （无） |']
    if a.context > 0 and where:
        lines += ['', f'## 引语语境（出处前后各 {a.context} 条同群消息；► 为出处）', '']
        for q in quotes:
            if q not in where:
                continue
            m, n = where[q]
            i = pos[m['id']]
            before, after, j, k = [], [], i - 1, i + 1
            while j >= 0 and len(before) < a.context:
                if allm[j]['g'] == m['g']:
                    before.append(j)
                j -= 1
            while k < len(allm) and len(after) < a.context:
                if allm[k]['g'] == m['g']:
                    after.append(k)
                k += 1
            lines += [f'### 「{q}」' + (f'（共 {n} 处出现，这里取第一处）' if n > 1 else ''), '```']
            for x in before[::-1] + [i] + after:
                mm = allm[x]
                lines.append(f'{"►" if x == i else " "} {mm["t"][:16]} {display(cfg, mm["s"])}: {mm["c"][:100]}')
            lines += ['```', '']
    out = a.work / 'attr'
    out.mkdir(parents=True, exist_ok=True)
    (out / f'{safe(a.person)}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{a.person}: {len(quotes)} 条引语，非本人 {len(wrong)}，未找到 {len(missing)} → {out / (safe(a.person) + ".md")}')


if __name__ == '__main__':
    main()
