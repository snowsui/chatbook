#!/usr/bin/env bash
# 增量更新 + 核心人物选择的冒烟测试。需要一个已经做完大事记（有 work/stable/）的项目做源，第一个群是 txt 格式
# （init_project 建的项目即可：导出文件在哪都行，相对或绝对路径都认）。
# 用法：bash scripts/test_incremental.sh <源项目目录> [测试目录]
#   源项目只读；测试目录缺省是临时目录（跑完删除），给了就保留结果（会先清空）。
# 流程：复制 config / 各群导出（复制到测试目录的 exports/ 并改写 config 里的路径）/ stable → ingest
#       → 无基线推测（只会把 stable 最晚那个月的尾部报成“（推测）tail”，不会有 new/changed）→ commit 建基线
#       → 往导出末尾追加「旧月末尾几条 + 新的一个月」→ incremental 应判出 tail + new，只切这两个月，任务追加进 state.json
#       → 模拟抽取 → --merge-tail 追加进 stable（旧事件下标不变）→ freeze 新月 → commit → 再跑应“没有新增”
#       → 改动一条旧消息 → 应判为 changed → --stats 月报/年报统计 → select_core。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:?用法：bash scripts/test_incremental.sh <源项目目录> [测试目录]}"
if [ -n "${2:-}" ]; then P="$2"; rm -rf "$P"; mkdir -p "$P"; else P="$(mktemp -d)"; trap 'rm -rf "$P"' EXIT; fi
PY="python3 -I"
run() { echo "+ $(basename "$1") ${*:2}"; $PY "$@"; }

mkdir -p "$P/work" "$P/exports"
cp -R "$SRC/work/stable" "$P/work/"
EXPORT="$($PY - "$SRC" "$P" <<'EOF'
import json, shutil, sys, pathlib
src, p = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2])
cfg = json.loads((src / 'chronicle.config.json').read_text(encoding='utf-8'))
n = 0
def copy(f):
    global n
    q = pathlib.Path(f).expanduser()
    q = q if q.is_absolute() else src / q
    n += 1
    dst = p / 'exports' / f'{n}_{q.name}'
    shutil.copy(q, dst)
    return str(dst.relative_to(p))
for g in cfg['groups']:
    fs = g['file'] if isinstance(g['file'], list) else [g['file']]
    fs = [dict(x, file=copy(x['file'])) if isinstance(x, dict) else copy(x) for x in fs]
    g['file'] = fs if isinstance(g['file'], list) else fs[0]
(p / 'chronicle.config.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
g = cfg['groups'][0]
assert g['format'] == 'txt', '这个测试只支持第一个群是 txt 导出（追加行时按 txt 行格式写）'
last = g['file'][-1] if isinstance(g['file'], list) else g['file']
print(p / (last['file'] if isinstance(last, dict) else last))
EOF
)"

run "$HERE/ingest.py" --project "$P" >/dev/null
echo "== 1. 无基线：按 stable 推测"
OUT="$($PY "$HERE/incremental.py" --project "$P" --skip-ingest --dry-run)"; echo "$OUT"
# 没有基线时只能推测：stable 最晚那个月最后一条 ref 之后的消息都会报成“（推测）tail”（incremental.py 开头的说明），
# 所以这里只要求不出现 new / changed。
echo "$OUT" | grep -qE '\| (new|changed) \|' && { echo "FAIL: 原样导出不该有 new/changed"; exit 1; }
echo "$OUT" | grep -q '没有新增或变化的月份' || echo "$OUT" | grep -q '（推测）' || { echo "FAIL: 没有基线时应只给推测"; exit 1; }

echo "== 2. 建基线"
run "$HERE/incremental.py" --project "$P" --commit

echo "== 3. 往导出末尾追加：最后一个月末尾 + 新的一个月"
read -r LASTMON NEXTMON <<<"$($PY - "$P/work/all.json" <<'EOF'
import json, sys
a = json.load(open(sys.argv[1])); m = a[-1]['t'][:7]; y, mo = int(m[:4]), int(m[5:7])
print(m, '%04d-%02d' % ((y + 1, 1) if mo == 12 else (y, mo + 1)))
EOF
)"
LASTDAY="$($PY -c "import json,sys;print(json.load(open(sys.argv[1]))[-1]['t'][:10])" "$P/work/all.json")"
SPK=($($PY -c "
import json,sys,collections
a=json.load(open(sys.argv[1])); me=json.load(open(sys.argv[2])).get('me')
print(' '.join(me if s=='me' else s for s,_ in collections.Counter(m['s'] for m in a).most_common(3)))" "$P/work/all.json" "$P/chronicle.config.json"))
while [ ${#SPK[@]} -lt 3 ]; do SPK+=("${SPK[0]}"); done   # 两人私聊只有两个发言人
# 旧月末尾的追加消息要晚于原导出的最后一条（否则排进旧消息中间，会被判成 changed）
read -r T1 T2 T3 T4 <<<"$($PY -c "
import json,sys
from datetime import datetime, timedelta
t = datetime.strptime(json.load(open(sys.argv[1]))[-1]['t'], '%Y-%m-%d %H:%M:%S')
end = t.replace(hour=23, minute=59, second=59)
step = max(1, min(60, int((end - t).total_seconds()) // 5))
print(' '.join((t + timedelta(seconds=step * (i + 1))).strftime('%H:%M:%S') for i in range(4)))" "$P/work/all.json")"
{
  echo ""
  echo "$LASTDAY $T1 ${SPK[0]}: 还没睡的举手"
  echo "$LASTDAY $T2 ${SPK[1]}: 举手，在等零点"
  echo "$LASTDAY $T3 ${SPK[2]}: 我也在，倒计时一起"
  echo "$LASTDAY $T4 ${SPK[0]}: 三二一"
  for d in 02 03 05 09 12; do
    echo "$NEXTMON-$d 12:00:00 ${SPK[0]}: 今天谁有空，晚上吃火锅"
    echo "$NEXTMON-$d 12:01:00 ${SPK[1]}: 我我我（回复 ${SPK[0]}: 今天谁有空）"
    echo "$NEXTMON-$d 12:02:30 ${SPK[2]}: 加班，下次一定"
    echo "$NEXTMON-$d 21:30:00 ${SPK[1]}: [图片] 火锅照"
    echo "$NEXTMON-$d 21:31:00 ${SPK[0]}: 哈哈哈哈"
  done
} >> "$EXPORT"
$PY "$HERE/pipeline.py" --project "$P" status >/dev/null     # 项目用 pipeline 编排：有 work/state.json

echo "== 4. incremental：应判出 $LASTMON=tail、$NEXTMON=new"
OUT="$($PY "$HERE/incremental.py" --project "$P")"; echo "$OUT"
echo "$OUT" | grep -q "| $LASTMON | tail |" || { echo "FAIL: $LASTMON 没判成 tail"; exit 1; }
echo "$OUT" | grep -q "| $NEXTMON | new |" || { echo "FAIL: $NEXTMON 没判成 new"; exit 1; }
[ "$(echo "$OUT" | grep -c '^| 20')" = 2 ] || { echo "FAIL: 应只有两个月要做"; exit 1; }
$PY - "$P" "$LASTMON" "$NEXTMON" <<'EOF'
import json, sys, pathlib
p, last, nxt = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
fs = sorted(f.name for f in (p / 'work/chunks').glob('*.txt'))
assert fs == [f'{last}_tail_p1.txt', f'{nxt}_p1.txt'], fs
tail = (p / f'work/chunks/{last}_tail_p1.txt').read_text().splitlines()
assert len(tail) == 3 + 4 and '增量尾部' in tail[0] and 'part_events' in tail[1], tail[:3]
assert '第 1/1 段' not in tail[0]                      # 不能让抽取员把它写进 events/<月>.json
st = json.loads((p / 'work/state.json').read_text())
ids = sorted(st['tasks'])                               # pipeline 的格式：{任务 id: {stage, status, …}}
assert f'extract:{last}_tail_p1' in ids and f'merge-tail:{last}' in ids, ids     # 尾部：incremental 登记
assert f'read:{nxt}_p1' in ids and f'read:{last}_tail_p1' not in ids, ids         # 新月份：pipeline 的 read 阶段
assert st['tasks'][f'extract:{last}_tail_p1']['stage'] == 'incremental'
print('OK: 分段与 state.json 任务正确', fs, ids)
EOF

echo "== 5. 模拟抽取 → merge-tail → freeze 新月"
$PY - "$P" "$LASTMON" "$NEXTMON" <<'EOF'
import json, sys, pathlib
p, last, nxt = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
def ids(name):
    return [l.split('|')[0] for l in (p / 'work/chunks' / name).read_text().splitlines()[3:]]
t = ids(f'{last}_tail_p1.txt')
day = (p / 'work/chunks' / f'{last}_tail_p1.txt').read_text().splitlines()[3].split('|')[2][:2]
(p / 'work/part_events').mkdir(exist_ok=True)
json.dump({'month': last, 'month_summary': '零点倒计时', 'events': [
    {'date': f'{last}-{day}', 'title': '零点倒计时', 'summary': '几个人熬到零点一起倒数。', 'people': [], 'category': '名场面',
     'heat': 1, 'refs': t[:3], 'groups': []}]}, open(p / f'work/part_events/{last}_tail_p1.json', 'w'), ensure_ascii=False)
n = ids(f'{nxt}_p1.txt')
(p / 'work/events').mkdir(exist_ok=True)
json.dump({'month': nxt, 'month_summary': '火锅月', 'events': [
    {'date': f'{nxt}-02', 'title': '火锅局', 'summary': '约火锅。', 'people': [], 'category': '聚会出行', 'heat': 2,
     'refs': n[:3], 'groups': []}]}, open(p / f'work/events/{nxt}.json', 'w'), ensure_ascii=False)
EOF
BEFORE="$($PY -c "import json,sys;d=json.load(open(sys.argv[1]));print(json.dumps(d['events'],ensure_ascii=False))" "$P/work/stable/$LASTMON.json")"
run "$HERE/incremental.py" --project "$P" --merge-tail
run "$HERE/freeze.py" --project "$P"
$PY - "$P" "$LASTMON" "$NEXTMON" "$BEFORE" <<'EOF'
import json, sys, pathlib
p, last, nxt, before = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
d = json.loads((p / f'work/stable/{last}.json').read_text())
assert d['events'][:len(before)] == before, '旧事件下标变了'
assert len(d['events']) == len(before) + 1 and d['events'][-1]['title'] == '零点倒计时'
assert all(r.startswith('A:') for r in d['events'][-1]['refs']), d['events'][-1]['refs']
assert (p / f'work/stable/{nxt}.json').exists()
assert not list((p / 'work/part_events').glob('*_tail_p*.json')), '尾部文件应挪进 merged/'
print('OK: 尾部事件追加在末尾、旧事件不动；新月已冻结')
EOF
$PY "$HERE/pipeline.py" --project "$P" status >/dev/null
$PY - "$P" "$LASTMON" <<'EOF'
import json, sys, pathlib
p, last = pathlib.Path(sys.argv[1]), sys.argv[2]
t = json.loads((p / 'work/state.json').read_text())['tasks']
assert t[f'extract:{last}_tail_p1']['status'] == 'done' and t[f'merge-tail:{last}']['status'] == 'done', t
print('OK: pipeline 自动判定增量任务 done')
EOF

echo "== 6. commit 后再跑：应没有新增"
run "$HERE/incremental.py" --project "$P" --commit
OUT="$($PY "$HERE/incremental.py" --project "$P" --skip-ingest --dry-run)"; echo "$OUT"
echo "$OUT" | grep -q '没有新增或变化的月份' || { echo "FAIL: commit 后不该有新增"; exit 1; }

echo "== 7. 改动一条旧消息：应判为 changed"
cp "$EXPORT" "$EXPORT.bak"
$PY - "$EXPORT" <<'EOF'
import sys, re
p = sys.argv[1]; L = open(p, encoding='utf-8').read().splitlines()
i = next(i for i, l in enumerate(L) if re.match(r'^\d{4}-\d{2}-1\d ', l))      # 第一个月中旬的某一行之前插一条
L.insert(i, L[i][:19] + ' 补导的人: 之前漏掉的消息')
open(p, 'w', encoding='utf-8').write('\n'.join(L) + '\n')
EOF
OUT="$($PY "$HERE/incremental.py" --project "$P" --dry-run)"; echo "$OUT"
echo "$OUT" | grep -q '| changed |' || { echo "FAIL: 旧消息变化没判出 changed"; exit 1; }
mv "$EXPORT.bak" "$EXPORT"; run "$HERE/ingest.py" --project "$P" >/dev/null

echo "== 8. 月报/年报统计、核心人物"
run "$HERE/incremental.py" --project "$P" --stats "$NEXTMON"
run "$HERE/incremental.py" --project "$P" --stats "${LASTMON:0:4}"
grep -q '大事记事件 1 个' "$P/work/digest/$NEXTMON-stats.md" || { echo "FAIL: 月报统计事件数"; exit 1; }
grep -q '## 各月' "$P/work/digest/${LASTMON:0:4}-stats.md" || { echo "FAIL: 年报统计"; exit 1; }
run "$HERE/select_core.py" --project "$P" --min-msgs 5 >/dev/null
grep -q '"members"' "$P/work/core.md" || { echo "FAIL: core.md 没有建议名单"; exit 1; }
for x in "17-monthly $NEXTMON" "17b ${LASTMON:0:4}"; do set -- $x
  $PY "$HERE/fill_prompt.py" --project "$P" --prompt "$1" --months "$2" >/dev/null || { echo "FAIL: fill_prompt $x"; exit 1; }
done
echo "ALL OK（测试目录：${P}）"
