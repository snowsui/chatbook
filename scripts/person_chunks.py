"""为 config.people 里每个人切出「本人全部文字发言 + 紧邻上一句他人上下文」→ work/people/<人>/chunks/NN.txt。
“文字发言”含带配文的图片/链接（`[图片] 配文`），与 split_chunks 口径一致；纯占位符（`[图片]`、`[语音]`…）不收。

用法：
  python3 scripts/person_chunks.py --project <dir> [--max-chars 160000] [--person 张三 ...]

格式：
  # <人> 文字发言 第 i/n 块（起止日期）
  ## 2020-05-03
    [李四:他人上一句前40字]
  12:30 本人内容
  12:31 ‹家属群› 本人内容          ← 非主群（groups[0] 以外）在时间后加群标记
上下文行只在本人这条的同群上一条是别人说的时才出现。按日切块，每块约 --max-chars 字。重跑会清空旧块。
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, display, is_text, load_all, main_group, people, safe, sender_key  # noqa: E402


def extra(p):
    p.add_argument('--max-chars', type=int, default=160000, help='每块约多少字，默认 160000')
    p.add_argument('--person', nargs='*', help='只处理这些人')


def main():
    a = args(__doc__, extra)
    allm = load_all(a)
    mg = main_group(a.cfg)
    prev_in_group = {}
    prev = []  # prev[i] = 同群上一条的下标
    for i, m in enumerate(allm):
        prev.append(prev_in_group.get(m['g']))
        prev_in_group[m['g']] = i
    for p in people(a.cfg, a.person):
        s = sender_key(a.cfg, p)
        days = collections.OrderedDict()
        for i, m in enumerate(allm):
            if m['s'] != s or not is_text(m):
                continue
            lines = days.setdefault(m['t'][:10], [])
            j = prev[i]
            if j is not None and allm[j]['s'] != s:
                lines.append(f'  [{display(a.cfg, allm[j]["s"])}:{allm[j]["c"][:40]}]')
            tag = f' ‹{m["g"]}›' if m['g'] != mg else ''
            lines.append(f'{m["t"][11:16]}{tag} {m["c"]}')
        blocks, cur, size = [], [], 0
        for day, lines in days.items():
            text = f'## {day}\n' + '\n'.join(lines)
            if size + len(text) > a.max_chars and cur:
                blocks.append(cur)
                cur, size = [], 0
            cur.append((day, text))
            size += len(text) + 1
        if cur:
            blocks.append(cur)
        out = a.work / 'people' / safe(p) / 'chunks'
        out.mkdir(parents=True, exist_ok=True)
        for f in out.glob('*.txt'):
            f.unlink()
        for bi, b in enumerate(blocks):
            head = f'# {p} 文字发言 第 {bi + 1}/{len(blocks)} 块（{b[0][0]} ~ {b[-1][0]}）\n\n'
            (out / f'{bi + 1:02d}.txt').write_text(head + '\n\n'.join(t for _, t in b), encoding='utf-8')
        n = sum(len([x for x in v if not x.startswith('  [')]) for v in days.values())
        print(f'{p}: {n} 条文字发言，{len(days)} 天 → {len(blocks)} 块')


if __name__ == '__main__':
    main()
