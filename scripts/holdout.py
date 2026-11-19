"""人物模型盲测题：按年份分层随机抽 N 个情境 → work/holdout/<人>-q.md（题目）与 <人>-a.md（答案）。

用法：
  python3 scripts/holdout.py --project <dir> [--n 12] [--seed 7] [--person 张三 ...]
                             [--exclude-dates-from <dir> ...] [--sensitive '医院|生病|...']

规则：
- 以 turn（同群连续同一人的发言）为单位；不过滤短回复（只要求 turn 里至少有一条文字消息）。
- 每个情境给本人发言前最多 6 条同群他人上下文（遇到本人上一句即停，且只取 6 小时内的），没有上下文的不要。
- 上下文或答案含敏感词的情境跳过。敏感词正则：--sensitive > config.holdout_sensitive（列表）> 默认表。
- --exclude-dates-from：扫描这些目录下所有文件里出现的 YYYY-MM-DD，这些日期不出题（避免与已用材料重复）。
- 同一天只出一题；年份轮流抽，尽量每年都有。
"""
import collections
import random
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, display, is_text, load_all, people, safe, sender_key, turns  # noqa: E402

DEFAULT_SENSITIVE = ['医院', '生病', '住院', '手术', '怀孕', '备孕', '流产', '离职', '裁员', '辞退', '工资', '薪水',
                     '分手', '离婚', '相亲', '结婚', '去世', '葬礼', '借钱', '欠钱', '密码', '验证码', '身份证', '银行卡']


def extra(p):
    p.add_argument('--n', type=int, default=12, help='每人题数，默认 12')
    p.add_argument('--seed', type=int, default=7)
    p.add_argument('--person', nargs='*', help='只处理这些人')
    p.add_argument('--exclude-dates-from', nargs='*', default=[], help='目录：其中出现过的日期不出题')
    p.add_argument('--sensitive', help='敏感词正则，覆盖配置和默认表')


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    sens = re.compile(a.sensitive or '|'.join(map(re.escape, cfg.get('holdout_sensitive') or DEFAULT_SENSITIVE)))
    used = set()
    for d in a.exclude_dates_from:
        for f in Path(d).rglob('*'):
            if f.is_file():
                used |= set(re.findall(r'\d{4}-\d{2}-\d{2}', f.read_text(encoding='utf-8', errors='ignore')))
    allm = load_all(a)
    ts = [datetime.strptime(m['t'], '%Y-%m-%d %H:%M:%S') for m in allm]
    prev, last = [], {}
    for i, m in enumerate(allm):
        prev.append(last.get(m['g']))
        last[m['g']] = i
    tl = turns(allm)
    out = a.work / 'holdout'
    out.mkdir(parents=True, exist_ok=True)
    for p in people(cfg, a.person):
        s = sender_key(cfg, p)
        rnd = random.Random(f'{a.seed}:{p}')
        byy = collections.defaultdict(list)
        skipped = collections.Counter()
        for g, sp, idx in tl:
            if sp != s or not any(is_text(allm[i]) for i in idx):
                continue
            day = allm[idx[0]]['t'][:10]
            if day in used:
                skipped['日期已用'] += 1
                continue
            ctx, j = [], prev[idx[0]]
            while j is not None and len(ctx) < 6 and allm[j]['s'] != s and (ts[idx[0]] - ts[j]).total_seconds() <= 6 * 3600:
                ctx.append(j)
                j = prev[j]
            if not ctx:
                continue
            if any(sens.search(allm[k]['c']) for k in ctx + idx):
                skipped['敏感词'] += 1
                continue
            byy[day[:4]].append((ctx[::-1], idx))
        cand = sum(len(v) for v in byy.values())
        for v in byy.values():
            rnd.shuffle(v)
        picks, days = [], set()
        years = sorted(byy)
        while len(picks) < a.n and any(byy[y] for y in years):
            for y in years:
                while byy[y]:
                    ctx, idx = byy[y].pop()
                    day = allm[idx[0]]['t'][:10]
                    if day not in days:
                        days.add(day)
                        picks.append((ctx, idx))
                        break
                if len(picks) >= a.n:
                    break
        picks.sort(key=lambda x: x[1][0])
        q = [f'# {p} 盲测题（{len(picks)} 题）', '',
             f'每题给出群聊上下文，请写出 {p} 接下来会说什么（一次发言，可以是多条、也可以只是一个表情）。', '']
        ans = [f'# {p} 盲测答案（{len(picks)} 题）', '']
        for n, (ctx, idx) in enumerate(picks, 1):
            m0 = allm[idx[0]]
            q.append(f'## 第 {n} 题  {m0["t"][:7]} ‹{m0["g"]}›')
            q += [f'  {allm[j]["t"][11:16]} {display(cfg, allm[j]["s"])}: {allm[j]["c"]}' for j in ctx]
            q += [f'→ {p}:', '']
            ans.append(f'## 第 {n} 题  {m0["t"][:16]} ‹{m0["g"]}›')
            ans += [f'  {allm[i]["t"][11:16]} {allm[i]["c"]}' for i in idx] + ['']
        (out / f'{safe(p)}-q.md').write_text('\n'.join(q), encoding='utf-8')
        (out / f'{safe(p)}-a.md').write_text('\n'.join(ans), encoding='utf-8')
        print(f'{p}: {len(picks)} 题（候选 {cand} 个；跳过 ' + ('、'.join(f'{k} {v}' for k, v in skipped.items()) or '无') + '）')


if __name__ == '__main__':
    main()
