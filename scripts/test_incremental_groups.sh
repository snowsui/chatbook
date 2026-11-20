#!/usr/bin/env bash
# 多群增量的冒烟测试：基线按“群 × 月”记，各群同步进度不同、中途新接入一个群，都只读各群自己的新增部分。
# 用法：bash scripts/test_incremental_groups.sh      （在临时目录里跑；KEEP=<空目录> 则保留产物）
# 合成：A 周末群（txt，没有消息 ID）导出到 10-10，B 家属群（json-array，有消息 ID）导出到 10-20；09、10 两个月已冻结。
# 覆盖：旧版基线（按月混在一起）自动换算 → commit 存成新版（每群 label/last/months）
#       → A 补同步到 10-15（早于 B 的 10-20）+ A 有了 11 月：10 月判 tail 且只取 A 的新增、11 月 new
#       → 尾部事件日期早于旧事件也不重排（旧下标不变）→ commit 后无新增
#       → 新接入 C 群（只有 09 月）：09 月判 tail，只取 C 的全部消息 → A 补导 09 月中间漏掉的消息：判 changed。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="${KEEP:-$(mktemp -d)}"; [ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT
PY="python3 -I"
ok(){ echo "  ok  $*"; }
fail(){ echo "  FAIL $*"; exit 1; }
P="$T/proj"; rm -rf "$P"; mkdir -p "$P/exports" "$P/work/stable"
inc(){ $PY "$HERE/incremental.py" --project "$P" "$@"; }

echo "0. 合成导出、冻结 09/10 两个月、写旧版基线"
$PY - "$P" <<'EOF'
import json, sys, hashlib, pathlib
p = pathlib.Path(sys.argv[1])
def txt(days, month='2026-09'):
    return [f'{month}-{d:02d} 20:{i:02d}:00 {w}: {c}' for d in days for i, (w, c) in
            enumerate([('木木', f'{d} 号谁有空'), ('小鹿', '我'), ('大熊', '加一')])]
(p / 'exports/a.txt').write_text('\n'.join(txt([1, 5, 9, 20]) + txt([2, 6, 10], '2026-10')) + '\n', encoding='utf-8')
B, n = [], 5000
for mon, days in (('2026-09', [3, 15]), ('2026-10', [4, 12, 20])):
    for d in days:
        for i, (w, c) in enumerate([('妈妈', '吃了吗'), ('木木', '吃了')]):
            n += 1
            B.append({'time': f'{mon}-{d:02d} 09:0{i}:00', 'msg_id': str(n), 'sender': w, 'sender_id': 'u_' + w,
                      'is_self': w == '木木', 'type': 'text', 'content': c})
(p / 'exports/b.json').write_text(json.dumps(B, ensure_ascii=False), encoding='utf-8')
json.dump({'title': '测试', 'me': '木木', 'members': ['木木', '小鹿', '大熊', '妈妈'],
           'groups': [{'key': 'A', 'label': '周末群', 'file': 'exports/a.txt', 'format': 'txt'},
                      {'key': 'B', 'label': '家属群', 'file': 'exports/b.json', 'format': 'json-array'}]},
          open(p / 'chronicle.config.json', 'w'), ensure_ascii=False)
EOF
$PY "$HERE/ingest.py" --project "$P" >/dev/null
$PY - "$P" <<'EOF'
import json, sys, hashlib, pathlib, collections
p = pathlib.Path(sys.argv[1]); allm = json.load(open(p / 'work/all.json'))
by = collections.defaultdict(list)
for m in allm:
    by[m['t'][:7]].append(m)
for mon, ms in by.items():   # 每月一个事件，日期在月末（A 群 20 号 / B 群 20 号）
    last = [m for m in ms if m['t'][8:10] == '20']
    json.dump({'month': mon, 'month_summary': '旧', 'events': [
        {'date': last[0]['t'][:10], 'title': f'{mon} 旧事件', 'summary': '旧', 'people': [], 'category': '群内热议', 'heat': 1,
         'refs': [m['k'] for m in last], 'groups': []}]}, open(p / f'work/stable/{mon}.json', 'w'), ensure_ascii=False)
# 旧版基线：按月、各群混在一起
fp = lambda ks: hashlib.sha1('\n'.join(ks).encode('utf-8')).hexdigest()[:16]
json.dump({'months': {mon: {'n': len(ms), 'first': ms[0]['t'], 'last': ms[-1]['t'], 'fp': fp([m['k'] for m in ms])}
                      for mon, ms in by.items()}, 'updated': 'x', 'source_last': allm[-1]['t']},
          open(p / 'work/incremental.json', 'w'))
EOF

echo "1. 旧版基线：换算后无新增；commit 存成按群的新版"
OUT="$(inc --skip-ingest --dry-run)"
echo "$OUT" | grep -q '旧版' || fail "没提示旧版基线"
echo "$OUT" | grep -q '没有新增或变化的月份' || { echo "$OUT"; fail "旧版基线换算后不该有新增"; }
inc --commit >/dev/null
$PY - "$P/work/incremental.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1]))
assert d['version'] == 2 and 'months' not in d, d.keys()
g = d['groups']
assert g['A']['label'] == '周末群' and g['A']['last'] == '2026-10-10 20:02:00', g['A']
assert g['B']['label'] == '家属群' and g['B']['last'] == '2026-10-20 09:01:00', g['B']
assert set(g['A']['months']) == set(g['B']['months']) == {'2026-09', '2026-10'}
EOF
ok "新版基线：每群各自记 label / last / months"

echo "2. A 补同步到 10-15（早于 B 的 10-20），并有了 11 月"
$PY - "$P/exports/a.txt" <<'EOF'
import sys
lines = [f'2026-10-{d} 21:0{i}:00 {w}: {c}' for d in (11, 15) for i, (w, c) in enumerate([('小鹿', '周末爬山'), ('大熊', '好')])]
lines += [f'2026-11-0{d} 21:00:00 木木: 十一月第{d}天' for d in (1, 2, 3)]
open(sys.argv[1], 'a', encoding='utf-8').write('\n'.join(lines) + '\n')
EOF
$PY "$HERE/pipeline.py" --project "$P" status >/dev/null 2>&1 || true
OUT="$(inc)"; echo "$OUT"
echo "$OUT" | grep -q '| 2026-10 | tail |' || fail "10 月应判 tail（旧版逻辑会因 B 的 last 更晚误判 changed）"
echo "$OUT" | grep -q '| 2026-11 | new |' || fail "11 月应判 new"
echo "$OUT" | grep -q '| 2026-09 |' && fail "09 月没变，不该出现"
$PY - "$P" <<'EOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
L = (p / 'work/chunks/2026-10_tail_p1.txt').read_text(encoding='utf-8').splitlines()
body = L[3:]
assert len(body) == 4 and all('|周末群|' in l for l in body), body          # 只有 A 的 4 条新增，B 的一条都没有
assert '周末群 2026-10-10 20:02:00 之后' in L[0], L[0]
EOF
ok "10 月只切出 A 在自己 last 之后的 4 条"

echo "3. 尾部事件日期早于旧事件：追加在末尾、不重排"
$PY - "$P" <<'EOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1])
ids = [l.split('|')[0] for l in (p / 'work/chunks/2026-10_tail_p1.txt').read_text(encoding='utf-8').splitlines()[3:]]
(p / 'work/part_events').mkdir(exist_ok=True)
json.dump({'month': '2026-10', 'events': [{'date': '2026-10-11', 'title': '爬山', 'summary': '约爬山。', 'people': [],
           'category': '聚会出行', 'heat': 1, 'refs': ids[:2], 'groups': []}]},
          open(p / 'work/part_events/2026-10_tail_p1.json', 'w'), ensure_ascii=False)
n = [l.split('|')[0] for l in (p / 'work/chunks/2026-11_p1.txt').read_text(encoding='utf-8').splitlines() if '|' in l]
(p / 'work/events').mkdir(exist_ok=True)
json.dump({'month': '2026-11', 'month_summary': '新', 'events': [{'date': '2026-11-01', 'title': '十一月', 'summary': '新',
           'people': [], 'category': '群内热议', 'heat': 1, 'refs': n[:1], 'groups': []}]},
          open(p / 'work/events/2026-11.json', 'w'), ensure_ascii=False)
EOF
inc --merge-tail
$PY "$HERE/freeze.py" --project "$P" >/dev/null
$PY - "$P" <<'EOF'
import json, sys, pathlib
e = json.load(open(pathlib.Path(sys.argv[1]) / 'work/stable/2026-10.json'))['events']
assert [x['title'] for x in e] == ['2026-10 旧事件', '爬山'], [x['title'] for x in e]
assert all(r.startswith('A:') for r in e[1]['refs']), e[1]['refs']
EOF
ok "旧事件仍是 E:2026-10-0，新事件在 E:2026-10-1"
inc --commit >/dev/null
OUT="$(inc --skip-ingest --dry-run)"
echo "$OUT" | grep -q '没有新增或变化的月份' || { echo "$OUT"; fail "commit 后不该有新增"; }
ok "commit 后无新增"

echo "4. 新接入 C 群（只有 09 月）：09 月判 tail，只取 C 的消息"
printf '2026-09-07 08:00:00 老同学: 好久不见\n2026-09-07 08:01:00 木木: 是啊\n' > "$P/exports/c.txt"
$PY - "$P/chronicle.config.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1])); c['groups'].append({'key': 'C', 'label': '同学群', 'file': 'exports/c.txt', 'format': 'txt'})
json.dump(c, open(sys.argv[1], 'w'), ensure_ascii=False)
EOF
OUT="$(inc)"; echo "$OUT"
echo "$OUT" | grep -q '| 2026-09 | tail | 同学群：新接入，本月 2 条 |' || fail "09 月应判 tail、说明新接入"
[ "$(echo "$OUT" | grep -c '^| 20')" = 1 ] || fail "只有 09 月要做"
$PY - "$P" <<'EOF'
import sys, pathlib
L = (pathlib.Path(sys.argv[1]) / 'work/chunks/2026-09_tail_p1.txt').read_text(encoding='utf-8').splitlines()
assert len(L[3:]) == 2 and all('|同学群|' in l for l in L[3:]), L
assert '同学群 本月全部（新接入）' in L[0], L[0]
EOF
ok "09 月只切出 C 的 2 条"
rm -f "$P"/work/chunks/*_tail_*.txt

echo "5. A 补导了 09 月中间漏掉的一条：判 changed"
echo '2026-09-05 20:05:00 补导的人: 之前漏掉的消息' >> "$P/exports/a.txt"
OUT="$(inc --dry-run)"; echo "$OUT"
echo "$OUT" | grep -q '| 2026-09 | changed | 周末群：旧 12 条 → 现 13 条，旧消息也有变化' || fail "旧消息变化应判 changed 并点名周末群"
ok "旧消息变化判 changed"
echo "ALL OK"
