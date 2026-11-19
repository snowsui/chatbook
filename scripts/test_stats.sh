#!/usr/bin/env bash
# 数据页（build_stats.py）冒烟测试：合成语料 → ingest → build_stats → 单文件页 → 打包网站。
# 用法：bash scripts/test_stats.sh        （在临时目录里跑，不污染仓库；KEEP=<空目录> 则保留产物便于人工打开看）
# 1. 手造小群：复读 / @ / 引用 / 口头禅 / 路人 / 敏感短句的精确断言
# 2. 评测语料 roommates（chatlab，6671 条；导出文件不在仓库里，缺了先用 build_corpus.py 生成）：字段、合计、敏感词零命中、hash 种子无关
# 3. 隐私闸门：config.pages.stats 文案里有本群敏感词 → 默认警告且构建成功；严格模式（privacy.strict）拦下
# 4. lang=en；5. package_site 出 /stats；5b. 昵称带 HTML 标签 → 提示框按字面显示；6. 浏览器（有 playwright 才跑）
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/.."
T="${KEEP:-$(mktemp -d)}"; [ -n "${KEEP:-}" ] || trap 'rm -rf "$T"' EXIT
PY="python3 -I"
ok(){ echo "  ok  $*"; }
fail(){ echo "  FAIL $*"; exit 1; }

echo "1. 手造小群"
P="$T/mini"; mkdir -p "$P/work"
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
json.dump({"title": "测试群大事记", "me": "甲", "groups": [{"key": "A", "label": "主群", "file": "x.txt", "format": "txt"},
           {"key": "B", "label": "家属群", "file": "y.txt", "format": "txt"}],
           "aliases": {"小乙": "乙"}, "members": ["甲", "乙", "丙", "丁"], "people": ["乙"],
           "sensitive_words": ["秘密基地"], "real_names": {"乙": "王二丫"}, "taboo_extra": ["丙的相亲"],
           "pages": {"show_chat_groups": ["A"]}}, open(f'{p}/chronicle.config.json', 'w'), ensure_ascii=False)
rows = []
def say(t, g, s, c):
    rows.append({'id': f'{g[0]}{len(rows)}', 'k': f'{g[0]}:{len(rows)}', 'g': g, 't': t, 's': s, 'c': c})
# 复读：两人 10 分钟内 → 1 次；隔 11 分钟 → 不算；应答句、带敏感词的句子算次数但不展示
say('2022-01-03 10:00:00', '主群', '乙', '冲冲冲'); say('2022-01-03 10:01:00', '主群', 'me', '[图片]')
say('2022-01-03 10:02:00', '主群', 'me', '冲冲冲'); say('2022-01-03 10:03:00', '主群', '丙', '冲冲冲')
say('2022-01-04 10:00:00', '主群', '乙', '下雨了'); say('2022-01-04 10:11:00', '主群', '丙', '下雨了')
say('2022-01-05 10:00:00', '主群', '乙', '好的'); say('2022-01-05 10:01:00', '主群', '丙', '好的')
say('2022-01-06 10:00:00', '主群', '乙', '工资到了'); say('2022-01-06 10:01:00', '主群', '丁', '工资到了')
say('2022-01-06 11:00:00', '主群', '乙', '去秘密基地'); say('2022-01-06 11:01:00', '主群', '丁', '去秘密基地')
say('2022-01-07 10:00:00', '家属群', '乙', '晚饭吃啥呀'); say('2022-01-07 10:01:00', '家属群', '丙', '晚饭吃啥呀')
# @ 与引用：@ 认 aliases；引用里的名字已归一
say('2022-01-08 10:00:00', '主群', 'me', '@小乙 在吗'); say('2022-01-08 10:05:00', '主群', '乙', '在（回复 甲: @小乙 在吗）')
# 口头禅：5 次跨 3 个月 → 上；5 次同一月 → 不上；路人不进按人统计
for i, m in enumerate(['02', '02', '03', '04', '04']):
    say(f'2022-{m}-1{i} 09:00:00', '主群', '丁', '绝绝子')
    say(f'2022-05-1{i} 09:00:00', '主群', '丁', '一次性')
    say(f'2022-{m}-1{i} 09:30:00', '主群', '丙', '哈哈哈哈')
for i, m in enumerate(['02', '03', '04', '05', '06']):
    say(f'2022-{m}-2{i} 09:00:00', '主群', '丙', '王二丫来了')
    say(f'2022-{m}-2{i} 10:00:00', '主群', '丙', '相亲去了')
say('2022-06-01 09:00:00', '主群', '路人', '大家好')
rows.sort(key=lambda r: r['t'])
json.dump(rows, open(f'{p}/work/all.json', 'w'), ensure_ascii=False)
EOF
$PY "$HERE/build_stats.py" --project "$P" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "build_stats 失败"; }
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
d = json.load(open(f'{p}/work/stats.json')); allm = json.load(open(f'{p}/work/all.json'))
names = [x['n'] for x in d['people']]
assert names == ['甲', '乙', '丙', '丁'], names                          # 路人不进按人统计
I = {n: i for i, n in enumerate(names)}
c = d['combos']['all|all']
assert c['total'] == len(allm) and c['members'] == 5                       # 路人仍计入整体
assert sum(map(sum, c['heat'])) == len(allm) and sum(c['types']) == len(allm)
assert c['types'][d['cats'].index('图片')] == 1
ev = d['repeat']['events']; ph = d['repeat']['phrases']
assert len(ev) == 5, ev                                                    # 冲冲冲、好的、工资到了、秘密基地、家属群那句；下雨了隔 11 分钟不算
first = ev[0]; assert first[3] == I['乙'] and first[4] == [I['甲'], I['丙']], first   # 中间夹图片不打断
assert ph == ['冲冲冲'], ph                                                 # 应答、敏感、本群敏感词、不公开群都不展示
assert [e[2] for e in ev if e[1] == 'B'] == [-1]
assert [I['甲'], I['乙'], 1] in c['at'], c['at']                            # @小乙 → 乙
assert [I['乙'], I['甲'], 1] in c['quote'], c['quote']
assert d['catch'][str(I['丁'])] == [['绝绝子', 5]], d['catch']             # 一次性（同一月）不上
assert d['catch'][str(I['丙'])] == [], d['catch']                          # 真名、禁区片段（相亲）被滤
assert d['laugh'][str(I['丙'])] == [['哈哈哈哈', 5]]
assert set(d['combos']) == {'all|all', 'all|2022', 'A|all', 'A|2022', 'B|all', 'B|2022'}
assert all(x['core'] for x in d['people']) and d['cfg']['diversN'] == 1   # people 不足 3 人 → 核心 = members；潜水榜最多点 4//3 = 1 人
EOF
ok "复读 / @ / 引用 / 口头禅 / 路人 / 敏感短句"
# 没有真实时刻的群（ingest 记在 work/ingest.json）不进作息类统计；口头禅不算接龙行与纯称呼
cp "$P/work/all.json" "$T/all.bak"
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
rows = json.load(open(f'{p}/work/all.json'))
for i, m in enumerate(['02', '03', '04', '05', '06']):
    rows += [{'id': f'Z{i}', 'k': f'A:z{i}', 'g': '主群', 't': f'2022-{m}-0{i + 1} 08:00:00', 's': '丁', 'c': '1. 丁'},
             {'id': f'Y{i}', 'k': f'A:y{i}', 'g': '主群', 't': f'2022-{m}-0{i + 1} 08:10:00', 's': '丁', 'c': '小乙'}]
rows.sort(key=lambda r: r['t'])
json.dump(rows, open(f'{p}/work/all.json', 'w'), ensure_ascii=False)
json.dump({'v': 1, 'no_time': ['家属群']}, open(f'{p}/work/ingest.json', 'w'))
EOF
$PY "$HERE/build_stats.py" --project "$P" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "build_stats 失败"; }
$PY - "$P" <<'EOF'
import json, sys
p = sys.argv[1]
d = json.load(open(f'{p}/work/stats.json')); allm = json.load(open(f'{p}/work/all.json'))
I = {x['n']: i for i, x in enumerate(d['people'])}
c = d['combos']['all|all']
fam = sum(1 for m in allm if m['g'] == '家属群')
assert fam and sum(map(sum, c['heat'])) == len(allm) - fam, (sum(map(sum, c['heat'])), len(allm), fam)
assert sum(c['p'][str(I['丙'])]['h']) == c['p'][str(I['丙'])]['n'] - 1        # 丙在家属群那条不进活跃时段
assert d['noTime'] == ['家属群'], d.get('noTime')
assert d['catch'][str(I['丁'])] == [['绝绝子', 5]], d['catch']                # 「1. 丁」「小乙」都不算口头禅
EOF
cp "$T/all.bak" "$P/work/all.json"; rm "$P/work/ingest.json"
$PY "$HERE/build_stats.py" --project "$P" >/dev/null 2>&1
ok "无时刻的群不进作息统计；接龙行、纯称呼不算口头禅"
H="$P/out/stats.html"
grep -q '%%' "$H" && fail "页面里有没填的占位符" || true
grep -q 'id="data">{' "$H" || fail "单文件页没有内嵌数据"
grep -q '王二丫\|秘密基地\|工资' "$H" && fail "页面里出现了真名/敏感词" || ok "单文件页：数据内嵌、无真名敏感词"

echo "2. 评测语料 roommates"
R="$T/rm"; mkdir -p "$R/exports"
[ -f "$SKILL/evals/corpus/roommates/exports/roommates.json" ] || $PY "$SKILL/evals/corpus/build_corpus.py" "$SKILL/evals/corpus/roommates" >/dev/null
cp "$SKILL/evals/corpus/roommates/exports/roommates.json" "$R/exports/"
$PY - "$SKILL/evals/corpus/roommates/truth/config.json" "$R/chronicle.config.json" <<'EOF'
import json, sys
c = json.load(open(sys.argv[1]))
c['sensitive_words'] = ['煤球']; c['real_names'] = {'芳姐': '李芳洲', '老赵': '赵屹'}
json.dump(c, open(sys.argv[2], 'w'), ensure_ascii=False)
EOF
$PY "$HERE/ingest.py" --project "$R" >/dev/null
PYTHONHASHSEED=1 python3 "$HERE/build_stats.py" --project "$R" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "build_stats 失败"; }
cp "$R/work/stats.json" "$T/s1.json"
PYTHONHASHSEED=2 python3 "$HERE/build_stats.py" --project "$R" --no-page >/dev/null 2>&1
cmp -s "$T/s1.json" "$R/work/stats.json" || fail "换 hash 种子结果不同（有按 set 迭代顺序计数/排序的地方）"
ok "两个 hash 种子结果逐字节相同"
$PY - "$R" <<'EOF'
import json, re, sys
p = sys.argv[1]
d = json.load(open(f'{p}/work/stats.json')); allm = json.load(open(f'{p}/work/all.json'))
assert set(d) >= {'people', 'cats', 'years', 'groups', 'daily', 'combos', 'repeat', 'catch', 'laugh', 'cloud', 'cfg', 'lang'}
c = d['combos']['all|all']
assert c['total'] == len(allm) == sum(d['daily']['all'])
assert sum(v['n'] for v in c['p'].values()) == len(allm)
assert sum(d['combos'][f'all|{y}']['total'] for y in d['years']) == len(allm)
assert len(c['heat']) == 7 and all(len(r) == 24 for r in c['heat'])
assert c['quote'] and c['next'] and c['graph']['edges'] and len(d['cloud']) >= 50
assert d['groups'][0]['quote'] is False and d['repeat']['phrases'] == []    # 没配 show_chat_groups：复读句不展示
shown = [w for w, _ in d['cloud']] + [t for rows in d['catch'].values() for t, _ in rows] + [t for rows in d['laugh'].values() for t, _ in rows]
bad = re.compile(r'煤球|李芳洲|赵屹|工资|医院|公司|分手|怀孕|小区|offer|\d{2,}元')
hit = [w for w in shown if bad.search(w)]
assert not hit, hit
page = open(f'{p}/out/stats.html').read()
assert not re.search(r'李芳洲|赵屹', page)
print('  ', len(allm), '条；词云', len(d['cloud']), '词；口头禅', sum(map(len, d['catch'].values())), '条')
EOF
ok "字段、合计、敏感词零命中"

echo "3. 隐私闸门"
cp "$R/out/stats.html" "$T/rm-stats.html"   # 第 6 节浏览器测试用这一版
$PY - "$R/chronicle.config.json" <<'EOF'
import json, sys
f = sys.argv[1]; c = json.load(open(f)); c.setdefault('pages', {})['stats'] = {'lede': '煤球也在群里'}
json.dump(c, open(f, 'w'), ensure_ascii=False)
EOF
rm -f "$R/out/stats.html"
$PY "$HERE/build_stats.py" --project "$R" >"$T/gate.log" 2>&1 || { cat "$T/gate.log"; fail "默认模式不该拦下构建"; }
grep -q '本群敏感词：煤球' "$T/gate.log" || { cat "$T/gate.log"; fail "没有警告敏感词"; }
[ -f "$R/out/stats.html" ] || fail "默认模式应生成 stats.html"
ok "页面文案含本群敏感词 → 警告、照常出页面"
$PY "$HERE/privacy_gate.py" --project "$R" --target stats >/dev/null 2>&1 || fail "--target stats 默认应返回 0"
$PY "$HERE/privacy_gate.py" --project "$R" --target stats --strict >/dev/null 2>&1 && fail "--target stats --strict 应失败" || ok "--target stats 可单独跑"
$PY - "$R/chronicle.config.json" <<'EOF'
import json, sys
f = sys.argv[1]; c = json.load(open(f)); c['privacy'] = {'strict': True}
json.dump(c, open(f, 'w'), ensure_ascii=False)
EOF
rm -f "$R/out/stats.html"
if $PY "$HERE/build_stats.py" --project "$R" >"$T/gate.log" 2>&1; then fail "严格模式下 pages.stats 里的敏感词没被拦"; fi
grep -q '本群敏感词：煤球' "$T/gate.log" || { cat "$T/gate.log"; fail "拦下原因不对"; }
[ ! -f "$R/out/stats.html" ] || fail "严格模式拦下后不应有 stats.html"
ok "严格模式：页面文案含本群敏感词 → 拦下"
cp "$T/rm-stats.html" "$R/out/stats.html"

echo "4. lang=en"
E="$T/en"; mkdir -p "$E/work"
$PY - "$E" <<'EOF'
import json, sys, random, datetime as dt
p = sys.argv[1]
json.dump({"title": "Test", "me": "Ann", "lang": "en", "groups": [{"key": "A", "label": "Main", "file": "x.txt", "format": "txt"}],
           "members": ["Ann", "Bob", "Cy", "Dee"], "aliases": {"bobby": "Bob"}, "pages": {"show_chat_groups": ["A"]}},
          open(f'{p}/chronicle.config.json', 'w'))
rnd = random.Random(3); t = dt.datetime(2023, 1, 1, 9); rows = []
lines = ['lol', 'anyone free tonight?', 'pizza again', 'my salary is late', 'that movie was wild', '[图片]', '[表情]',
         'see you at the pub', 'hiking on saturday', 'pizza again', 'no way', 'brunch tomorrow?', '@bobby you there']
for i in range(1500):
    t += dt.timedelta(minutes=rnd.choice([1, 2, 5, 40, 300, 700]))
    rows.append({'id': f'A{i}', 'k': f'A:{i}', 'g': 'Main', 't': t.strftime('%Y-%m-%d %H:%M:%S'),
                 's': rnd.choice(['me', 'Bob', 'Cy', 'Dee']), 'c': rnd.choice(lines)})
json.dump(rows, open(f'{p}/work/all.json', 'w'))
EOF
$PY "$HERE/build_stats.py" --project "$E" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "en build 失败"; }
$PY - "$E" <<'EOF'
import json, sys
p = sys.argv[1]; d = json.load(open(f'{p}/work/stats.json'))
assert d['lang'] == 'en' and d['tokenizer'] == 'words'
ws = [w for w, _ in d['cloud']]
assert 'pizza' in ws and 'salary' not in ws and not any(' ' in w for w in ws), ws
c = d['combos']['all|all']; assert c['at'] and c['at'][0][1] == 1, c['at']      # @bobby → Bob
assert any(t == 'pizza again' for rows in d['catch'].values() for t, _ in rows), d['catch']
page = open(f'{p}/out/stats.html').read()
assert '<html lang="en"' in page and 'Stats' in page
EOF
ok "英文：按词分词、@ 别名、口头禅、页面语言"

echo "5. 打包网站"
mkdir -p "$P/work/stable"
cat > "$P/work/stable/2022-01.json" <<'EOF'
{"month": "2022-01", "month_summary": "开年", "events": [
 {"date": "2022-01-03", "title": "开年冲冲冲", "summary": "大家在群里喊冲冲冲。", "people": ["乙", "甲"],
  "category": "群内热议", "heat": 2, "refs": ["A:0"], "groups": ["主群"]}]}
EOF
# 先有大事记 + 人物志、后有数据页：单文件版的旧导航里没有“数据”，打包时要补上
mkdir -p "$P/out/portraits"; printf '# 乙\n> 一句话\n\n乙爱喊冲冲冲。\n' > "$P/out/portraits/乙.md"
mv "$P/out/stats.html" "$T/stats.html"
$PY "$HERE/build_chronicle.py" --project "$P" >/dev/null 2>&1
$PY "$HERE/build_portraits.py" --project "$P" >/dev/null 2>&1
grep -q 'data-tab="stats"' "$P/out/people.html" && fail "前提不成立" || true
mv "$T/stats.html" "$P/out/stats.html"
$PY "$HERE/package_site.py" --project "$P" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "package_site 失败"; }
S="$P/site/public/stats.html"
[ -f "$S" ] || fail "没有 site/public/stats.html"
grep -q 'data-stats="/data/stats\.[0-9a-f]*\.json"' "$S" || fail "数据页没指向带哈希的数据"
grep -q '<script src="/assets/stats\.[0-9a-f]*\.js" defer>' "$S" || fail "数据页脚本没抽出"
grep -q 'id="data"' "$S" && fail "网站版还内嵌着数据" || true
ls "$P"/site/public/data/stats.*.json "$P"/site/public/assets/stats.*.js >/dev/null || fail "哈希文件不存在"
grep -q 'href="/stats"' "$P/site/public/chronicle.html" || fail "网站版大事记导航没有 /stats"
grep -q 'href="/stats"' "$P/site/public/people.html" || fail "网站版人物志导航没有 /stats"
grep -q 'href="/people"' "$S" || fail "数据页导航没有 /people"
grep -q "'/stats'" "$P/site/src/index.js" || fail "Worker 没放行 /stats"
ok "网站版：哈希数据/脚本、第四栏导航、Worker 放行"
if command -v node >/dev/null; then node --check "$(ls "$P"/site/public/assets/stats.*.js)" && ok "脚本语法（node --check）"; fi

echo "5b. 提示框转义"
X="$T/xss"; mkdir -p "$X/work"
$PY - "$X" <<'EOF'
import json, sys
p = sys.argv[1]; bad = '<img src=x onerror=alert(1)>'
json.dump({"title": "转义测试", "me": "甲", "groups": [{"key": "A", "label": "主群", "file": "x.txt", "format": "txt"}],
           "members": ["甲", bad, "丙"], "pages": {"show_chat_groups": ["A"]}}, open(f'{p}/chronicle.config.json', 'w'), ensure_ascii=False)
rows = [{'id': f'A{i}', 'k': f'A:{i}', 'g': '主群', 't': f'2022-01-0{1 + i % 5} 1{i % 10}:00:00',
         's': [bad, '丙', 'me'][i % 3], 'c': ['吃饭去', '<b>加粗</b>', '好的'][i % 3]} for i in range(30)]
json.dump(rows, open(f'{p}/work/all.json', 'w'), ensure_ascii=False)
EOF
$PY "$HERE/build_stats.py" --project "$X" >/dev/null 2>"$T/err" || { cat "$T/err"; fail "build_stats 失败"; }
# 数据内嵌在 application/json 脚本里（不执行）；除此之外的页面源码不应出现该标签
$PY -c "import re,sys; h=open(sys.argv[1],encoding='utf-8').read(); h=re.sub(r'<script type=\"application/json\" id=\"data\">.*?</script>','',h,flags=re.S); sys.exit('<img src=x' in h)" "$X/out/stats.html" || fail "页面源码里出现了未转义的 <img"
JS="$SKILL/assets/templates/stats.js"
grep -qE "innerHTML = (html|t\.getAttribute)" "$JS" && fail "提示框仍把 data-tip 原样写进 innerHTML"
grep -q 'tip.innerHTML = tipHtml(' "$JS" || fail "showTip 没经 tipHtml 转义"
if command -v node >/dev/null; then
  # 取模板里的 esc / tipHtml 原样执行，喂 getAttribute 解码后的提示文字
  node - "$JS" <<'EOF' || fail "tipHtml 没挡住标签"
const src = require('fs').readFileSync(process.argv[2], 'utf8');
const esc = eval(src.match(/const esc = ([^\n]+);/)[1]);
const tipHtml = eval(src.match(/const tipHtml = ([^\n]+);/)[1]);
const out = tipHtml('<img src=x onerror=alert(1)>：最常在 9 点说话<br><b>3</b> 条');
if (/<img/.test(out) || !out.includes('&lt;img') || !out.includes('<br><b>3</b>')) { console.error(out); process.exit(1); }
EOF
fi
ok "昵称 <img …> → 页面源码与提示框里都按字面显示"

echo "6. 浏览器"
if ! python3 -c 'import playwright' 2>/dev/null; then echo "  跳过：没装 playwright"; echo "全部通过"; exit 0; fi
python3 - "$P/out/stats.html" "$R/out/stats.html" "$E/out/stats.html" "$X/out/stats.html" <<'EOF'
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for path in sys.argv[1:]:
        for w in (1280, 375):
            pg = b.new_page(viewport={'width': w, 'height': 900}); errs = []
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
            pg.goto('file://' + path); pg.wait_for_selector('#s-cards')
            for sel in ['#f-y button:nth-of-type(2)', '#mxtabs button:nth-of-type(2)', '#chips button:last-child', '#gran button']:
                if pg.query_selector(sel): pg.click(sel)
            if path.endswith('/xss/out/stats.html'):   # 逐个悬停提示：不应渲染出 <img> 标签
                for el in pg.query_selector_all('[data-tip]'):
                    if el.is_visible(): el.hover()
                    assert not pg.query_selector('#tip img'), (path, pg.inner_html('#tip'))
            assert not errs, (path, errs)
            assert pg.evaluate('document.documentElement.scrollWidth') <= w, (path, w, '横向溢出')
            pg.close()
    b.close()
EOF
ok "三个页面在 1280/375 宽度下无 JS 报错、无横向溢出"
echo "全部通过"
