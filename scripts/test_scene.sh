#!/usr/bin/env bash
# scene_sampler.py 的无 LLM 部分冒烟测试：节拍表 / --real / --pack / --tally。
# 用法：bash scripts/test_scene.sh        （在临时目录里造一个虚构小群跑，不污染仓库）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
P="$(mktemp -d)"
trap 'rm -rf "$P"' EXIT
PY="python3 -I"
run() { echo "+ $*"; $PY "$@"; }

mkdir -p "$P/work"
$PY - "$P" <<'EOF'
import json, random, sys, datetime as dt
p = sys.argv[1]
json.dump({"title": "测试群", "me": "甲", "groups": [{"key": "A", "label": "测试群", "file": "x.txt", "format": "txt"}],
           "members": ["甲", "乙", "丙", "丁"], "people": ["乙"]}, open(f'{p}/chronicle.config.json', 'w'), ensure_ascii=False)
rnd = random.Random(1)
lines = ['哈哈哈', '[表情]', '我今天加班到九点', '你们周末去哪', '乙你怎么看', '[图片]', '[链接] 一篇文章',
         '这个电影真的很好看推荐大家都去看一下', '好的', '确实', '我想吃火锅了', '明天下雨吗']
t, out = dt.datetime(2022, 1, 1, 9), []
for i in range(1200):
    t += dt.timedelta(minutes=rnd.choice([1, 1, 2, 3, 5, 30, 200, 600]))
    s = rnd.choice(['me', '乙', '丙', '丁', '乙', 'me'])
    out.append({'id': f'A{i}', 'k': f'A:{i}', 'g': '测试群', 't': t.strftime('%Y-%m-%d %H:%M:%S'), 's': s,
                'c': rnd.choice(lines) + ('（2022-03-05 那次）' if i == 5 else '')})
json.dump(out, open(f'{p}/work/all.json', 'w'), ensure_ascii=False)
EOF
run "$HERE/turnmix.py" --project "$P" >/dev/null

# 1. 节拍表：可复现、人数/turn 数/类型/相邻发言人
run "$HERE/scene_sampler.py" --project "$P" --people 甲,乙,丙 --turns 30 --seed 4 --situation 周末去哪玩
cp "$P/work/scenes/beats-s4.json" "$P/b1.json"
run "$HERE/scene_sampler.py" --project "$P" --people 甲,乙,丙 --turns 30 --seed 4 --situation 周末去哪玩 >/dev/null
cmp -s "$P/b1.json" "$P/work/scenes/beats-s4.json" || { echo '同一 seed 结果不同'; exit 1; }
$PY - "$P/work/scenes/beats-s4.json" "$P/work/scenes/beats-s4.md" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1])); md = open(sys.argv[2]).read()
CATS = {'只发图/语音', '纯反应', '转链接', '跳线', '点名他人', '追问', '讲自己', '短评', '其他'}
b = r['beats']
assert len(b) == 30 and [x['n'] for x in b] == list(range(1, 31))
assert {x['speaker'] for x in b} <= {'甲', '乙', '丙'}
assert all(x['type'] in CATS for x in b)
assert all(b[i]['speaker'] != b[i + 1]['speaker'] for i in range(29)), '相邻 turn 同一人'
assert all(x['msgs'] >= 1 for x in b)
assert b[0]['opener'] and r['lines'][0]['topic'] == '周末去哪玩'
assert all(x['type'] not in ('纯反应', '跳线') for x in b if x['opener']), '开头不应是纯反应/跳线'
assert not b[-1]['cold_after']
for x in b:  # 冷场后下一 turn 必是开头且开新线
    if x['cold_after']:
        nx = b[x['n']]
        assert nx['opener'] and nx['reply_to'] == '—'
assert sorted(t for ln in r['lines'] for t in ln['turns']) == list(range(1, 31)), '每个 turn 恰属一条线'
assert r['sources'] == {'甲': 'work/turns', '乙': 'work/turns', '丙': 'work/turns'}
assert '| # | 时刻 | 发言人 | 类型 | 条数 | 线 | 接谁 | 备注 |' in md and md.count('\n| ') >= 30
print('节拍表断言通过：', len(r['lines']), '条线')
EOF

# 2. 人物模型 0.6 节覆盖分布 + 私人频道
mkdir -p "$P/out/personas"
cat > "$P/out/personas/乙.md" <<'EOF'
# 乙 · 人物模型
## 0.6 发言类型分布（创作抽样用）
| 人 | 次数 | 单条占比 | 只发图/语音 | 纯反应 | 转链接 | 跳线 | 讲自己 | 追问 | 点名他人 | 短评/其他 |
|---|---|---|---|---|---|---|---|---|---|---|
| 乙 | 300 | 50% | 0% | 10% | 0% | 60% | 10% | 10% | 0% | 10% |
| 全体 | 1000 | 60% | 2% | 12% | 2% | 5% | 15% | 11% | 3% | 50% |

- **私人频道**：基金、猫、羽毛球
## 1. 人格画像
EOF
run "$HERE/scene_sampler.py" --project "$P" --people 甲,乙 --turns 40 --seed 2 --tag p >/dev/null
$PY - "$P/work/scenes/beats-p.json" <<'EOF'
import json, sys
r = json.load(open(sys.argv[1]))
assert r['sources']['乙'] == '人物模型 0.6', r['sources']
pr = r['profiles']['乙']
assert pr['single'] == 0.5 and pr['dist']['跳线'] == 60 and pr['topics'] == ['基金', '猫', '羽毛球'], pr
jumps = [x for x in r['beats'] if x['speaker'] == '乙' and x['type'] == '跳线']
assert jumps, '乙 跳线 60% 却一次没抽到'
tp = {ln['id']: ln['topic'] for ln in r['lines']}
assert all(tp[x['line']].startswith('私人频道：') for x in jumps)
print('人物模型覆盖断言通过：乙 跳线', len(jumps), '次')
EOF

# 3. --real：互不重叠、发言人都在名单里、日期替换
run "$HERE/scene_sampler.py" --project "$P" --real --people 甲,乙,丙,丁 --turns 20 --seed 3 --count 2 --tag r
$PY - "$P/work/scenes" <<'EOF'
import json, re, sys
d = sys.argv[1]
meta = json.load(open(f'{d}/real-r.json'))
assert len(meta) == 2 and all(m['turns'] == 20 for m in meta)
assert not set(meta[0]['keys']) & set(meta[1]['keys']), '片段重叠'
for m in meta:
    t = open(f'{d}/{m["file"]}').read()
    assert t.startswith('—— 第 1 天 ——') and not re.search(r'20\d\d', t), '年份没换掉'
    names = re.findall(r'^\*\*\d\d:\d\d (\S+?)\*\*：', t, re.M)
    assert names and set(names) <= {'甲', '乙', '丙', '丁'} and 'me' not in names
print('真实片段断言通过')
EOF

# 4. --pack + --tally
cat > "$P/gen.md" <<'EOF'
**09:00 甲**：早
**09:01 乙**：早啊
—— 第 2 天 ——
**10:00 丙**：哈哈哈
EOF
for i in 1 2 3 4; do run "$HERE/scene_sampler.py" --project "$P" --pack "$P/gen.md" "$P/work/scenes/real-r-1.md" --id t$i --seed $i >/dev/null; done
$PY - "$P/work/scenes/blind" <<'EOF'
import json, sys
d = sys.argv[1]
q = open(f'{d}/t1-q.md').read()
assert '## 片段 A' in q and '## 片段 B' in q and 'gen.md' not in q and 'real-r' not in q, '题目泄露来源'
assert q.count('—— 第 1 天 ——') == 2
reals = []
for i in (1, 2, 3, 4):
    k = json.load(open(f'{d}/t{i}-key.json')); reals.append(k['real'])
    gen = 'B' if k['real'] == 'A' else 'A'
    guess = k['real'] if i <= 3 else gen           # 前三组识破、第四组没识破
    sc = {k['real']: '5', gen: '2'}
    open(f'{d}/t{i}-r.md', 'w').write(f"# 评审\n**真实片段：{guess}**\n**把握：4**\n\n## 逐人像不像（1–5）\n| 人 | A | B | 理由 |\n|---|---|---|---|\n| **甲** | {sc['A']} | {sc['B']} | x |\n| 丁 | - | 3 | 只在一段 |\n\n## 破绽\n")
print('A/B 分布：', reals)
EOF
run "$HERE/scene_sampler.py" --project "$P" --tally | tee "$P/tally.txt"
grep -q '被识破率：3/4 = 75%' "$P/tally.txt"
grep -q '| 甲 | 2.0 | 5.0 | -3.0 |' "$P/tally.txt"
test -f "$P/work/scenes/blind/summary.md"
echo 'test_scene 全部通过'
