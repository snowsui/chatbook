"""把任一 out/*.html 打包成「输入口令才能看」的页面 out/locked/<名>.html。
仅在使用免费静态托管（无服务器、无法做登录）时用：给公开链接加访问口令。本地单文件默认不加密，直接发。

用法：
  python3 scripts/build_locked.py --project <dir> --page people.html [--page wrapped-2023.html ...]
                                  [--title 需要口令] [--hint 提示语] [--iterations 600000]
口令：从环境变量 CHRONICLE_LOCK_PASS 读；没有就在终端里输入两遍（不回显）。口令不写进任何文件、不打印。

做法：页面整页用 AES-256-GCM 加密，加密用的 key 由口令经 PBKDF2-HMAC-SHA256（缺省 60 万次，最少 20 万次）派生；
浏览器端用 WebCrypto 还原后 document.write 出原页面。需要 `cryptography` 包（pip install cryptography）。
打开要 WebCrypto：直接打开本地文件或 https 地址都行；纯 http 地址和个别 App 内置浏览器打不开。

安全边界：防的是「公开链接被转出去后，不知道口令的人随手点开」；不防有人拿到文件后离线暴力猜口令——
口令要长（建议 ≥12 位、别用群名/生日/手机号这类群友都猜得到的词）。口令一旦发进群里，就等于公开给了能看到这条消息的所有人。
页面标题和提示语是明文，别写敏感内容。详见 references/11-share-hosting.md。
隐私闸门：加密前先过 privacy_gate.enforce('site')（已生成的公开页面及其输入），并把 --page 的每个页面、标题和提示语
按重点类规则扫一遍（已删除素材、敏感词、引用 personas/），列出疑似问题供你过目；默认不拦，严格模式下才拦。
"""
import base64
import getpass
import json
import os
import secrets
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args  # noqa: E402
from pagekit import TEMPLATES, esc, fill  # noqa: E402
from privacy_gate import enforce, review_note  # noqa: E402

MIN_ITER = 200_000


def password():
    pw = os.environ.get('CHRONICLE_LOCK_PASS')
    if not pw:
        if not sys.stdin.isatty():
            sys.exit('没有口令：设置环境变量 CHRONICLE_LOCK_PASS，或在终端里交互运行')
        pw = getpass.getpass('口令：')
        if getpass.getpass('再输一遍：') != pw:
            sys.exit('两次口令不一致')
    pw = unicodedata.normalize('NFC', pw)  # 浏览器端同样 normalize('NFC')
    if len(pw) < 8:
        sys.exit('口令太短（至少 8 位；建议 12 位以上）')
    if len(pw) < 12:
        print('提示：口令不到 12 位，拿到文件的人可以离线猜，建议更长')
    return pw


def main():
    def extra(p):
        p.add_argument('--page', nargs='+', required=True, help='out/ 下的页面文件名（或任意 html 路径）')
        p.add_argument('--title', default='需要口令', help='口令页标题（明文，别写敏感内容）')
        p.add_argument('--hint', default='这一页只给群友看。口令问群主要。', help='口令页提示语（明文）')
        p.add_argument('--iterations', type=int, default=600_000, help=f'PBKDF2 次数，默认 600000，最少 {MIN_ITER}')
    a = args(__doc__, extra)
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError:
        sys.exit('需要 cryptography 包：pip install cryptography（本脚本不自己实现加密算法）')
    if a.iterations < MIN_ITER:
        sys.exit(f'--iterations 至少 {MIN_ITER}')
    out_dir = a.project / 'out'
    srcs = []
    for p in a.page:
        f = out_dir / p if (out_dir / p).is_file() else Path(p).expanduser()
        if not f.exists():
            sys.exit(f'找不到 {f}')
        srcs.append(f)
    enforce(a.project, a.cfg, 'site', texts=[('口令页标题', a.title), ('口令页提示语', a.hint)], pages=srcs)
    review_note(a.project)
    pw = password().encode('utf-8')
    tpl = (TEMPLATES / 'locked.html').read_text(encoding='utf-8')
    (out_dir / 'locked').mkdir(parents=True, exist_ok=True)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    for f in srcs:
        salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)  # 每个文件各自的盐和 IV
        key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=a.iterations).derive(pw)
        ct = AESGCM(key).encrypt(iv, f.read_bytes(), None)
        blob = json.dumps({'v': 1, 'it': a.iterations, 'salt': b64(salt), 'iv': b64(iv), 'ct': b64(ct)})
        dst = out_dir / 'locked' / f.name
        dst.write_text(fill(tpl, {'TITLE': esc(a.title), 'HINT': esc(a.hint), 'DATA': blob}), encoding='utf-8')
        print(f'{f.name} → {dst}（{dst.stat().st_size // 1024} KB，PBKDF2 {a.iterations:,} 次）')
    print('提醒：口令另走渠道告诉对方，别和文件发在同一处；页面里指向其他栏目的链接会指向 locked/ 下的同名文件，要一起加密才不断链。')


if __name__ == '__main__':
    main()
