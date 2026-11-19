#!/usr/bin/env bash
# 隐私闸门（默认只提醒 / 严格模式拦）+ 本人确认（可选工具）的冒烟测试（无浏览器交互部分）。
# 用法：bash scripts/test_privacy.sh        （在临时目录里跑，不污染仓库）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SAMPLES="$HERE/../assets/samples"
P="$(mktemp -d)"
trap 'rm -rf "$P"' EXIT
cp "$SAMPLES"/* "$P"/
PY="python3 -I"
run() { echo "+ $*"; $PY "$@"; }
fail() { echo "FAIL: $*"; exit 1; }
blocked() { if $PY "$@" >"$P/gate.log" 2>&1; then cat "$P/gate.log"; fail "严格模式应被闸门拦下：$*"; fi; }
warned() { $PY "$@" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail "默认应只警告、构建成功：$*"; }
           grep -q '隐私闸门·警告' "$P/gate.log" || { cat "$P/gate.log"; fail "应打印警告：$*"; }; }
strict() { $PY - "$P/chronicle.config.json" "$1" <<'EOF'
import json, sys
f = sys.argv[1]; c = json.load(open(f))
c['privacy'] = {'strict': sys.argv[2] == 'on'}
json.dump(c, open(f, 'w'), ensure_ascii=False)
EOF
}
ids() { $PY -c "import json,sys;print(' '.join(h['id'] for h in json.load(open('$P/work/privacy/last_scan.json'))['hits'] if h['severity']=='block'))"; }
G="$HERE/privacy_gate.py"

# 配置：敏感词、真名
$PY - "$P/chronicle.config.json" <<'EOF'
import json, sys
f = sys.argv[1]; c = json.load(open(f))
c['sensitive_words'] = ['搬家公司那事']
c['real_names'] = {'老周': '周建国'}
c['blocked_snippets'] = ['老周年轻时候的外号叫胖周']
json.dump(c, open(f, 'w'), ensure_ascii=False)
EOF
run "$HERE/ingest.py" --project "$P" >/dev/null
mkdir -p "$P/work/stable" "$P/out/portraits" "$P/out/stories" "$P/out/personas"
cat > "$P/work/stable/2019-03.json" <<'EOF'
{"month": "2019-03", "month_summary": "相约爬香山", "events": [
 {"date": "2019-03-02", "title": "约爬香山", "summary": "青禾提议周六爬香山，大家定了八点集合。", "people": ["青禾", "阿然", "老周"],
  "category": "聚会出行", "heat": 2, "refs": ["A:7000000000000000001"], "groups": ["主群"]},
 {"date": "2019-03-03", "title": "老周搬家", "summary": "老周说起搬家公司那事，大家笑了一晚上。", "people": ["老周"],
  "category": "群内热议", "heat": 1, "refs": ["A:7000000000000000003"], "groups": ["主群"]}]}
EOF
printf '# 老周\n> 一句品藻\n\n老周爱爬山，周六一早就在群里喊人。\n\n他的电话 13812345678，邮箱 laozhou@example.com。\n\n大家都叫他胖周，这是老周年轻时候的外号。\n\n## 史官曰\n好。\n' > "$P/out/portraits/老周.md"
printf '# 老周 · 人物模型\n\n## 10. 对照清单\n| 编号 | 判断 | 置信度 | 依据 | 本人 |\n|---|---|---|---|---|\n| 1 | 他组局总是第一个到 | 高 | 2019-03 | |\n| 2 | 他不爱谈工作 | 低 | 少 | |\n' > "$P/out/personas/老周.md"

# 1. 默认只提醒：敏感词（大事记）、电话+邮箱+已删除素材（近似）（人物志）都作为警告打印，页面照常生成
warned "$HERE/build_chronicle.py" --project "$P"
grep -q '本群敏感词：搬家公司那事' "$P/gate.log" || fail '敏感词'
grep -q '只提醒、构建照常继续' "$P/gate.log" || fail '默认应说明只提醒'
[ -e "$P/out/chronicle.html" ] || fail '默认模式应生成 chronicle.html'
[ -e "$P/work/privacy/last_scan.json" ] || fail '应写 last_scan.json'
warned "$HERE/build_portraits.py" --project "$P"
grep -q '手机号' "$P/gate.log" && grep -q '邮箱' "$P/gate.log" || fail 'pii'
grep -q '已删除素材' "$P/gate.log" || fail '已删除素材（近似匹配）'
[ -e "$P/out/people.html" ] || fail '默认模式应生成 people.html'
$PY "$G" --project "$P" >/dev/null 2>&1 || fail '单独运行默认应返回 0'
if $PY "$G" --project "$P" --strict >/dev/null 2>&1; then fail '--strict 有重点命中应返回非 0'; fi
# 2. 严格模式（config.privacy.strict）：同样的命中拦下构建；标记已看过（--allow）后可以构建
strict on
rm "$P/out/chronicle.html"
blocked "$HERE/build_chronicle.py" --project "$P"
grep -q '本群敏感词：搬家公司那事' "$P/gate.log" || fail '严格模式·敏感词'
[ ! -e "$P/out/chronicle.html" ] || fail '严格模式拦下后不应生成 chronicle.html'
blocked "$HERE/build_portraits.py" --project "$P"
run "$G" --project "$P" --target portraits >/dev/null 2>&1 || true
run "$G" --project "$P" --allow $(ids) --reason 测试
run "$HERE/build_portraits.py" --project "$P" >/dev/null
grep -q '"reason": "测试"' "$P/work/privacy/allowlist.json"
# 改掉原文也能构建
sed -i.bak 's/搬家公司那事/搬家的事/' "$P/work/stable/2019-03.json"
run "$HERE/build_chronicle.py" --project "$P" >/dev/null
# 3. 人物模型隔离：小传里引用 out/personas/ 或出现模型章节标题
printf '\n他的大五人格里外向性很高（见 out/personas/老周.md）。\n' >> "$P/out/portraits/老周.md"
blocked "$HERE/build_portraits.py" --project "$P"
grep -q '人物模型内容' "$P/gate.log" || fail 'persona'
strict off
warned "$HERE/build_portraits.py" --project "$P"
grep -q '人物模型内容' "$P/gate.log" || fail 'persona 默认应警告'
sed -i.bak '$d' "$P/out/portraits/老周.md"
run "$HERE/build_portraits.py" --project "$P" >/dev/null 2>&1
# 4. 真名：小剧场里算重点（CAST.md 的真名列不查）
printf '| 化名 | 真名 | 称呼 |\n|---|---|---|\n| 周山 | 周建国 | 老周 |\n' > "$P/out/stories/CAST.md"
printf '# 山行\n> 导语\n\n周山约大家爬山。\n' > "$P/out/stories/01-山行.md"
run "$HERE/build_stories.py" --project "$P" >/dev/null
printf '\n周建国说八点集合。\n' >> "$P/out/stories/01-山行.md"
warned "$HERE/build_stories.py" --project "$P"
grep -q '真名：周建国' "$P/gate.log" || fail 'realname'
strict on
blocked "$HERE/build_stories.py" --project "$P"
strict off
sed -i.bak '$d' "$P/out/stories/01-山行.md"
# 5. --scan 单独扫描（默认返回 0，--strict 返回非 0）；--add-blocked 追加
printf '身份证 110101199003071234 银行卡 6222 0212 3456 7891 234\n' > "$P/x.txt"
$PY "$G" --project "$P" --scan "$P/x.txt" >"$P/gate.log" 2>&1 || fail '--scan 默认应返回 0'
grep -q '身份证号' "$P/gate.log" || fail 'idcard'
$PY "$G" --project "$P" --scan "$P/x.txt" --strict >"$P/gate.log" 2>&1 && fail '--scan --strict 应返回非 0'
run "$G" --project "$P" --add-blocked "周山约大家爬山"
run "$G" --project "$P" --add-blocked "周山约大家爬山" | grep -q '已追加 0 条'
warned "$HERE/build_stories.py" --project "$P"
grep -q '已删除素材：周山约大家爬山' "$P/gate.log" || fail 'add-blocked 应警告'
# 6. 打包网站：页面被手改加回已删除素材 → 默认警告、照常打包；严格模式拦下
rm "$P/work/privacy/blocked.txt"
run "$HERE/build_stories.py" --project "$P" >/dev/null 2>&1
sed -i.bak 's#</body>#<p>老周年轻时候的外号叫胖周</p></body>#' "$P/out/people.html"
warned "$HERE/package_site.py" --project "$P"
grep -q 'out/people.html' "$P/gate.log" || fail 'html 复查'
strict on
blocked "$HERE/package_site.py" --project "$P"
strict off
run "$HERE/build_portraits.py" --project "$P" >/dev/null 2>&1
# 没做本人确认：不影响打包，也不提醒
$PY "$HERE/package_site.py" --project "$P" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail '没做本人确认也应能打包'; }
grep -q '本人确认' "$P/gate.log" && fail '没回收过确认结果不应提醒' || true

# 7. 本人确认页（可选）+ 回收：只汇总、只提醒，不拦
run "$HERE/build_review_pages.py" --project "$P" --person 老周
F="$P/out/review/老周.html"
grep -q '他组局总是第一个到' "$F" && grep -q '老周搬家' "$F" && grep -q '老周爱爬山' "$F"
grep -Eq '(src|href)="https?:' "$F" && fail '确认页不应有外部请求'
grep -q '本人确认' "$F" && grep -q '>可以公开<' "$F" && grep -q '>要改<' "$F" && grep -q '>别公开<' "$F" || fail '确认页按钮'
grep -q '按不公开' "$F" && fail '确认页不应再有“没点按不公开”的说法' || true
$PY - "$F" "$P/in.txt" <<'EOF'
import json, sys, re
html = open(sys.argv[1]).read()
meta = json.loads(re.search(r'id="meta">(.*?)</script>', html, re.S).group(1).replace('<\\/', '</'))
it = meta['items']
pick = {'p02': ('public', ''), 'p03': ('hide', ''), 'p04': ('wrong', '不是这样'), 'c01': ('partly', '只在周末'), 'e001': ('public', ''), 'e002': ('hide', '别提搬家')}
rows = []
for k, v in it.items():
    r = {'id': k, 'kind': v['kind'], 'key': v['key'], 'v': pick.get(k, ('', ''))[0]}
    if pick.get(k, ('', ''))[1]: r['note'] = pick[k][1]
    if r['v'] in ('hide', 'wrong', 'partly'): r['text'] = v['text']; r.update({'title': v['title']} if 'title' in v else {})
    rows.append(r)
d = {'schema': 'gcc-review/1', 'project': meta['project'], 'person': meta['person'], 'page': meta['page'],
     'generated': '2026-01-01T00:00:00Z', 'answered': 6, 'total': len(rows), 'general': '挺好', 'items': rows}
open(sys.argv[2], 'w').write('老周：看完了\n' + json.dumps(d, ensure_ascii=False) + '\n')
EOF
run "$HERE/collect_reviews.py" --project "$P" --in "$P/in.txt"
C="$P/work/review/replies.md"
grep -q '| 老周 | 2026-01-01 | 6/' "$C" && grep -q '只在周末' "$C" && grep -q '别公开（2）' "$C" && grep -q '## 未回收' "$C" || fail 'replies.md'
[ -e "$P/work/review/replies/老周.json" ] || fail 'replies/<人>.json'
$PY "$HERE/package_site.py" --project "$P" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail '有人标了别公开也应能打包（只提醒）'; }
grep -q '\[本人确认·提醒\] 老周 有 2 条标了别公开、1 条标了要改' "$P/gate.log" || { cat "$P/gate.log"; fail '应打一行确认汇总'; }
$PY "$HERE/build_portraits.py" --project "$P" >"$P/gate.log" 2>&1 && grep -q '本人确认·提醒' "$P/gate.log" || fail 'build_portraits 应提醒'
[ ! -e "$P/work/privacy/blocked.txt" ] || fail '没加 --apply-blocked 不应写 blocked.txt'
run "$HERE/collect_reviews.py" --project "$P" --in "$P/in.txt" --apply-blocked
grep -q '来自 老周 本人确认' "$P/work/privacy/blocked.txt"
warned "$HERE/build_portraits.py" --project "$P"          # 「别公开」的段落还在小传里 → 默认警告
grep -q '已删除素材' "$P/gate.log" || fail '别公开的段落应警告'
strict on
blocked "$HERE/build_portraits.py" --project "$P"         # 严格模式 → 拦
strict off
# 8. public_detail=standard：人物志、月报里的具体金额与门牌住址算重点；工作变故词在内置词表里
mkdir -p "$P/out/digest"
printf '# 三月月报\n老周搬去了幸福路12号，房租3500元，上个月裸辞了。\n' > "$P/out/digest/2019-03.md"
$PY "$G" --project "$P" --target digest >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail '默认应只警告'; }
grep -q '具体住址' "$P/gate.log" && grep -q '具体金额' "$P/gate.log" && grep -q '内置词表·工作单位职级' "$P/gate.log" || fail 'digest 规则'
if $PY "$G" --project "$P" --target digest --strict >"$P/gate.log" 2>&1; then cat "$P/gate.log"; fail '严格模式下月报里的金额/住址应拦'; fi
printf '\n他家在3号楼2单元。\n' >> "$P/out/portraits/老周.md"
if $PY "$G" --project "$P" --target portraits --strict >"$P/gate.log" 2>&1; then fail '严格模式下人物志里的门牌应拦'; fi
grep -q '具体住址' "$P/gate.log" || fail 'address'
# 9. 严格模式下 --allow 稳定：报错里给的 id（含页面复查、persona 命中）都能 allow，中间跑别的构建也不影响
Q="$P/q"; mkdir -p "$Q/work/stable"
cp "$SAMPLES"/* "$Q"/
$PY - "$Q/chronicle.config.json" <<'EOF'
import json, sys
f = sys.argv[1]; c = json.load(open(f))
c['sensitive_words'] = ['搬家公司那事']; c['privacy'] = {'strict': True}
json.dump(c, open(f, 'w'), ensure_ascii=False)
EOF
$PY "$HERE/ingest.py" --project "$Q" >/dev/null
cp "$P/work/stable/2019-03.json.bak" "$Q/work/stable/2019-03.json"   # 含“搬家公司那事”的原版
gate_ids() { grep -oE '^  [0-9a-f]{10}  ' "$P/gate.log" | tr -d ' ' | sort -u; }
blocked "$HERE/build_chronicle.py" --project "$Q"
grep -q '本群敏感词：搬家公司那事' "$P/gate.log" || fail '应拦下敏感词'
IDS="$(gate_ids)"; [ -n "$IDS" ] || fail '报错里应给出 id'
$PY "$HERE/build_stats.py" --project "$Q" >/dev/null 2>&1 || true    # 别的构建跑一遍，最近一次扫描换了口径
run "$G" --project "$Q" --allow $IDS --reason 测试 | tee "$P/allow.log"
grep -q '不在 last_scan.json' "$P/allow.log" && fail '报错里的 id 应能在 last_scan.json 找到'
run "$HERE/build_chronicle.py" --project "$Q" >/dev/null 2>&1 || fail 'allow 后 build_chronicle 应通过'
$PY "$HERE/package_site.py" --project "$Q" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail 'allow 后 package_site 应通过（页面复查按规则+原文认）'; }
# 页面里引用了 personas/：id 不再是 '-'，allow 后能打包
sed -i.bak 's#</body>#<p>详见 personas/老周.md</p></body>#' "$Q/out/chronicle.html"
blocked "$HERE/package_site.py" --project "$Q"
grep -q '页面里引用了 personas/' "$P/gate.log" || fail 'persona 页面复查'
IDS="$(gate_ids)"; [ -n "$IDS" ] || fail 'persona 命中应有 id'
run "$G" --project "$Q" --allow $IDS --reason 测试 >/dev/null
$PY "$HERE/package_site.py" --project "$Q" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail 'persona allow 后应能打包'; }
# 10. --scan 不存在的文件：友好报错、退出码 1、不 traceback
set +e; $PY "$G" --project "$Q" --scan "$Q/没有这个文件.md" >"$P/gate.log" 2>&1; rc=$?; set -e
[ "$rc" = 1 ] && grep -q '找不到文件' "$P/gate.log" && ! grep -q Traceback "$P/gate.log" || { cat "$P/gate.log"; fail '--scan 不存在的文件'; }
# 11. 本人确认回收文件损坏：跳过并提醒，打包照常
mkdir -p "$Q/work/review/replies"; printf '{坏掉的' > "$Q/work/review/replies/坏.json"
$PY "$HERE/package_site.py" --project "$Q" >"$P/gate.log" 2>&1 || { cat "$P/gate.log"; fail '回收文件坏了不应中止打包'; }
grep -q '跳过读不了的回收文件' "$P/gate.log" || fail '应提醒跳过坏文件'
echo "隐私闸门 + 本人确认：全部通过"
