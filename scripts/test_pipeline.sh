#!/usr/bin/env bash
# 统一阅读 / 引语出处标注 / 流程编排 / 成本估算 的冒烟测试（不调 LLM：子任务产物用固定样例文件代替）。
# 用法：bash scripts/test_pipeline.sh        （在临时目录里跑，不污染仓库）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SAMPLES="$HERE/../assets/samples"
P="$(mktemp -d)"
[ -n "${KEEP:-}" ] || trap "rm -rf \"$P\"" EXIT
cp "$SAMPLES"/* "$P"/
PY="python3 -I"
run() { echo "+ $*"; $PY "$@"; }
no() { if grep -q -- "$1" "$2"; then echo "不应出现 $1 于 $2"; exit 1; fi; }

run "$HERE/ingest.py" --project "$P" >/dev/null
run "$HERE/split_chunks.py" --project "$P" >/dev/null

# ---- pipeline：ingest/split 已做，read 6 个分段待派 ----
run "$HERE/pipeline.py" --project "$P" status | tee "$P/st.txt"
grep -q '| read | 子任务 | cheap | split | 6 | 0 | 0 | 0 | todo |' "$P/st.txt"
grep -q '| personas' "$P/st.txt" && { echo 'standard 档不应有 personas'; exit 1; }
run "$HERE/pipeline.py" --project "$P" next --limit 2 | tee "$P/next.txt"
[ "$(grep -c '^## read:' "$P/next.txt")" = 2 ]                   # 并发上限 2
grep -q '^## person-stats  \[脚本' "$P/next.txt"                  # 脚本阶段不占名额
grep -q '子任务 · 便宜模型（Claude Code 子任务选 sonnet 或 haiku）' "$P/next.txt"
grep -q -- "--prompt 00 --files 2015-09_p1.txt --set 'people=阿然、老周'" "$P/next.txt"
run "$HERE/pipeline.py" --project "$P" next --limit 2 | tee "$P/next2.txt"
grep -q '没有可派' "$P/next2.txt" || grep -q '^## person-stats' "$P/next2.txt"   # 两个 read 在 doing，名额已满
no '^## read:' "$P/next2.txt"
# next 给出的 fill_prompt 命令能直接跑通（没有漏填的占位）
eval "$(grep -m1 'fill_prompt.py' "$P/next.txt" | sed 's/^ *//; s/^python3 /python3 -I /')"
no '{{' "$P/work/prompts/read-2015-09_p1.md"
grep -q '只为这几位记：阿然、老周' "$P/work/prompts/read-2015-09_p1.md"

# ---- 统一阅读产物（固定样例，代替子任务）----
mkdir -p "$P/work/cards"
cat > "$P/work/cards/2019-03_p1.json" <<'EOF'
{"chunk": "2019-03_p1", "lines": 10, "read_to": 10, "month": "2019-03", "month_summary": "相约爬香山",
 "events": [{"date": "2019-03-02", "title": "约爬香山", "summary": "青禾提议周六爬香山，阿然秒答应，老周定了八点。",
   "people": ["青禾", "阿然", "老周"], "category": "聚会出行", "heat": 2, "refs": ["A0", "A1", "A2"], "groups": ["主群"]}],
 "people": {
  "阿然": {"glance": "一喊就到", "items": [
   {"kind": "名场面", "id": "A1", "who": "阿然", "quote": "去！几点集合", "tone": "真心", "note": "秒答应"},
   {"kind": "名场面", "id": "A2", "who": "阿然", "quote": "八点吧", "tone": "真心", "note": "（故意错：这是老周说的）"},
   {"kind": "日常", "id": "A99", "who": "阿然", "quote": "不存在", "tone": "真心", "note": "（故意错：ID 不存在）"}]},
  "老周": {"glance": "定时间的人", "items": [
   {"kind": "日常", "id": "A2", "who": "老周", "quote": "八点吧", "tone": "真心", "note": "拍板时间"},
   {"kind": "日常", "id": "A2", "who": "老周", "quote": "周六去爬香山吗", "tone": "真心", "note": "（故意错：引用回复里的话不是他说的）"},
   {"kind": "他评", "id": "A0", "who": "青禾", "quote": "周六去爬香山吗", "tone": "真心", "note": "他评：说话人是别人，合法"},
   {"kind": "禁区", "id": "A2", "topic": "健康"}]}}}
EOF
echo '{"chunk": "2020-05_p1", "lines": 9, "read_to": 5, "events": [], "people": {}}' > "$P/work/cards/2020-05_p1.json"
run "$HERE/pipeline.py" --project "$P" status | tee "$P/st2.txt"
grep -q 'read:2020-05_p1.*没读完（读到 5/9 行）' "$P/st2.txt"        # 自动判定：没读完 → failed
grep -q '| read | 子任务 | cheap | split | 3 | 1 | 1 | 1 | failed |' "$P/st2.txt"
# 补派剩余行：next 给出 --from-line，产出写 -b 卡片、不覆盖原卡片
run "$HERE/pipeline.py" --project "$P" next --peek --limit 8 > "$P/next3.txt"
grep -q -- '--files 2020-05_p1.txt --from-line 6' "$P/next3.txt"
eval "$(grep -m1 'from-line 6' "$P/next3.txt" | sed 's/^ *//; s/^python3 /python3 -I /')"
grep -q '这次只读第 6 行到最后一行' "$P/work/prompts/read-2020-05_p1.md" && grep -q 'work/cards/2020-05_p1-b.json' "$P/work/prompts/read-2020-05_p1.md"
echo '{"chunk": "2020-05_p1", "from": 6, "lines": 9, "read_to": 9, "events": [], "people": {}}' > "$P/work/cards/2020-05_p1-b.json"
run "$HERE/pipeline.py" --project "$P" status | grep -q '| read | 子任务 | cheap | split | 3 | 1 | 2 | 0 |'   # 接上就算读完
mv "$P/work/cards/2020-05_p1-b.json" "$P/b.json"   # 下面的断言按“没读完”写

run "$HERE/collect_evidence.py" --project "$P"
E="$P/work/people/阿然/evidence.md"
grep -q '名场面｜k=A:1002｜阿然：「去！几点集合」' "$E"
grep -q '原文是 老周 说的' "$E"                                     # 说话人认错被抓
grep -q 'id A99 不在 all.json' "$E"
grep -q 'quote 是被引用的旧消息里的话' "$P/work/people/老周/evidence.md"    # 引用回复里的旧话不算本人原话，且说清原因
grep -q '健康｜k=A:1003' "$P/work/people/老周/evidence.md"
grep -q '^- 2020-05_p1（读到 5/9 行）' "$P/work/review/evidence-check.md"
grep -q '"title": "约爬香山"' "$P/work/events/2019-03.json"         # 事件导出（单段月份 → events/）

# ---- 引语出处标注 ----
mkdir -p "$P/out/portraits"
cat > "$P/out/portraits/阿然.md" <<'EOF'
# 阿然
> 一喊就到的人

青禾问「周六去爬香山吗」<!--k:A:1001@青禾-->，阿然一分钟内回了「去！几点集合」<!--k:A:1002-->。
她还说过「八点吧」<!--k:A:1003-->，大家都叫老周「周哥」<!--k:none-->。
老周说的是「八点集合吧」<!--k:A:1003@老周-->，另有「编出来的一句话」<!--k:A:999-->。
最后这句「这句没有标注的话」没写出处。

## 史官曰
好。
EOF
if $PY "$HERE/verify_citations.py" --project "$P" --person 阿然 --md out/portraits/阿然.md --strict | tee "$P/vc.txt"; then echo '--strict 应失败'; exit 1; fi
grep -q '说话人不符：「八点吧」 标注说是 阿然，原文说话人是 老周' "$P/vc.txt"    # 故意的错误归属被抓到
grep -q '原文不符：「八点集合吧」' "$P/vc.txt"
grep -q 'k 不存在：「编出来的一句话」' "$P/vc.txt"
grep -q '未标注：「这句没有标注的话」' "$P/vc.txt"
grep -q '已标注 4，问题 3，未标注 1' "$P/vc.txt"
grep -q '► 2019-03-02 20:01 阿然: 去！' "$P/work/review/阿然-citations.md"   # 出处表带语境
# 构建时标注不进页面
run "$HERE/build_portraits.py" --project "$P" >/dev/null
no 'k:A:' "$P/out/people.html"
grep -q '去！几点集合' "$P/out/people.html"

# ---- mark / reset ----
run "$HERE/pipeline.py" --project "$P" mark read:2015-09_p1 done --note 人工确认
grep -q '"manual": true' "$P/work/state.json"
run "$HERE/pipeline.py" --project "$P" reset read | grep -q '重置 6 个任务'
run "$HERE/pipeline.py" --project "$P" status | grep -q '| read | 子任务 | cheap | split | 4 | 0 | 1 | 1 |'   # 有合格产出的又自动 done

# ---- lite 档：read 用 01、不汇总证据 ----
run "$HERE/pipeline.py" --project "$P" --tier lite next --peek --limit 1 | tee "$P/lite.txt"
grep -q -- '--prompt 01 --files' "$P/lite.txt"
run "$HERE/pipeline.py" --project "$P" --tier lite status | grep -q '| collect' && { echo 'lite 不应有 collect'; exit 1; }

# ---- 不设知情关卡：人物模型给 people 里每个人派；两人私聊照常派写作任务 ----
run "$HERE/pipeline.py" --project "$P" --tier deep status > "$P/deep.txt"
no '知情' "$P/deep.txt"
grep -q '"personas:老周"' "$P/work/state.json" || { echo '人物模型应包含老周'; exit 1; }
$PY "$HERE/fill_prompt.py" --project "$P" --prompt 11 --person 老周 >/dev/null
$PY "$HERE/fill_prompt.py" --project "$P" --prompt 11 --person 阿然 >/dev/null
if $PY "$HERE/fill_prompt.py" --project "$P" --prompt 08 --person 不存在的人 >/dev/null 2>&1; then echo '--person 不存在应报错'; exit 1; fi
cp "$P/chronicle.config.json" "$P/cfg.bak"
$PY - "$P/chronicle.config.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1])); c['scale'] = 'pair'; json.dump(c, open(sys.argv[1], 'w'), ensure_ascii=False)
EOF
run "$HERE/pipeline.py" --project "$P" status > "$P/pair.txt"
no '知情' "$P/pair.txt"
grep -q '| portraits ' "$P/pair.txt"
$PY "$HERE/fill_prompt.py" --project "$P" --prompt 05 --story-id 01 --story-brief x >/dev/null
cp "$P/cfg.bak" "$P/chronicle.config.json"

# ---- config 还没有核心人物：status/next 不崩，提示先选核心人物 ----
Q="$P/nocore"
run "$HERE/init_project.py" --project "$Q" "$SAMPLES/chatlab.json" >/dev/null
run "$HERE/pipeline.py" --project "$Q" status > "$Q/st.txt"
grep -q '| ingest | 脚本 ' "$Q/st.txt"
grep -q '先跑 roster.py apply 选核心人物' "$Q/st.txt"
run "$HERE/pipeline.py" --project "$Q" next --peek > "$Q/next.txt"
grep -q '^## split' "$Q/next.txt"

# ---- 成本估算 ----
run "$HERE/estimate.py" --project "$P" --all-tiers --calibrate > "$P/est.txt"
grep -q '## 档位 lite' "$P/est.txt" && grep -q '## 档位 deep' "$P/est.txt"
grep -q 'read（统一阅读 00）' "$P/est.txt"
grep -A20 '### 旧流程' "$P/est.txt" | grep -q '总计.*8\.[0-9][0-9] 亿'      # 校准场景 ≈ 8.2 亿
test -f "$P/work/estimate.md"
grep -qF '按 API 价格：约 $' "$P/est.txt"
echo "全部通过"
