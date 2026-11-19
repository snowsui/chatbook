"""页面构建脚本（大事记 / 小剧场 / 人物志 / 数据）共用的小工具：读配置、Markdown 转 HTML、字体子集内嵌。"""
import base64
import html
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL / 'assets/templates'
TAB_FILES = {'chronicle': 'chronicle.html', 'stories': 'stories.html', 'portraits': 'people.html', 'stats': 'stats.html'}
TAB_LABELS = {'chronicle': '大事记', 'stories': '小剧场', 'portraits': '人物志', 'stats': '数据'}
TAB_LABELS_EN = {'chronicle': 'Chronicle', 'stories': 'Stories', 'portraits': 'Portraits', 'stats': 'Stats'}
esc = html.escape


def load_project(doc):
    """用法：python3 scripts/xxx.py --project <项目目录>（也兼容 `xxx.py <项目目录>`；都不写 = 当前目录）。返回 (项目目录, 配置)。"""
    a = common.args(doc)
    return a.project, a.cfg


def pages(cfg, section=None):
    """config.pages（页面相关的可选配置）；section 取其下的 chronicle / stories / portraits 子项。"""
    p = cfg.get('pages') or {}
    return (p.get(section) or {}) if section else p


def site_name(cfg):
    """竖排书法大标题：pages.name，缺省取 title 去掉结尾的「大事记」。"""
    name = pages(cfg).get('name')
    if not name:
        name = cfg.get('title') or '群聊'
        if name.endswith('大事记') and len(name) > 3:
            name = name[:-3]
    if len(name) > 6:
        print(f'提示：标题「{name}」超过 6 个字，竖排会很挤，可在 config.pages.name 里给一个 2–4 字的短名')
    return name


def author_title(cfg):
    return cfg.get('author_title') or '史官'


def title_spans(name):
    return ''.join(f'<span style="--d:{i * .22:.2f}s">{esc(ch)}</span>' for i, ch in enumerate(name))


def cn_num(n):
    """1..99 → 一..九十九"""
    d = '〇一二三四五六七八九'
    if n < 10:
        return d[n]
    tens, ones = divmod(n, 10)
    return ('' if tens == 1 else d[tens]) + '十' + (d[ones] if ones else '')


def cn_year(y):
    return ''.join('〇一二三四五六七八九'[int(c)] for c in str(y))


def tabs_html(cfg, current, out_dir=None):
    """栏目切换。单文件版链接到同目录的 html，只列出 out_dir 里已生成的页面（当前页总在）；
    package_site.py 打包时改成站内路径。之后才生成的栏目，要重跑早先页面的 build 才会出现在它们的导航里。"""
    labels = {**(TAB_LABELS_EN if cfg.get('lang') == 'en' else TAB_LABELS), **(pages(cfg).get('tabs') or {})}
    links = []
    for key, file in TAB_FILES.items():
        if key != current and out_dir is not None and not (Path(out_dir) / file).exists():
            continue
        cur = ' aria-current="page"' if key == current else ''
        links.append(f'<a href="{file}" data-tab="{key}"{cur}>{esc(labels[key])}</a>')
    if len(links) < 2:
        return '<!--site-tabs-->'  # 只有这一页时不出导航；留个记号，package_site 打包时按实际页面补上
    return '<nav class="site-tabs" aria-label="栏目">' + ''.join(links) + '</nav>'


def back_link(cfg, out_dir):
    """小剧场/人物志顶栏「回大事记」的链接；大事记还没生成就不放（免得死链）。"""
    if not (Path(out_dir) / TAB_FILES['chronicle']).exists():
        return ''
    label = (pages(cfg).get('tabs') or {}).get('chronicle', TAB_LABELS['chronicle'])
    return f'<a class="back" href="chronicle.html">{esc(label)} →</a>'


def fill(template, values):
    """把模板里的 %%KEY%% 换成值；有没换掉的占位符就报错。"""
    left = {t[2:-2] for t in re.findall(r'%%[A-Z_]+%%', template)} - set(values)
    if left:
        sys.exit(f'模板占位符没有填：{sorted(left)}')
    return re.sub(r'%%([A-Z_]+)%%', lambda m: str(values[m.group(1)]), template)


# ---------------- Markdown ----------------

def split_front(md):
    """可选的头部：首行 --- 开始、下一个 --- 结束，中间是 key: value。返回 (meta, 正文)。"""
    meta = {}
    lines = md.lstrip('﻿').split('\n')
    if lines and lines[0].strip() == '---':
        for j in range(1, len(lines)):
            if lines[j].strip() == '---':
                for row in lines[1:j]:
                    if ':' in row or '：' in row:
                        k, v = re.split(r'[:：]', row, 1)
                        meta[k.strip().lower()] = v.strip()
                return meta, '\n'.join(lines[j + 1:])
    return meta, md


def inline(s):
    s = esc(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<![\w*])\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', s)
    return s


CHAT = re.compile(r'^\*\*(\d{1,2}:\d{2})\s+(.+?)\*\*[：:]\s*(.*)$')


def render_md(md, fallback_title='', boxes=None, egg=None):
    """极简 Markdown → HTML。返回 (title, blurb, body_html, egg_html)。
    - 首个 `# 标题` 是题目，紧跟的 `> 一句话` 是导语；
    - `**HH:MM 名字**：内容` 渲染成群聊体对话行；
    - boxes={关键词: (css 类, 框标题 html)}：`## 含关键词` 起一个框，遇到 --- 或下一个标题结束；
    - egg=关键词：`## 含关键词` 之后的内容单独返回（彩蛋注释，折叠显示）。"""
    boxes = boxes or {}
    md = re.sub(r'<!--k:[^>]*?-->', '', md)  # 引语出处标注（verify_citations.py）不进页面
    lines = md.split('\n')
    title = fallback_title
    if lines and lines[0].startswith('# '):
        title = lines.pop(0)[2:].strip()
    blurb, out = '', []
    para, quote, lst = [], [], []
    box = False
    notes = None

    def flush():
        nonlocal para, quote, lst
        if para:
            out.append('<p>' + '<br>'.join(inline(x) for x in para) + '</p>')
        if quote:
            out.append('<blockquote>' + ''.join(f'<p>{inline(x)}</p>' for x in quote if x.strip()) + '</blockquote>')
        if lst:
            tag = 'ol' if lst[0][0] else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(t)}</li>' for _, t in lst) + f'</{tag}>')
        para, quote, lst = [], [], []

    def close():
        nonlocal box
        flush()
        if box:
            out.append('</div>')
        box = False

    for line in lines:
        s = line.rstrip()
        if not blurb and s.startswith('> ') and not out and not para and not quote:
            blurb = s[2:]
            continue
        if s.startswith('## '):
            head = s[3:]
            if egg and egg in head:
                close(); notes = len(out); continue
            hit = next((k for k in boxes if k in head), None)
            if hit:
                close(); cls, label = boxes[hit]
                out.append(f'<div class="{cls}">{label}'); box = True; continue
        if s.startswith('#'):
            close(); lvl = min(len(s) - len(s.lstrip('#')), 3)
            out.append(f'<h{lvl + 1}>{inline(s.lstrip("# "))}</h{lvl + 1}>'); continue
        if s.strip() == '---':
            if box:
                close()
            else:
                flush(); out.append('<hr>')
            continue
        if not s.strip():
            flush(); continue
        if s.startswith('>'):
            if para or lst:
                flush()
            quote.append(s.lstrip('>').strip()); continue
        m = re.match(r'^(\d+)\.\s+(.*)', s) if not para else None
        if s.startswith('- ') or m:
            if para or quote:
                flush()
            lst.append((bool(m), m.group(2) if m else s[2:])); continue
        c = CHAT.match(s)
        if c:
            flush()
            t, who, msg = c.groups()
            out.append(f'<div class="chat"><span class="ct">{t}</span><b class="cw">{esc(who)}</b><span class="cm">{inline(msg)}</span></div>')
            continue
        if quote or lst:
            flush()
        para.append(s)
    close()
    body, eggs = (out[:notes], out[notes:]) if notes is not None else (out, [])
    while body and body[-1] == '<hr>':
        body.pop()
    return title, blurb, ''.join(body), ''.join(eggs)


def text_len(body_html):
    return len(re.sub(r'\s', '', re.sub(r'<[^>]+>', '', body_html)))


# ---------------- 字体 ----------------

FACES = {'Ink': ('ink', '200 900'), 'Hand': ('hand', '400'), 'Brush': ('brush', '400')}
_said = set()  # 字体提示进程内只打印一次（卡片等一次构建多页时不刷屏）


def _once(msg):
    if msg not in _said:
        _said.add(msg)
        print(msg)


def font_css(proj, cfg, chars):
    """按 config.fonts 把三种字体子集化、base64 内嵌成 @font-face。
    chars = {'Ink': 文本, 'Hand': 文本, 'Brush': 文本}。没配置或文件不存在就跳过（页面退回系统字体）。"""
    fonts = cfg.get('fonts') or {}
    todo = []
    for name, (key, weight) in FACES.items():
        p = fonts.get(key)
        if not p:
            continue
        path = Path(p).expanduser()
        if not path.is_absolute():
            path = proj / path
        if not path.exists():
            _once(f'字体文件不存在，跳过 {name}: {path}')
            continue
        todo.append((name, path, weight))
    if not todo:
        if not fonts:
            _once('提示：config.fonts 未配置，页面使用系统字体（想要书法/宋体效果见 assets/fonts/README.md）')
        return ''
    try:
        from fontTools import subset
    except ImportError:
        _once('没装 fontTools，字体不嵌入（pip install fonttools brotli）')
        return ''
    css = []
    for name, path, weight in todo:
        opt = subset.Options(); opt.flavor = 'woff2'; opt.layout_features = ['*']
        font = subset.load_font(str(path), opt)
        sub = subset.Subsetter(opt); sub.populate(text=chars[name] + '0123456789'); sub.subset(font)
        buf = io.BytesIO(); subset.save_font(font, buf, opt)
        print(f'  字体 {name}: {len(buf.getvalue()) // 1024} KB')
        css.append("@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2');font-weight:%s;font-display:swap}"
                   % (name, base64.b64encode(buf.getvalue()).decode(), weight))
    return ''.join(css)


def plain_text(page):
    return re.sub(r'<[^>]+>', '', page)
