"""每人随机抽 N 条文字消息（固定种子），每条带同群前两句上下文 → work/base/<人>-sample.txt。

用法：
  python3 scripts/baseline_sample.py --project <dir> [--n 500] [--seed 42] [--person 张三 ...]

用途：人物模型的“基线语料”——看 TA 平时真实的说话分布，而不是只看名场面。按时间排序输出。
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, display, is_text, load_all, people, safe, sender_key  # noqa: E402


def extra(p):
    p.add_argument('--n', type=int, default=500)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--person', nargs='*', help='只处理这些人')


def main():
    a = args(__doc__, extra)
    allm = load_all(a)
    prev, last = [], {}
    for i, m in enumerate(allm):
        prev.append(last.get(m['g']))
        last[m['g']] = i
    out = a.work / 'base'
    out.mkdir(parents=True, exist_ok=True)
    for p in people(a.cfg, a.person):
        s = sender_key(a.cfg, p)
        pool = [i for i, m in enumerate(allm) if m['s'] == s and is_text(m)]
        pick = sorted(random.Random(f'{a.seed}:{p}').sample(pool, min(a.n, len(pool))))
        lines = [f'# {p} 随机文字消息 {len(pick)}/{len(pool)} 条（种子 {a.seed}），每条前附同群上两句', '']
        for n, i in enumerate(pick, 1):
            m = allm[i]
            lines.append(f'### {n}  {m["t"][:16]} ‹{m["g"]}›')
            c1 = prev[i]
            c2 = prev[c1] if c1 is not None else None
            for j in (c2, c1):
                if j is not None:
                    lines.append(f'  {display(a.cfg, allm[j]["s"])}: {allm[j]["c"][:120]}')
            lines.append(f'► {p}: {m["c"]}')
            lines.append('')
        (out / f'{safe(p)}-sample.txt').write_text('\n'.join(lines), encoding='utf-8')
        print(f'{p}: {len(pick)}/{len(pool)} 条')


if __name__ == '__main__':
    main()
