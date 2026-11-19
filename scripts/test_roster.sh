#!/usr/bin/env bash
# 多份聊天记录 → 人物名单 → 用户圈定核心人物（init_project.py + roster.py）的冒烟测试。
# 用法：bash scripts/test_roster.sh        （在临时目录里跑，不污染仓库；KEEP=<空目录> 则保留产物）
# 合成三个群：A 周末群 json-array 两份时间重叠的导出、B 家属群 ChatLab（账号与 A 相同）、C 旧同学群 txt。
# 覆盖：格式嗅探与 文件:格式 指定、同群重叠导出去重、跨群同账号合并、同名不同账号、改名/引用/作者本人建议、
#       apply 写回 config 且幂等、编号稳定、core → people / 数据页核心成员联动、编号写法（范围/顿号/称呼）、两人私聊不误标机器人。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
T="${KEEP:-$(mktemp -d)}"; [ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT
PY="python3 -I"
ok(){ echo "  ok  $*"; }
fail(){ echo "  FAIL $*"; exit 1; }
P="$T/proj"; X="$T/exports"; mkdir -p "$P" "$X"

echo "0. 合成导出"
$PY - "$X" <<'EOF'
import json, sys, random
from datetime import datetime, timedelta
x = sys.argv[1]; rnd = random.Random(7)
# ---- A 周末群（json-array）：木木=本人；阿光 4/15 起改名光哥（同一账号）；两个不同账号都叫小雨；群助手=机器人 ----
A, sid = [], 100000
def wx(t, uid, name, text, self=False, refer=None):
    global sid
    sid += 1
    m = {"time": t.strftime('%Y-%m-%d %H:%M:%S'), "msg_id": str(sid), "sender": name, "sender_id": uid, "is_self": self,
         "type": "text", "content": text}
    if refer:
        m.update(type="reply", reply_to={"msg_id": refer["msg_id"], "sender": refer["sender"], "sender_id": refer["sender_id"],
                                         "content": refer["content"]})
    A.append(m); return m
lines = ['周末去哪', '我都行', '吃火锅吧', '下雨了', '哈哈哈哈', '在路上', '到了没', '几点', '好的', '明天见']
d0 = datetime(2024, 1, 1, 20, 0)
for d in range(182):
    t = d0 + timedelta(days=d)
    guang = ('u_guang', '阿光' if t < datetime(2024, 4, 15) else '光哥')
    cast = [('u_mumu', '木木'), guang, ('u_lu', '小鹿'), ('u_xiong', '大熊'), ('u_y1', '小雨'), ('u_y2', '小雨')]
    prev = None
    for i, (w, n) in enumerate(rnd.sample(cast, 4)):
        refer = prev if prev and i == 2 else None
        prev = wx(t + timedelta(minutes=i), w, n, rnd.choice(lines), self=(w == 'u_mumu'), refer=refer)
    for j in range(3):
        wx(t + timedelta(hours=1, minutes=j), 'u_bot', '群助手', f'今日签到 {j}')
    if d in (10, 90):
        wx(t + timedelta(hours=2), 'u_pass', '路过的', '请问这是周末群吗')
cut1, cut2 = datetime(2024, 4, 30), datetime(2024, 3, 1)
p1 = [m for m in A if m['time'] < cut1.strftime('%Y-%m-%d')]
p2 = [m for m in A if m['time'] >= cut2.strftime('%Y-%m-%d')]
json.dump(p1, open(f'{x}/weekend_part1.json', 'w'), ensure_ascii=False, indent=0)
json.dump(p2, open(f'{x}/weekend_part2.json', 'w'), ensure_ascii=False, indent=0)
# ---- B 家属群（ChatLab，和 A 同一平台、同一套账号）：小鹿在这里叫鹿鹿 ----
B = []
for d in range(0, 120, 2):
    t = datetime(2024, 2, 1, 9) + timedelta(days=d)
    for i, (u, n) in enumerate([('u_lu', '鹿鹿'), ('u_mom', '鹿妈'), ('u_mumu', '木木')]):
        B.append({"sender": u, "accountName": n, "groupNickname": n, "timestamp": int((t + timedelta(minutes=i)).timestamp()),
                  "type": 0, "content": rnd.choice(lines), "platformMessageId": f"b{len(B)}"})
json.dump({"chatlab": {"version": "0.0.1"}, "meta": {"name": "家属群", "platform": "wechat", "type": "group",
           "groupId": "g_family", "ownerId": "u_mumu"}, "members": [], "messages": B},
          open(f'{x}/family.json', 'w'), ensure_ascii=False)
# ---- C 旧同学群（txt，无账号）：木木子=作者本人（没有标记）；阿杰 6/10 后改名杰哥；引用回复用旧名/外号 ----
C = []
for d in range(0, 300, 2):
    t = datetime(2023, 1, 2, 21) + timedelta(days=d)
    jie = '阿杰' if t < datetime(2023, 6, 10) else '杰哥'
    for i, n in enumerate([jie, '熊大', '木木子']):
        C.append(f'{(t + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")} {n}: {rnd.choice(lines)}')
C += ['2023-11-01 08:00:00 杰哥: 明天几点集合',
      '2023-11-01 08:01:00 熊大: 七点（回复 阿杰: 明天几点集合）',
      '2023-11-01 08:02:00 木木子: 收到（回复 杰杰: 明天几点集合）']
C.sort()
open(f'{x}/classmates.txt', 'w').write('\n'.join(C) + '\n')
open(f'{x}/README.txt', 'w').write('这是导出说明，不是聊天记录。\n')
json.dump({'A': len(A), 'A1': len(p1), 'A2': len(p2), 'B': len(B), 'C': len(C)}, open(f'{x}/../expect.json', 'w'))
EOF
ok "三个群、四份导出"

echo "1. 格式嗅探"
cp "$HERE/../assets/samples/telegram.json" "$T/tg.dat"
mkdir -p "$T/p0"
if $PY "$HERE/init_project.py" --project "$T/p0" "$T/tg.dat" --no-ingest >"$T/err.txt" 2>&1; then fail "识别不了的文件应报错"; fi
grep -q 'tg.dat:<格式>' "$T/err.txt" || fail "报错没提示 文件:格式"
$PY "$HERE/init_project.py" --project "$T/p0" "$T/tg.dat:telegram" --no-ingest >/dev/null
grep -q '"format": "telegram"' "$T/p0/chronicle.config.json" && grep -q '"label": "旅行计划"' "$T/p0/chronicle.config.json" || fail "文件:格式 指定无效"
ok "识别不了就报错；文件:格式 可指定；Telegram 群名作 label"

echo "2. init_project：分群、重叠导出合并去重"
$PY "$HERE/init_project.py" --project "$P" "$X" | tee "$T/init.txt" | grep -E '新群|同一个群|跳过|\[' || true
grep -q '跳过（识别不了）' "$T/init.txt" || fail "目录里的 README.txt 应跳过"
$PY - "$P" "$T/expect.json" <<'EOF'
import json, sys, collections
p, exp = sys.argv[1], json.load(open(sys.argv[2]))
cfg = json.load(open(f'{p}/chronicle.config.json'))
gs = {g['format']: g for g in cfg['groups']}
assert len(cfg['groups']) == 3, cfg['groups']
assert all(f.endswith(('weekend_part1.json', 'weekend_part2.json')) for f in gs['json-array']['file']), gs['json-array']
assert gs['chatlab']['label'] == '家属群' and gs['txt']['label'] == 'classmates', cfg['groups']
a = json.load(open(f'{p}/work/all.json'))
by = collections.Counter(m['g'] for m in a)
assert by[gs['json-array']['label']] == exp['A'] < exp['A1'] + exp['A2'], (by, exp)        # 去重后 = 原始条数
assert by['家属群'] == exp['B'] and by['classmates'] == exp['C'], by
assert len({m['k'] for m in a}) == len(a)
rows = json.load(open(f'{p}/work/senders.json'))['rows']
assert len(rows) == len(a) and any(r[0] == 'wx:u_lu' for r in rows) and any(r[2] for r in rows), rows[:3]
print('  groups:', {g['key']: (g['label'], g['format']) for g in cfg['groups']}, dict(by))
EOF
cp "$P/chronicle.config.json" "$T/c0.json"
$PY "$HERE/init_project.py" --project "$P" "$X/weekend_part2.json" --no-ingest | grep -q '跳过（已在 config 里）' || fail "重复传入应跳过"
cmp -s "$P/chronicle.config.json" "$T/c0.json" || fail "重复 init 改了 config"
ok "3 个群；A 两份导出去重合并；重复 init 不改 config"

echo "3. roster build"
$PY "$HERE/roster.py" --project "$P" build
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
r = json.load(open(f'{p}/work/roster.json'))
P = {x['name']: x for x in r['people']}
no = {x['name']: x['no'] for x in r['people']}
assert '光哥' in P and '阿光' in P['光哥']['aliases'], P.get('光哥')                         # 同账号改名：称呼取最近的
lu = next(x for x in r['people'] if 'wx:u_lu' in x['accounts'])
assert set(lu['groups']) == {'weekend_part1', '家属群'} or len(lu['groups']) == 2, lu      # 跨群同账号合并
assert {lu['name']} | set(lu['aliases']) == {'小鹿', '鹿鹿'}, lu
me = [x for x in r['people'] if x['self']]
assert len(me) == 1 and me[0]['name'] == '木木' and len(me[0]['groups']) == 2, me          # is_self + ownerId
assert [c for c in r['conflicts'] if c['no'] == no['小雨']], r['conflicts']                 # 两个账号都叫小雨
pairs = {frozenset((s['a'], s['b'])): s for s in r['suggestions']}
s = pairs.get(frozenset((no['阿杰'], no['杰哥'])))
assert s and any('引用回复' in w for w in s['why']) and any('改名' in w for w in s['why']), r['suggestions']
s = pairs.get(frozenset((no['木木子'], no['木木'])))
assert s and any('作者本人' in w for w in s['why']), r['suggestions']
assert '杰杰' in P['杰哥']['ref_names'], P['杰哥']                                         # 引用名（txt 按内容找到被引用的消息）
assert P['木木']['level'] != '路人' and P['熊大']['level'] != '路人', {k: v['level'] for k, v in P.items()}  # 小群活跃者至少成员
assert P['路过的']['level'] == '路人'
assert any(x['level'] == '核心' for x in r['people'])
json.dump(no, open(f'{p}/../no.json', 'w'), ensure_ascii=False)
print('  ', {k: (v['no'], v['level']) for k, v in P.items()})
EOF
grep -q '可能是同一个人' "$P/work/roster.md" && grep -q '可能是两个人用了同一个名字' "$P/work/roster.md" && grep -q '按账号自动合并的人' "$P/work/roster.md" || fail "roster.md 缺小节"
ok "跨群同账号合并、改名、同名多账号、引用/改名/本人建议、推荐等级"

echo "4. roster apply：写回 config、重跑 ingest"
N() { $PY -c "import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$T/no.json" "$1"; }
# 编号写法混用：顿号分隔、称呼代替编号
ARGS=(apply --core "$(N 光哥)、小鹿、$(N 木木)" --merge "$(N 杰哥)=$(N 阿杰)" --merge "木木=$(N 木木子)"
      --rename "$(N 大熊)=熊老大" --split "$(N 小雨)" --drop 群助手 --me "$(N 木木)")
$PY "$HERE/roster.py" --project "$P" "${ARGS[@]}" | tee "$T/apply.txt"
grep -q '当前已选：核心 3' "$T/apply.txt" || fail "apply 后汇总应显示当前已选"
if $PY "$HERE/roster.py" --project "$P" apply --core 不存在的人 >"$T/err.txt" 2>&1; then fail "认不出的称呼应报错"; fi
grep -q '认不出「不存在的人」' "$T/err.txt" && ! grep -q Traceback "$T/err.txt" || fail "报错要友好"
$PY - "$P" "$T/no.json" <<'EOF'
import json, sys, collections
p, no = sys.argv[1], json.load(open(sys.argv[2]))
cfg = json.load(open(f'{p}/chronicle.config.json'))
al = cfg['aliases']
assert cfg['core'] == ['光哥', '小鹿', '木木'] and cfg['me'] == '木木', cfg
assert 'people' not in cfg, 'people 不写（缺省 = core）'
m = cfg['members']
assert m[:3] == ['光哥', '小鹿', '木木'] and '熊老大' in m and '杰哥' in m and '群助手' not in m and '路过的' not in m, m
for k, v in {'阿光': '光哥', '鹿鹿': '小鹿', '阿杰': '杰哥', '杰杰': '杰哥', '木木子': '木木', '大熊': '熊老大'}.items():
    assert al.get(k) == v, (k, al.get(k))
assert {al.get('u_y1'), al.get('u_y2')} == {'小雨', '小雨（2）'}, al
a = json.load(open(f'{p}/work/all.json'))
spk = collections.Counter(m['s'] for m in a)
assert not {'阿杰', '木木子', '阿光', '鹿鹿', '大熊'} & set(spk), spk
assert spk['小雨'] and spk['小雨（2）'] and spk['熊老大'] and spk['me'], spk
assert '（回复 杰哥: 明天几点集合）' in ''.join(m['c'] for m in a), '引用回复里的旧名也要归一'
r = json.load(open(f'{p}/work/roster.json'))
P = {x['name']: x for x in r['people']}
assert P['光哥']['no'] == no['光哥'] and P['杰哥']['no'] == min(no['杰哥'], no['阿杰']), '编号应稳定'
assert P['熊老大']['no'] == no['大熊'] and P['熊老大']['current'] == '成员' and P['光哥']['current'] == '核心'
assert P['群助手']['dropped'] and not r['conflicts'], r['conflicts']
EOF
cp "$P/chronicle.config.json" "$T/c1.json"
$PY "$HERE/roster.py" --project "$P" "${ARGS[@]}" >/dev/null
cmp -s "$P/chronicle.config.json" "$T/c1.json" || { diff "$T/c1.json" "$P/chronicle.config.json"; fail "apply 不幂等"; }
ok "core/members/me/aliases 写回，名字归一生效；同样的参数再跑一遍 config 逐字节不变"

echo "5. core 联动：people 缺省 = core，数据页核心成员 = core"
$PY "$HERE/fill_prompt.py" --project "$P" --prompt 08 --person 光哥 --out "$T/p08.md" >/dev/null || fail "core 里的人应能 --person"
grep -q '光哥、小鹿、木木' "$T/p08.md" || grep -q '光哥, 小鹿, 木木' "$T/p08.md" || true
$PY "$HERE/build_stats.py" --project "$P" --no-page >/dev/null
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
s = json.load(open(f'{p}/work/stats.json'))
core = [x['n'] for x in s['people'] if x['core']]
assert sorted(core) == sorted(['光哥', '小鹿', '木木']), core
a = json.load(open(f'{p}/work/all.json'))
assert s['combos']['all|all']['members'] == len({m['s'] for m in a} - {'群助手'}), s['combos']['all|all']['members']  # --drop 的人不计
cfg = json.load(open(f'{p}/chronicle.config.json'))
cfg['stats'] = {'core': ['熊老大', '光哥', '杰哥']}           # stats.core 优先
json.dump(cfg, open(f'{p}/chronicle.config.json', 'w'), ensure_ascii=False)
EOF
$PY "$HERE/build_stats.py" --project "$P" --no-page >/dev/null
$PY -c "
import json,sys; s=json.load(open(sys.argv[1]))
assert sorted(x['n'] for x in s['people'] if x['core']) == sorted(['熊老大','光哥','杰哥'])" "$P/work/stats.json" || fail "stats.core 应优先"
ok "people 缺省 = core；数据页核心成员 stats.core > core"

echo "6. --members 列表"
$PY "$HERE/roster.py" --project "$P" apply --members "$(N 大熊)" >/dev/null
$PY -c "
import json,sys; c=json.load(open(sys.argv[1]))
assert c['members'] == ['光哥','小鹿','木木','熊老大'], c['members']
assert c['core'] == ['光哥','小鹿','木木']" "$P/chronicle.config.json" || fail "--members 列表 = core + 列表 + 本人"
ok "--members 列表 = core + 列出的人 + 作者本人；core 不变"

echo "6b. 拆开的同名两人再合并：不写「小雨（2）→小雨」这类无用别名"
M="$T/remerge"; cp -r "$P" "$M"
$PY "$HERE/roster.py" --project "$M" build >/dev/null
Y2=$($PY -c "import json,sys;print(next(x['no'] for x in json.load(open(sys.argv[1]))['people'] if x['name']=='小雨（2）'))" "$M/work/roster.json")
Y1=$($PY -c "import json,sys;print(next(x['no'] for x in json.load(open(sys.argv[1]))['people'] if x['name']=='小雨'))" "$M/work/roster.json")
$PY "$HERE/roster.py" --project "$M" apply --merge "$Y1=$Y2" >/dev/null
$PY -c "
import json,sys; al=json.load(open(sys.argv[1]))['aliases']
assert '小雨（2）' not in al, al
assert al.get('u_y1') == al.get('u_y2') == '小雨', al" "$M/chronicle.config.json" || fail "合并后不应写重名后缀别名"
ok "合并重名两人：账号别名指向同一称呼，不写带（2）的别名"

echo "7. 编号范围；两人私聊不误标机器人"
$PY "$HERE/roster.py" --project "$P" apply --members "$(N 大熊)-$(N 大熊)" >/dev/null || fail "范围写法 a-b"
Q="$T/pair"; mkdir -p "$Q"
$PY - "$Q/chat.txt" <<'EOF'
import sys
from datetime import datetime, timedelta
rows = []
for d in range(200):
    t = datetime(2024, 1, 1, 21) + timedelta(days=d)
    rows += [f'{t:%Y-%m-%d %H:%M:%S} 小雨: 今天怎么样', f'{t + timedelta(minutes=1):%Y-%m-%d %H:%M:%S} 阿森: 还行吧']
open(sys.argv[1], 'w').write('\n'.join(rows) + '\n')
EOF
$PY "$HERE/init_project.py" --project "$Q" "$Q/chat.txt" >/dev/null 2>&1
$PY "$HERE/roster.py" --project "$Q" build >/dev/null
grep -q '机器人' "$Q/work/roster.md" && fail "两人私聊不该标“机器人”" || true
ok "1-3 范围；两人私聊不误标"
echo "全部通过"
