"""把修订清单应用到 work/stable/*.json，以及（可选）成品 HTML 里内嵌的 `const DATA=` 数据。

用法：
  python3 scripts/apply_fixes.py --project <dir> fixes1.json [fixes2.json ...] [--html out/chronicle.html ...] [--dry-run]

清单每条（见 CONTRACT.md）：
  {"key": "E:<YYYY-MM>-<序号>", "field": "title|summary|date|category", "old": "原文片段", "new": "新文", "why": "依据"}
  {"key": "M:<YYYY-MM>", "field": "summary", "old": "...", "new": "..."}
  {"key": "E:<YYYY-MM>-<序号>", "field": "people", "add": "显示名"}      # 也可 "remove": "显示名"
<序号> 是该月 events 数组里的下标（从 0 开始）。
`old` 必须在该字段里恰好出现一次，任何一条对不上则整批都不写。

HTML 约定：页面里有一段 `const DATA=<JSON>;`，JSON 里 months[] 每项含 month、summary（或 month_summary）、events[]，
且 events 顺序与 stable/ 一致（build 脚本从 stable/ 生成时自然满足）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args  # noqa: E402

MARK = 'const DATA='


def extra(p):
    p.add_argument('fixes', nargs='+', help='修订清单 JSON 文件')
    p.add_argument('--html', nargs='*', default=[], help='同时修改的成品 HTML（相对项目目录或绝对路径）')
    p.add_argument('--dry-run', action='store_true', help='只检查不写入')


def load_html(path):
    src = path.read_text(encoding='utf-8')
    i = src.index(MARK) + len(MARK)
    data, end = json.JSONDecoder().raw_decode(src, i)
    return src, i, end, data


def main():
    a = args(__doc__, extra)
    fixes = [fx for f in a.fixes for fx in json.loads(Path(f).read_text(encoding='utf-8'))]
    sdir = a.work / 'stable'
    stable = {}
    htmls = []
    for h in a.html:
        hp = Path(h) if Path(h).is_absolute() else a.project / h
        src, i, end, data = load_html(hp)
        htmls.append((hp, src, i, end, data, {m['month']: m for m in data['months']}))

    def stable_month(mon):
        if mon not in stable:
            f = sdir / f'{mon}.json'
            if not f.exists():
                raise KeyError(f'找不到 {f}')
            stable[mon] = json.loads(f.read_text(encoding='utf-8'))
        return stable[mon]

    def targets(fx):
        kind, ref = fx['key'].split(':', 1)
        if kind == 'M':
            out = [(stable_month(ref), 'month_summary')]
            for *_, months in htmls:
                m = months[ref]
                out.append((m, 'month_summary' if 'month_summary' in m else 'summary'))
            return out
        if kind == 'E':
            mon, idx = ref.rsplit('-', 1)
            out = [(stable_month(mon)['events'][int(idx)], fx['field'])]
            for *_, months in htmls:
                out.append((months[mon]['events'][int(idx)], fx['field']))
            return out
        raise KeyError(f'不认识的 key：{fx["key"]}（只支持 E: / M:）')

    errors = []
    for fx in fixes:
        try:
            tg = targets(fx)
        except (KeyError, IndexError, ValueError) as e:
            errors.append(f'{fx.get("key")}: {e}')
            continue
        for obj, field in tg:
            if field == 'people':
                ps = obj.setdefault('people', [])
                if fx.get('add') and fx['add'] not in ps:
                    ps.append(fx['add'])
                if fx.get('remove') in ps:
                    ps.remove(fx['remove'])
                continue
            val = obj.get(field, '')
            n = val.count(fx['old']) if fx.get('old') else 0
            if n != 1:
                errors.append(f'{fx["key"]} {field}: 「{fx.get("old")}」出现 {n} 次')
                break
            obj[field] = val.replace(fx['old'], fx['new'])
    if errors:
        sys.exit('未写入，以下修改对不上：\n' + '\n'.join(errors))
    if a.dry_run:
        print(f'检查通过：{len(fixes)} 处修改（dry-run，未写入）')
        return
    for mon, d in stable.items():
        (sdir / f'{mon}.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    for hp, src, i, end, data, _ in htmls:
        payload = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
        hp.write_text(src[:i] + payload + src[end:], encoding='utf-8')
    print(f'已应用 {len(fixes)} 处修改（stable {len(stable)} 个月' + (f'，HTML {len(htmls)} 个' if htmls else '') + '）')


if __name__ == '__main__':
    main()
