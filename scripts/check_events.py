"""机检事件 JSON（抽取/合并的产物）→ 打印逐条警告与汇总。冻结前跑一遍，把警告交回抽取/合并子任务或主控修。

用法：
  python3 scripts/check_events.py --project <dir> [--dir events part_events] [--strict]

--dir 默认 events 和 part_events（work/ 下）；也可写 stable（refs 已是稳定键，同样能查）。
检查项（规则来自 prompts/01、02 与 CONTRACT.md）：
  字段齐全；title ≤14 字、summary ≤80 字、month_summary ≤30 字；category 合法；heat ∈ 1/2/3；
  refs 2–6 条、都存在于 all.json、都在本月、按时间排序；
  date 必须等于最早一条 ref 的日期（早于或晚于都报）；
  refs 跨度 >3 天：可能把隔几天重演的梗合成了一件（prompts/01「同一件事」的界定）；
  people 都在 config.members / people / aliases 里（作者本人写 config.me，不写 me）；groups 都是 config 里的群 label。
只报警告，不改文件；--strict 时有警告就以退出码 1 结束。
"""
import collections
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ME, args, load_all, members  # noqa: E402

CATS = {'人生节点', '聚会出行', '群内热议', '名场面'}
FIELDS = ('date', 'title', 'summary', 'people', 'category', 'heat', 'refs', 'groups')
SPAN_DAYS = 3
LIMITS = {'zh': (14, 80, 30), 'en': (48, 240, 90)}  # title / summary / month_summary，按 config.lang


def extra(p):
    p.add_argument('--dir', nargs='*', default=['events', 'part_events'], help='work/ 下要检查的目录，默认 events part_events')
    p.add_argument('--strict', action='store_true', help='有警告时退出码为 1')


def days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    lt, ls, lm = LIMITS.get(cfg.get('lang') or 'zh', LIMITS['zh'])
    allm = load_all(a)
    msg = {m['id']: m for m in allm}
    msg.update({m['k']: m for m in allm})
    me = cfg.get('me')
    known = set(members(cfg, allm)) | set((cfg.get('aliases') or {}).values()) | ({me} if me else set())
    labels = {g['label'] for g in cfg.get('groups') or []}
    kinds = collections.Counter()
    nfile = nev = 0
    for d in a.dir:
        for f in sorted((a.work / d).glob('*.json')):
            nfile += 1
            warns = []

            def warn(kind, text):
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
                tag = f'#{i} {e.get("date", "?")}「{e.get("title", "")}」'
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
                refs = e.get('refs') or []
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
            if warns:
                print(f'\n{d}/{f.name}（{len(data.get("events") or [])} 个事件，{len(warns)} 条警告）\n  - ' + '\n  - '.join(warns))
    print(f'\n共检查 {nfile} 个文件、{nev} 个事件；警告 {sum(kinds.values())} 条'
          + ('：' + '，'.join(f'{k} {n}' for k, n in kinds.most_common()) if kinds else '。'))
    if a.strict and kinds:
        sys.exit(1)


if __name__ == '__main__':
    main()
