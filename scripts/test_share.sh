#!/usr/bin/env bash
# 分享形态（卡片 / 年度报告 / 口令加密单文件）的无交互冒烟测试。不会改动传入的项目：先复制到临时目录再跑。
# 用法：scripts/test_share.sh <项目目录（已跑过 ingest、person_stats、事件冻结，最好也有 out/people.html）> [年份]
# 不测浏览器端打开口令页与版面（那部分要 Playwright，见 references/11-share-hosting.md 的「验收」）。
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:?用法：test_share.sh <项目目录> [年份]}"
YEAR="${2:-}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
cp -R "$SRC" "$T/p"; P="$T/p"
PY=python3
ok(){ echo "  ok  $*"; }
fail(){ echo "  FAIL $*"; exit 1; }

echo "1. 分享卡片（只出 HTML）"
$PY "$SKILL/scripts/build_share_cards.py" --project "$P" --no-png >/dev/null
[ -f "$P/out/cards/_group.html" ] || fail "没有群体总卡"
n=$(ls "$P"/out/cards/*.html | grep -vc '_group.html' || true)
[ "$n" -ge 1 ] || fail "没有个人卡"; ok "个人卡 $n 张 + 总卡"
grep -q '%%' "$P"/out/cards/*.html && fail "卡片里有没填的占位符" || ok "占位符都填了"

echo "2. 年度报告"
$PY "$SKILL/scripts/build_wrapped.py" --project "$P" ${YEAR:+--year "$YEAR"} >/dev/null
W=$(ls "$P"/out/wrapped-*.html | head -1); [ -f "$W" ] || fail "没有 wrapped"
s=$(grep -o 'class="slide ' "$W" | wc -l | tr -d ' '); [ "$s" -ge 4 ] || fail "只有 $s 页"; ok "$(basename "$W") $s 页"
# 不允许原文时，页面里不能出现聊天原文（>20 字的消息正文）
$PY - "$P" <<'EOF'
import json, sys, subprocess, pathlib
p = pathlib.Path(sys.argv[1]); cfg = json.loads((p / 'chronicle.config.json').read_text())
cfg.setdefault('pages', {})['show_chat_groups'] = []
(p / 'chronicle.config.json').write_text(json.dumps(cfg, ensure_ascii=False))
EOF
$PY "$SKILL/scripts/build_wrapped.py" --project "$P" ${YEAR:+--year "$YEAR"} >/dev/null
$PY - "$P" "$W" <<'EOF'
import json, sys, pathlib
p, w = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]).read_text()
leak = [m['c'] for m in json.loads((p / 'work/all.json').read_text()) if len(m['c']) > 20 and m['c'].replace(' ⏎ ', '\n') in w]
assert 'class="chat"' not in w, '不允许原文时出现了聊天框'
assert not leak, f'原文泄漏：{leak[:2]}'
EOF
ok "show_chat_groups 为空时不含原文"

echo "3. 口令加密单文件"
if ! $PY -c 'import cryptography' 2>/dev/null; then echo "  跳过：没装 cryptography"; exit 0; fi
PAGE=$(basename "$W")
CHRONICLE_LOCK_PASS='correct horse battery staple' $PY "$SKILL/scripts/build_locked.py" --project "$P" --page "$PAGE" >/dev/null
L="$P/out/locked/$PAGE"; [ -f "$L" ] || fail "没有加密文件"
grep -q '年度报告' "$L" && fail "加密文件里有明文正文" || ok "加密文件不含明文"
$PY - "$L" "$W" <<'EOF'
import base64, json, re, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag
d = json.loads(re.search(r'<script type="application/json" id="blob">(.*?)</script>', open(sys.argv[1]).read(), re.S).group(1))
b = lambda s: base64.b64decode(s)
assert d['it'] >= 200_000
def dec(pw):
    k = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=b(d['salt']), iterations=d['it']).derive(pw.encode())
    return AESGCM(k).decrypt(b(d['iv']), b(d['ct']), None)
assert dec('correct horse battery staple') == open(sys.argv[2], 'rb').read(), '解出来和原页面不一致'
try:
    dec('wrong password!'); raise SystemExit('错口令居然解开了')
except InvalidTag:
    pass
EOF
ok "正确口令还原原页面、错误口令解不开"
CHRONICLE_LOCK_PASS='short' $PY "$SKILL/scripts/build_locked.py" --project "$P" --page "$PAGE" >/dev/null 2>&1 && fail "短口令没被拒绝" || ok "短口令被拒绝"
CHRONICLE_LOCK_PASS='correct horse battery staple' $PY "$SKILL/scripts/build_locked.py" --project "$P" --page "$PAGE" --iterations 1000 >/dev/null 2>&1 \
  && fail "迭代次数过低没被拒绝" || ok "迭代次数 <20 万被拒绝"
echo "全部通过"
