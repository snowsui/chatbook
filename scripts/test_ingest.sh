#!/usr/bin/env bash
# 用 assets/samples/ 的六种格式样例一键跑通 ingest（另测 txt 的补充形态、非 UTF-8、config 校验、init_project 的容错与跨格式合并），
# 并对其余脚本做冒烟测试。
# 用法：bash scripts/test_ingest.sh        （在临时目录里跑，不污染仓库）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SAMPLES="$HERE/../assets/samples"
P="$(mktemp -d)"
trap 'rm -rf "$P"' EXIT
cp "$SAMPLES"/* "$P"/
PY="python3 -I"
run() { echo "+ $*"; $PY "$@"; }

run "$HERE/ingest.py" --project "$P"

$PY - "$P/work/all.json" <<'EOF'
import json, sys, collections
a = json.load(open(sys.argv[1]))
by = collections.Counter(m['g'] for m in a)
want = {'主群': 9, '小分队': 5, '文本群': 6, '表格群': 3, '室友群': 3, '电报群': 4}
assert dict(by) == want, by
assert [m['t'] for m in a] == sorted(m['t'] for m in a), '未按时间排序'
assert all(set(m) == {'id', 'k', 'g', 't', 's', 'c'} for m in a)
assert len({m['k'] for m in a}) == len(a), '稳定键重复'
c = {m['k']: m for m in a}
assert c['A:1003']['c'] == '八点吧（回复 青禾: 周六去爬香山吗）'      # json-array 引用回复 + 旧昵称归一
assert c['A:1003']['s'] == '老周'                                    # aliases
assert c['A:1002']['s'] == 'me' and ' ⏎ ' in c['A:1002']['c']        # is_self
assert c['A:1007']['c'] == '[文章] 香山春季游览攻略' and c['A:1005']['c'] == '[图片]' and c['A:1009']['c'] == '[语音]'
assert c['A:1010']['c'] == '[其他] app-card 某个应用卡片'
assert not any('撤回' in m['c'] for m in a)                                         # 系统消息丢弃
assert c['C:m2']['s'] == 'me' and '（回复 米粒:' in c['C:m2']['c']                   # chatlab ownerId + reply
assert c['C:m5']['c'] == '[链接] 海边民宿推荐'
assert any(m['g'] == '文本群' and m['s'] == '青禾' and m['c'] == '我在加班…… ⏎ 这是第二行' for m in a)  # 微信 PC 复制格式
assert any(m['g'] == '文本群' and m['s'] == 'me' and '续行' in m['c'] for m in a)                    # 续行
assert c['V:c2']['c'] == '早，今天 ⏎ 好困' and c['V:c3']['t'] == '2021-06-01 08:05:00'               # csv 自定义列
assert [m['s'] for m in a if m['g'] == '室友群'] == ['老周', 'me', '豆豆']                           # qq 号别名 + 系统消息
assert c['G:3']['s'] == 'me' and '（回复 米粒: 下个月去成都？）' in c['G:3']['c']                  # telegram list text + reply
assert c['G:5']['c'] == '[表情]'
txt = [m for m in a if m['g'] == '文本群']
assert txt[4]['c'] == '起来嗨（回复 老周: 五一都在家躺着？）', txt[4]                       # txt 引用回复里的旧昵称过 aliases
assert txt[5]['c'] == '[图片] 我家猫在睡觉（回复 阿然: 哈哈哈哈）', txt[5]               # 账号别名 → 作者本人显示名
assert not any('（回复 me:' in m['c'] for m in a)
print('ingest 断言全部通过：', dict(by))
EOF

run "$HERE/split_chunks.py" --project "$P" --max-chars 200
ls "$P/work/chunks" | head -3

mkdir -p "$P/work/events"
cat > "$P/work/events/2019-03.json" <<'EOF'
{"month": "2019-03", "month_summary": "相约爬香山", "events": [
 {"date": "2019-03-02", "title": "约爬香山", "summary": "青禾提议周六爬香山，大家定了八点集合。", "people": ["青禾", "阿然"],
  "category": "聚会出行", "heat": 2, "refs": ["A0", "A2", "X999"], "groups": ["主群"]}]}
EOF
run "$HERE/check_events.py" --project "$P" | tee "$P/check.txt"
grep -q 'refs 在 all.json 里找不到：X999' "$P/check.txt"
if $PY "$HERE/check_events.py" --project "$P" --strict >/dev/null; then echo '--strict 应失败'; exit 1; fi
run "$HERE/freeze.py" "$P"                     # 位置参数写法也兼容
grep -q '"A:1001"' "$P/work/stable/2019-03.json"
cat > "$P/fix.json" <<'EOF'
[{"key": "E:2019-03-0", "field": "summary", "old": "八点集合", "new": "早上八点集合", "why": "原文"},
 {"key": "M:2019-03", "field": "summary", "old": "相约", "new": "周末相约"},
 {"key": "E:2019-03-0", "field": "people", "add": "老周"}]
EOF
printf '<script>\nconst DATA={"months":[{"month":"2019-03","summary":"相约爬香山","events":[{"title":"约爬香山","summary":"青禾提议周六爬香山，大家定了八点集合。","people":["青禾"]}]}]};\nconst CATS={};\n</script>\n' > "$P/page.html"
run "$HERE/apply_fixes.py" --project "$P" "$P/fix.json" --html page.html
grep -q '早上八点集合' "$P/work/stable/2019-03.json" && grep -q '周末相约爬香山' "$P/page.html" && grep -q '老周' "$P/page.html"
echo '[{"key": "E:2019-03-0", "field": "title", "old": "约爬", "new": "相约爬"}, {"key": "E:2019-03-0", "field": "summary", "old": "不存在的字", "new": "x"}]' > "$P/bad.json"
if $PY "$HERE/apply_fixes.py" --project "$P" "$P/bad.json" 2>/dev/null; then echo '应整批拒绝'; exit 1; fi
grep -q '"title": "约爬香山"' "$P/work/stable/2019-03.json"   # 整批不写

run "$HERE/person_chunks.py" --project "$P"
grep -q '我家猫在睡觉' "$P/work/people/老周/chunks/01.txt"          # 带配文的图片算文字
run "$HERE/person_stats.py" --project "$P"
grep -q '最常引用回复 TA 的人：豆豆(1)' "$P/work/stats/老周.md"
grep -q '最常引用回复 TA 的人：.*老周(1)' "$P/work/stats/阿然.md"
run "$HERE/metrics.py" --project "$P"
grep -q '| 指标 | 阿然 | 青禾 | 老周 | 豆豆 | 米粒 | 全群 |' "$P/work/metrics.md"   # 列 = members，不是 people
run "$HERE/turnmix.py" --project "$P"
run "$HERE/baseline_sample.py" --project "$P" --n 3
run "$HERE/holdout.py" --project "$P" --n 3
printf '她常说「周六去爬香山吗」，也爱说“去！几点集合”，还有"根本没说过这句话"。\n' > "$P/persona.md"
run "$HERE/quote_attr.py" --project "$P" --person 阿然 --md "$P/persona.md"
grep -q '青禾' "$P/work/attr/阿然.md" && grep -q '根本没说过这句话' "$P/work/attr/阿然.md"
grep -q '引语语境' "$P/work/attr/阿然.md"

# 子任务说明填空
run "$HERE/fill_prompt.py" --project "$P" --prompt 01 --files 2019-03_p1.txt --out "$P/p01.md"
grep -q '主群（key A）' "$P/p01.md"
no() { if grep -q -- "$1" "$2"; then echo "不应出现 $1 于 $2"; exit 1; fi; }
no '{{' "$P/p01.md"
run "$HERE/fill_prompt.py" --project "$P" --prompt 08 --person 老周 --out "$P/p08.md"
grep -q -- '- 老周：男' "$P/p08.md"
no '{{' "$P/p08.md"
if $PY "$HERE/fill_prompt.py" --project "$P" --prompt 08 >/dev/null 2>&1; then echo '缺 --person 应失败'; exit 1; fi

# 页面构建：栏目只列已生成的页面；一篇小传时 hero 不说“每个人”
run "$HERE/build_chronicle.py" --project "$P"
no 'href="stories.html"' "$P/out/chronicle.html"
mkdir -p "$P/out/portraits"
printf '# 老周\n> 一句品藻\n\n正文。\n\n## 史官曰\n好。\n' > "$P/out/portraits/老周.md"
run "$HERE/build_portraits.py" "$P"
grep -q '替<b>TA 写了一篇小传' "$P/out/people.html"
grep -q 'href="chronicle.html"' "$P/out/people.html"
no 'href="stories.html"' "$P/out/people.html"
# ---- txt 补充形态 + 早期导出写法兼容 ----
P2="$P/more"; mkdir -p "$P2"
cat > "$P2/head.txt" <<'TXT'
青禾 2024/1/1 12:00
新年快乐
老周 2024-01-01 12:00:30
同乐
第二行
TXT
cat > "$P2/notime.txt" <<'TXT'
2024年1月2日
青禾：今天去哪
老周: 看电影
链接如下
https://example.com/a
2024-01-03
豆豆：好
TXT
printf '米粒：在吗\n阿然：在\n' > "$P2/nodate.txt"
# 早期导出的字段名（数字类型码 + 类型名、引用在 detail 里），静默兼容
$PY - "$P2/old.json" <<'EOF'
import json, sys
uid, mid, tn = 'sender_id', 'server_id', 'type_name'
rows = [{'time': '2019-03-02 20:01:05', mid: 11, 'sender': '青禾', uid: 'u1', 'type': 1, tn: '文本', 'content': '周六去爬山吗'},
        {'time': '2019-03-02 20:02:10', mid: 12, 'sender': '周周', uid: 'u2', 'type': 9, tn: '引用回复', 'content': 'x',
         'detail': {'text': '八点吧', 'refer': {'svrid': 11, 'sender': '青禾宝宝', uid: 'u1', 'summary': '周六去爬山吗'}}},
        {'time': '2019-03-02 20:03:00', mid: 13, 'sender': '豆豆', uid: 'u3', 'type': 3, tn: '图片', 'content': '[图片]'},
        {'time': '2019-03-02 20:04:00', mid: 14, 'sender': '系统', 'type': 5, tn: '系统提示', 'content': '撤回了一条消息'}]
json.dump(rows, open(sys.argv[1], 'w'), ensure_ascii=False)
EOF
cat > "$P2/chronicle.config.json" <<JSON
{"title": "t", "me": "阿然", "groups": [
 {"key": "H", "label": "带时间头", "file": "head.txt", "format": "txt"},
 {"key": "N", "label": "无时间", "file": "notime.txt", "format": "txt"},
 {"key": "D", "label": "配日期", "file": "nodate.txt", "format": "txt", "date": "2024-02-01"},
 {"key": "W", "label": "旧写法", "file": "old.json", "format": "json-array"}]}
JSON
$PY "$HERE/ingest.py" --project "$P2" | tee "$P2/out.txt"
no '改名' "$P2/out.txt"
$PY - "$P2/work/all.json" "$P2/work/ingest.json" <<'EOF2'
import json, sys
a = json.load(open(sys.argv[1]))
g = lambda lab: [(m['t'], m['s'], m['c']) for m in a if m['g'] == lab]
assert g('带时间头') == [('2024-01-01 12:00:00', '青禾', '新年快乐'), ('2024-01-01 12:00:30', '老周', '同乐 ⏎ 第二行')], g('带时间头')
assert g('无时间') == [('2024-01-02 00:00:00', '青禾', '今天去哪'),
                      ('2024-01-02 00:00:01', '老周', '看电影 ⏎ 链接如下 ⏎ https://example.com/a'),
                      ('2024-01-03 00:00:00', '豆豆', '好')], g('无时间')
assert g('配日期') == [('2024-02-01 00:00:00', '米粒', '在吗'), ('2024-02-01 00:00:01', 'me', '在')], g('配日期')
assert [x[2] for x in g('旧写法')] == ['周六去爬山吗', '八点吧（回复 青禾: 周六去爬山吗）', '[图片]'], g('旧写法')
assert json.load(open(sys.argv[2]))['no_time'] == ['无时间', '配日期']          # 无时间的群标出来，数据页不算作息
print('txt 补充形态 / 早期写法 断言通过')
EOF2

# ---- 非 UTF-8：GB18030、UTF-16 自动认出并提示 ----
P5="$P/enc"; mkdir -p "$P5"
printf '2024-03-01 10:00:00 张三: 你好\n2024-03-01 10:01:00 李四: 在的\n' | iconv -f UTF-8 -t GB18030 > "$P5/gbk.txt"
printf '2024-04-01 10:00:00 王五: 早\n2024-04-01 10:01:00 赵六: 早啊\n' | iconv -f UTF-8 -t UTF-16 > "$P5/u16.txt"
$PY "$HERE/init_project.py" --project "$P5" "$P5" > "$P5/out.txt" 2>&1
grep -q 'GB18030' "$P5/out.txt" && grep -q 'UTF-16' "$P5/out.txt"
$PY -c "import json;a=json.load(open('$P5/work/all.json'));assert {m['s'] for m in a}=={'张三','李四','王五','赵六'},a"

# ---- init_project 容错：坏文件不拖累好文件，修复办法照做就能导入 ----
P3="$P/mixed"; mkdir -p "$P3/in"
cp "$P2/nodate.txt" "$P2/head.txt" "$P3/in/"
: > "$P3/in/empty.txt"
printf '时间,发送者,内容\n' > "$P3/in/header_only.csv"
$PY "$HERE/init_project.py" --project "$P3" "$P3/in" > "$P3/out.txt" 2>&1 || { cat "$P3/out.txt"; echo '有好文件时不应整体失败'; exit 1; }
grep -q '新群 \[A\] head' "$P3/out.txt"
grep -q '有 3 个文件没导入' "$P3/out.txt"
grep -q 'empty.txt：文件是空的' "$P3/out.txt" && grep -q 'header_only.csv：只有表头' "$P3/out.txt"
grep -q 'nodate.txt：这份 txt 没有时间也没有日期行' "$P3/out.txt"
grep -q 'nodate.txt:txt@2024-02-10' "$P3/out.txt"
grep -q '名字取自文件名' "$P3/out.txt"
$PY "$HERE/init_project.py" --project "$P3" "$P3/in/nodate.txt:txt@2024-02-10" > "$P3/out2.txt" 2>&1
grep -q '"date": "2024-02-10"' "$P3/chronicle.config.json"
grep -q '2024-02-10 00:00:00' "$P3/work/all.json"
# 去掉整个群
$PY "$HERE/init_project.py" --project "$P3" --drop-group B > "$P3/out3.txt" 2>&1
$PY -c "import json;c=json.load(open('$P3/chronicle.config.json'));assert [g['key'] for g in c['groups']]==['A'],c"
no '2024-02-10 00:00:00' "$P3/work/all.json"
# 只有坏文件：失败退出，但照样列出办法
P6="$P/onlybad"; mkdir -p "$P6"; cp "$P2/nodate.txt" "$P6/"
if $PY "$HERE/init_project.py" --project "$P6" "$P6/nodate.txt" > "$P6/out.txt" 2>&1; then echo '只有坏文件应失败'; exit 1; fi
grep -q '在文件开头加一行这份记录的日期' "$P6/out.txt"
# init_project 嗅探：无时间形态认成 txt，日期行在文件里就能直接读
P4="$P/sniff"; mkdir -p "$P4"; cp "$P2/notime.txt" "$P2/head.txt" "$P4/"
$PY "$HERE/init_project.py" --project "$P4" "$P4" >/dev/null
grep -c '"format": "txt"' "$P4/chronicle.config.json" | grep -q '^2$'

# ---- 跨格式：同一个群一份 json-array、一份手动 txt → 提示疑似同一个群，--same 合并去重 ----
P7="$P/cross"; mkdir -p "$P7"
$PY - "$P7" <<'EOF'
import json, sys
d = sys.argv[1]
rows = [('2024-05-0%d 2%d:%02d:00' % (1 + i // 20, i % 4, i % 60), ['阿光', '小鹿', '大熊'][i % 3], f'第{i}句话聊点什么') for i in range(60)]
json.dump([{'time': t, 'sender': s, 'sender_id': 'u' + s, 'msg_id': str(i), 'type': 'text', 'content': c}
           for i, (t, s, c) in enumerate(rows)], open(f'{d}/new.json', 'w'), ensure_ascii=False)
open(f'{d}/old.txt', 'w').write(''.join(f'{t[:16]} {s}: {c}\n' for t, s, c in rows[:40]))
EOF
$PY "$HERE/init_project.py" --project "$P7" "$P7/new.json" "$P7/old.txt" > "$P7/out.txt" 2>&1
grep -q '疑似同一个群' "$P7/out.txt"
CMD=$(grep -o -- '--same [A-Z]*=[A-Z]*' "$P7/out.txt")
[ "$CMD" = '--same B=A' ] || { echo "应建议把 txt 并进 json：$CMD"; exit 1; }
$PY "$HERE/init_project.py" --project "$P7" $CMD > "$P7/out2.txt" 2>&1
grep -q '去重 40 条' "$P7/out2.txt"
$PY -c "import json;a=json.load(open('$P7/work/all.json'));assert len(a)==60,len(a)"

# ---- config 校验：拼错的键给建议、类型不对直接报错、JSON 写错报行列号 ----
P8="$P/cfg"; mkdir -p "$P8"; cp "$P2/head.txt" "$P8/"
cfg() { printf '%s' "$1" > "$P8/chronicle.config.json"; $PY "$HERE/ingest.py" --project "$P8" > "$P8/out.txt" 2>&1; }
G8='"groups": [{"key": "A", "label": "群", "file": "head.txt", "format": "txt"}]'
cfg "{$G8, \"sensitive_word\": [\"x\"]}"
grep -q '不认识的键 "sensitive_word"，是不是 "sensitive_words"' "$P8/out.txt"
if cfg "{$G8, \"sensitive_words\": \"工资\"}"; then echo 'sensitive_words 写成字符串应报错'; exit 1; fi
grep -q '"sensitive_words" 应该是列表' "$P8/out.txt"
if cfg "{$G8, \"members\": [\"a\",]}"; then echo '非法 JSON 应报错'; exit 1; fi
grep -q '第 1 行第' "$P8/out.txt" && no 'Traceback' "$P8/out.txt"
if cfg "{$G8, \"tier\": \"max\"}"; then echo 'tier 取值不对应报错'; exit 1; fi
if cfg "{$G8, \"privacy\": {\"strict\": \"false\"}}"; then echo 'privacy.strict 写成字符串应报错'; exit 1; fi
grep -q '"privacy.strict" 应该是 true/false' "$P8/out.txt" || { cat "$P8/out.txt"; echo 'privacy.strict 报错文案不对'; exit 1; }
no 'Traceback' "$P8/out.txt"
cfg "{$G8, \"privacy\": {\"strict\": false}}" || { cat "$P8/out.txt"; echo 'privacy.strict=false 应能通过'; exit 1; }
echo "全部通过"
