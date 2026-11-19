"""把 work/events/*.json 里 refs 的序号 ID（A123）换成稳定键 k（A:<平台消息ID>）→ work/stable/。

用法：
  python3 scripts/freeze.py --project <dir> [--force]

序号 ID 只在本次 ingest 内有效，重新导出后会变；所以已冻结的月份默认不重算（--force 强制重算，
只应在 events/ 与当前 all.json 出自同一次 ingest 时使用）。找不到的 ref 会被丢弃并计数。
写入前把事件按 date 稳定排序（同日保持原顺序）、每个事件的 refs 按时间排序，这样 stable/ 里的下标 = 页面上的显示顺序 = 修订清单 key
`E:月份-序号` 的序号。冻结前建议先跑 check_events.py 看机检警告。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, load_all  # noqa: E402


def main():
    a = args(__doc__, lambda p: p.add_argument('--force', action='store_true', help='已存在的 stable 文件也重算'))
    allm = load_all(a)
    idk = {m['id']: m['k'] for m in allm}
    pos = {m['k']: i for i, m in enumerate(allm)}
    src, dst = a.work / 'events', a.work / 'stable'
    dst.mkdir(parents=True, exist_ok=True)
    done = skip = 0
    for f in sorted(src.glob('*.json')):
        if (dst / f.name).exists() and not a.force:
            skip += 1
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        miss = 0
        for e in d['events']:
            refs = e.get('refs') or []
            miss += sum(r not in idk for r in refs)
            e['refs'] = sorted((idk[r] for r in refs if r in idk), key=pos.get)
        d['events'].sort(key=lambda e: e.get('date') or '')  # sort 是稳定的：同日保持原顺序
        (dst / f.name).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        done += 1
        print(f'{f.name}: {len(d["events"])} 个事件' + (f'，{miss} 个 ref 找不到已丢弃' if miss else ''))
    print(f'冻结 {done} 个月，跳过已冻结 {skip} 个 → {dst}')


if __name__ == '__main__':
    main()
