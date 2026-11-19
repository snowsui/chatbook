"""把 work/all.json 按月切成事件抽取的输入分段 → work/chunks/<YYYY-MM>_p<i>.txt。

用法：
  python3 scripts/split_chunks.py --project <dir> [--max-chars 50000] [--from 2019-01] [--to 2020-12]

每段文件头：月份、第 i/n 段、日期范围、本月消息数（去掉纯图片/表情前后）、本段行数、本月最热的几天（消息数/发言人数）。
之后每行：`id|群|日 时:分|发言人: 内容`。纯图片/表情行（内容恰好是 `[图片]` 或 `[表情]`）已去掉；带配文的 `[图片] 配文` 保留。
一个月超过 --max-chars 字就按行切成多段（不拆行）。重跑会先清空 work/chunks/*.txt。
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, load_all  # noqa: E402


def extra(p):
    p.add_argument('--max-chars', type=int, default=50000, help='每段最大字数，默认 50000')
    p.add_argument('--from', dest='start', help='起始月份 YYYY-MM（含）')
    p.add_argument('--to', dest='end', help='结束月份 YYYY-MM（含）')


def main():
    a = args(__doc__, extra)
    allm = load_all(a)
    out = a.work / 'chunks'
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob('*.txt'):
        f.unlink()
    bym = collections.defaultdict(list)
    for m in allm:
        mon = m['t'][:7]
        if (a.start and mon < a.start) or (a.end and mon > a.end):
            continue
        bym[mon].append(m)
    files = 0
    for mon, ms in sorted(bym.items()):
        days = collections.Counter(m['t'][:10] for m in ms)
        spk = collections.defaultdict(set)
        for m in ms:
            spk[m['t'][:10]].add(m['s'])
        hot = '；'.join('%s %d条/%d人' % (d, c, len(spk[d])) for d, c in days.most_common(6))
        lines = ['%s|%s|%s|%s: %s' % (m['id'], m['g'], m['t'][8:16], m['s'], m['c'])
                 for m in ms if m['c'] not in ('[图片]', '[表情]')]
        parts, cur, size = [], [], 0
        for line in lines:
            if size + len(line) > a.max_chars and cur:
                parts.append(cur)
                cur, size = [], 0
            cur.append(line)
            size += len(line) + 1
        if cur:
            parts.append(cur)
        for i, p in enumerate(parts):
            head = ('月份 %s（第 %d/%d 段，%s 至 %s 日）。本月共 %d 条消息，去掉纯图片/表情后 %d 行；本段 %d 条（文件共 %d 行，含 3 行文件头）。\n'
                    '本月最热的几天（消息数/发言人数）：%s\n\n') % (
                mon, i + 1, len(parts), p[0].split('|')[2][:2], p[-1].split('|')[2][:2], len(ms), len(lines), len(p), len(p) + 3, hot)
            (out / f'{mon}_p{i + 1}.txt').write_text(head + '\n'.join(p), encoding='utf-8')
            files += 1
        print(f'{mon}: {len(ms)} 条（去掉纯图片/表情后 {len(lines)} 行）→ {len(parts)} 段')
    print(f'共 {len(bym)} 个月、{files} 个分段 → {out}')


if __name__ == '__main__':
    main()
