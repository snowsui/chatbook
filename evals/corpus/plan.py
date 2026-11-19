"""按天铺排合成语料的写作计划 → evals/corpus/<名>/plan/<YYYY-MM>.md（给写作子任务用）。

用法：python3 evals/corpus/plan.py <语料目录> --start 2023-09-01 --end 2025-08-31 --total 6000 [--seed 7]

每天给一个目标条数（工作日/周末/深夜差异 + 事件日加热 + 随机静默日），并列出当天的标准事件、禁区埋点、
当月每个人的身份阶段与改昵称日期。条数只是节奏参考，写作时 ±30% 都行。
"""
import argparse
import calendar
import json
import random
from datetime import date, timedelta
from pathlib import Path

BOOST = {3: 110, 2: 55, 1: 25}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('corpus')
    p.add_argument('--start', required=True)
    p.add_argument('--end', required=True)
    p.add_argument('--total', type=int, required=True)
    p.add_argument('--seed', type=int, default=7)
    p.add_argument('--quiet', type=float, default=0.12, help='静默日比例')
    a = p.parse_args()
    root = Path(a.corpus)
    rnd = random.Random(a.seed)
    truth = root / 'truth'
    events = json.loads((truth / 'events.json').read_text(encoding='utf-8'))
    taboo = json.loads((truth / 'taboo.json').read_text(encoding='utf-8'))
    personas = [json.loads(f.read_text(encoding='utf-8')) for f in sorted(truth.glob('persona_*.json'))]
    d0, d1 = date.fromisoformat(a.start), date.fromisoformat(a.end)
    days = [d0 + timedelta(i) for i in range((d1 - d0).days + 1)]
    w = {}
    for d in days:
        base = rnd.lognormvariate(0, 0.7) * (1.25 if d.weekday() >= 4 else 1.0)
        w[d] = 0 if rnd.random() < a.quiet else base
    raw_total = sum(w.values())
    boost = {d: 0 for d in days}
    for e in events:
        d = date.fromisoformat(e['date'])
        if d in boost:
            boost[d] += BOOST[e['heat']]
            if d + timedelta(1) in boost:
                boost[d + timedelta(1)] += BOOST[e['heat']] // 3
    for t in taboo:
        d = date.fromisoformat(t['date'])
        if d in boost:
            boost[d] += 12
    budget = a.total - sum(boost.values())
    target = {d: round(w[d] / raw_total * budget) + boost[d] for d in days}
    out = root / 'plan'
    out.mkdir(exist_ok=True)
    months = sorted({d.strftime('%Y-%m') for d in days})
    wk = '一二三四五六日'
    for mon in months:
        md = [d for d in days if d.strftime('%Y-%m') == mon]
        lines = [f'# {mon} 写作计划（目标约 {sum(target[d] for d in md)} 条）', '', '## 本月各人身份阶段']
        y, m = map(int, mon.split('-'))
        m_start, m_end = f'{mon}', f'{mon}'
        for ps in personas:
            stage = [s['what'] for s in ps['identity_timeline'] if s['from'] <= m_end and s['to'] >= m_start]
            nick = [n for n in ps['nickname_timeline'] if n['from'][:7] == mon and n['from'] != a.start]
            lines.append(f'- {ps["name"]}：' + ('；'.join(stage) or '（无变化）') +
                         ''.join(f'（{n["from"]} 起把群昵称改成“{n["nick"]}”，当天要有改名的对话）' for n in nick))
        lines += ['', '## 逐日', '', '| 日期 | 星期 | 目标条数 | 当天必须发生 |', '|---|---|---|---|']
        for d in md:
            must = [f'【事件 {e["id"]}】{e["title"]}：{e["summary"]}（参与：{"、".join(e["people"])}）'
                    for e in events if e['date'] == d.isoformat()]
            must += [f'【禁区埋点 {t["id"]}】{t["desc"]}——原文里要自然出现且逐字包含「{t["needles"][0]}」'
                     for t in taboo if t['date'] == d.isoformat()]
            lines.append(f'| {d.isoformat()} | {wk[d.weekday()]} | {target[d]} | {"<br>".join(must)} |')
        (out / f'{mon}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'{len(months)} 个月，合计目标 {sum(target.values())} 条 → {out}')


if __name__ == '__main__':
    main()
