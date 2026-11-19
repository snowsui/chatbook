"""本人确认页（可选工具）：给 config.people 每人生成一个只含 TA 自己内容的静态页 out/review/<人>.html。
创作者想让被写的人先看看时用；用不用、看完怎么处理，由创作者决定，构建与发布不依赖它。

用法：python3 scripts/build_review_pages.py --project <dir> [--person 小鹿 ...]

每页三部分（有哪部分的数据就出哪部分）：
1. 小传全文（out/portraits/<人>.md）：逐段「可以公开 / 要改 / 别公开」+ 备注；
2. 人物模型第 10 节对照清单（out/personas/ 下文件名含 <人> 的 md）：逐条「对 / 不对 / 部分对」+ 备注；
3. 大事记里涉及 TA 的事件（work/stable/*.json，people 含 TA）：逐条「可以公开 / 别公开」+ 备注。
页面纯静态、无外部请求；填写进度存在本人浏览器里（localStorage）。填完点「生成确认码」得到一段 JSON，
复制发回给作者，或下载 json 文件。作者用 scripts/collect_reviews.py 汇总。

注意：确认页含人物模型内容，建议一对一私发给本人，别发到群里，也别放进 site/。
"""
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from pagekit import author_title, esc, inline, split_front  # noqa: E402
from verify_citations import STRIP  # noqa: E402  引语出处标注 <!--k:…-->


def portrait_items(path):
    """小传按空行切段；标题只作分节标签，不单独确认。"""
    if not path.exists():
        return []
    _, md = split_front(STRIP.sub('', path.read_text(encoding='utf-8')))  # 去掉引语出处标注
    items, section, buf = [], '', []

    def flush():
        text = '\n'.join(buf).strip()
        buf.clear()
        if text and text != '---':
            items.append({'id': f'p{len(items) + 1:02d}', 'kind': 'portrait', 'key': f'P:{len(items) + 1}', 'section': section, 'text': text})

    for line in md.split('\n'):
        s = line.rstrip()
        if s.startswith('#'):
            flush()
            section = s.lstrip('# ').strip()
            if s.startswith('# '):
                section = ''  # 一级标题是称呼
            continue
        if not s.strip() or s.strip() == '---':
            flush()
            continue
        buf.append(s)
    flush()
    return items


def persona_items(proj, person):
    """人物模型第 10 节对照清单的表格行；只取「判断」一栏给本人看（依据里常有别人的话）。"""
    files = sorted(p for p in (proj / 'out/personas').glob('*.md') if person in p.stem) if (proj / 'out/personas').exists() else []
    if not files:
        return [], None
    path = files[0]
    lines = STRIP.sub('', path.read_text(encoding='utf-8')).split('\n')
    start = next((i for i, l in enumerate(lines) if re.match(r'^#{1,4}\s*10(?:[.、．\s]|$)', l) or (l.startswith('#') and '对照清单' in l)), None)
    if start is None:
        return [], path
    rows = []
    for l in lines[start + 1:]:
        if re.match(r'^#{1,3}\s', l):
            break
        if l.strip().startswith('|'):
            rows.append([c.strip() for c in l.strip().strip('|').split('|')])
    if len(rows) < 2:
        return [], path
    head = rows[0]
    col = next((i for i, h in enumerate(head) if '判断' in h), 1 if len(head) > 1 else 0)
    no_col = next((i for i, h in enumerate(head) if '编号' in h or h in ('#', '序号')), None)
    items = []
    for r in rows[1:]:
        if all(set(c) <= set('-: ') for c in r) or len(r) <= col or not r[col]:
            continue
        no = r[no_col] if no_col is not None and no_col < len(r) else str(len(items) + 1)
        items.append({'id': f'c{len(items) + 1:02d}', 'kind': 'persona', 'key': f'C:{no}', 'text': r[col]})
    return items, path


def event_items(proj, cfg, person):
    me = cfg.get('me') or ''
    items = []
    for f in sorted((proj / 'work/stable').glob('*.json')):
        mo = json.loads(f.read_text(encoding='utf-8'))
        for i, e in enumerate(mo.get('events', [])):
            ppl = [me if p == 'me' else p for p in e.get('people', [])]
            if person in ppl:
                items.append({'id': f'e{len(items) + 1:03d}', 'kind': 'event', 'key': f'E:{mo["month"]}-{i}',
                              'date': e.get('date', ''), 'title': e.get('title', ''), 'text': e.get('summary', '')})
    return items


CHOICES = {'portrait': [('public', '可以公开'), ('wrong', '要改'), ('hide', '别公开')],
           'persona': [('ok', '对'), ('wrong', '不对'), ('partly', '部分对')],
           'event': [('public', '可以公开'), ('hide', '别公开')]}


def item_html(it):
    btns = ''.join(f'<button type="button" data-v="{v}" aria-pressed="false">{esc(lab)}</button>' for v, lab in CHOICES[it['kind']])
    head = f'<div class="meta">{esc(it["date"])}</div><h4>{esc(it["title"])}</h4>' if it['kind'] == 'event' else ''
    text = '<br>'.join(inline(x.lstrip('> ').strip()) for x in it['text'].split('\n'))
    return (f'<div class="item" data-id="{it["id"]}">{head}<div class="txt">{text}</div>'
            f'<div class="act"><div class="btns" role="group">{btns}</div>'
            f'<textarea rows="1" placeholder="备注（可不填）：哪里不对、该怎么写"></textarea></div></div>')


def section_html(items, kind):
    out, last = [], None
    for it in items:
        if kind == 'portrait' and it.get('section') != last:
            last = it.get('section')
            if last:
                out.append(f'<h3 class="sub">{esc(last)}</h3>')
        out.append(item_html(it))
    return ''.join(out)


CSS = """
:root{--paper:#f2e9d6;--paper-hi:#faf5ea;--ink:#1c1915;--ink-2:#4a443a;--ink-3:#8a8172;--rule:#d8cbb0;--zhu:#b5321d;--zhu-soft:rgba(181,50,29,.1);--song:#4d6a45;--huang:#b0832f;
--serif:"Songti SC","STSong","Noto Serif SC","Source Han Serif SC",serif;--hand:"Kaiti SC","STKaiti","KaiTi",var(--serif)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.9 var(--serif)}
main{max-width:760px;margin:0 auto;padding:28px 16px 120px}
header h1{font:700 26px/1.4 var(--serif);letter-spacing:.12em;margin:0 0 6px}
header .seal{display:inline-block;border:2px solid var(--zhu);color:var(--zhu);font:700 13px/1 var(--serif);letter-spacing:.3em;padding:6px 4px 6px 8px;margin-bottom:14px}
.intro{font:15px/1.9 var(--hand);color:var(--ink-2);background:var(--paper-hi);border-left:3px solid var(--zhu);padding:12px 14px;margin:14px 0 8px}
h2{font:700 20px/1.4 var(--serif);letter-spacing:.1em;border-bottom:1px solid var(--rule);padding-bottom:8px;margin:40px 0 6px}
h2 small{font:400 13px/1 var(--serif);color:var(--ink-3);letter-spacing:0;margin-left:8px}
.hint{font:14px/1.7 var(--hand);color:var(--ink-3);margin:0 0 12px}
h3.sub{font:700 16px/1.4 var(--serif);color:var(--zhu);margin:26px 0 8px}
.item{background:var(--paper-hi);border:1px solid var(--rule);border-radius:4px;padding:12px 14px;margin:10px 0}
.item[data-v]{border-left:4px solid var(--ink-3)}
.item[data-v=ok],.item[data-v=public]{border-left-color:var(--song)}
.item[data-v=wrong],.item[data-v=partly]{border-left-color:var(--huang)}
.item[data-v=hide]{border-left-color:var(--zhu)}
.item h4{margin:0 0 4px;font:700 16px/1.5 var(--serif)}
.meta{font:13px/1 var(--serif);color:var(--ink-3);margin-bottom:6px}
.txt{overflow-wrap:anywhere}
.act{margin-top:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:flex-start}
.btns{display:flex;flex-wrap:wrap;gap:6px}
button{font:700 14px/1 var(--serif);letter-spacing:.08em;color:var(--ink-2);background:transparent;border:1px solid var(--rule);border-radius:3px;padding:9px 14px;cursor:pointer;min-height:38px}
button[aria-pressed=true]{background:var(--ink);color:var(--paper-hi);border-color:var(--ink)}
.btns button[data-v=hide][aria-pressed=true]{background:var(--zhu);border-color:var(--zhu)}
textarea{flex:1 1 220px;min-width:0;width:100%;font:15px/1.6 var(--hand);color:var(--ink);background:#fff8;border:1px solid var(--rule);border-radius:3px;padding:7px 9px;resize:vertical}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--ink);color:var(--paper-hi);padding:10px 16px;display:flex;gap:10px;align-items:center;justify-content:center;flex-wrap:wrap}
.bar span{font:14px/1.4 var(--serif)}
.bar button{color:var(--paper-hi);border-color:var(--paper-hi)}
.bar button.main{background:var(--zhu);border-color:var(--zhu)}
#out{display:none;margin:30px 0}
#out.show{display:block}
#out textarea{width:100%;font:12px/1.5 ui-monospace,Menlo,monospace;min-height:180px}
#out p{font:14px/1.8 var(--hand);color:var(--ink-2)}
.empty{color:var(--ink-3);font:14px/1.8 var(--hand)}
"""

JS = r"""
(function(){
var META=JSON.parse(document.getElementById('meta').textContent);
var KEY='gcc-review:'+META.person+':'+META.page;
var state={};
try{state=JSON.parse(localStorage.getItem(KEY)||'{}')||{}}catch(e){state={}}
var items=[].slice.call(document.querySelectorAll('.item'));
function save(){try{localStorage.setItem(KEY,JSON.stringify(state))}catch(e){}count()}
function paint(el){var s=state[el.dataset.id]||{};
  if(s.v)el.setAttribute('data-v',s.v);else el.removeAttribute('data-v');
  el.querySelectorAll('.btns button').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.v===s.v?'true':'false')});}
function count(){var n=items.filter(function(el){return (state[el.dataset.id]||{}).v}).length;
  document.getElementById('cnt').textContent='已选 '+n+' / '+items.length;}
items.forEach(function(el){
  var id=el.dataset.id,ta=el.querySelector('textarea');
  if(state[id]&&state[id].note)ta.value=state[id].note;
  el.querySelectorAll('.btns button').forEach(function(b){b.addEventListener('click',function(){
    var s=state[id]||(state[id]={});s.v=(s.v===b.dataset.v)?'':b.dataset.v;paint(el);save();});});
  ta.addEventListener('input',function(){(state[id]||(state[id]={})).note=ta.value;save();});
  paint(el);});
var gn=document.getElementById('general');
if(state._general)gn.value=state._general;
gn.addEventListener('input',function(){state._general=gn.value;save();});
count();
function build(){
  var out=[];
  items.forEach(function(el){var it=META.items[el.dataset.id],s=state[el.dataset.id]||{};
    var row={id:el.dataset.id,kind:it.kind,key:it.key,v:s.v||''};
    if(s.note)row.note=s.note;
    if(row.v&&row.v!=='ok'&&row.v!=='public'||s.note){row.text=it.text;if(it.title)row.title=it.title;}
    out.push(row);});
  return {schema:'gcc-review/1',project:META.project,person:META.person,page:META.page,
    generated:new Date().toISOString(),answered:out.filter(function(r){return r.v}).length,total:out.length,
    general:state._general||'',items:out};}
document.getElementById('gen').addEventListener('click',function(){
  var box=document.getElementById('out'),ta=document.getElementById('code');
  var data=build();
  if(data.answered<data.total&&!confirm('还有 '+(data.total-data.answered)+' 条没选。继续生成？'))return;
  ta.value=JSON.stringify(data);box.className='show';box.scrollIntoView({behavior:'smooth'});});
document.getElementById('copy').addEventListener('click',function(){
  var ta=document.getElementById('code');ta.focus();ta.select();
  var done=function(){document.getElementById('copy').textContent='已复制';};
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(ta.value).then(done,function(){document.execCommand('copy');done();});}
  else{document.execCommand('copy');done();}});
document.getElementById('dl').addEventListener('click',function(){
  var ta=document.getElementById('code');
  var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([ta.value],{type:'application/json'}));
  a.download='review-'+META.person+'.json';document.body.appendChild(a);a.click();
  setTimeout(function(){URL.revokeObjectURL(a.href);a.remove();},500);});
})();
"""


def items_hash(items):
    meta_items = {it['id']: {k: it[k] for k in ('kind', 'key', 'text', 'title') if k in it} for it in items}
    return hashlib.sha1(json.dumps(meta_items, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:10]


def build_page(cfg, person, portrait, persona, events):
    author = author_title(cfg)
    title = cfg.get('title') or '群聊年鉴'
    all_items = portrait + persona + events
    meta_items = {it['id']: {k: it[k] for k in ('kind', 'key', 'text', 'title') if k in it} for it in all_items}
    # page：整页内容的指纹，collect_reviews 用它提示“对方看的是旧版页面”
    meta = {'project': title, 'person': person, 'page': items_hash(all_items), 'items': meta_items}
    secs = []
    if portrait:
        secs.append(f'<h2>一、你的小传<small>{len(portrait)} 段</small></h2>'
                    '<p class="hint">逐段看：写得对、愿意给群友看，点「可以公开」；事实不对、语气不像你，点「要改」并写一句哪里不对；'
                    '内容没错但你不想让别人看到，点「别公开」。拿不准的可以不选，在备注里说说。</p>'
                    + section_html(portrait, 'portrait'))
    if persona:
        secs.append(f'<h2>二、{esc(author)}对你的几条判断<small>{len(persona)} 条</small></h2>'
                    '<p class="hint">这是从聊天记录里推出来的判断，只给你一个人看，不会公开。'
                    '对不对你最清楚：对 / 不对 / 部分对，愿意的话在备注里写写真实的你。</p>'
                    + section_html(persona, 'persona'))
    if events:
        secs.append(f'<h2>三、大事记里和你有关的事<small>{len(events)} 件</small></h2>'
                    '<p class="hint">这些事准备放进大事记（只给群友看）。愿意公开的点「可以公开」，不想公开的点「别公开」。</p>'
                    + section_html(events, 'event'))
    if not secs:
        secs.append('<p class="empty">暂时没有需要你确认的内容。</p>')
    data = json.dumps(meta, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>{esc(person)} · 本人确认</title>
<style>{CSS}</style></head><body><main>
<header><div class="seal">本人确认</div><h1>{esc(person)}，请你过目</h1>
<div class="intro">{esc(author)}在做《{esc(title)}》。下面是写到你的部分，只发给你一个人。<br>
每条点一下你的意见，写错的地方在备注里告诉我；全部看完，点最下面的「生成确认码」，把那一串字复制发回给我（或下载成文件发我）。
没看完也没关系，进度会留在这个浏览器里。</div></header>
{''.join(secs)}
<h2>还有什么想说的</h2>
<textarea id="general" rows="3" placeholder="整体感受、不想被写的事、想补充的事……"></textarea>
<section id="out"><h2>确认码</h2><p>把下面这一整段复制发回给{esc(author)}（微信里直接粘贴就行），或者点「下载文件」把 json 文件发过去。</p>
<textarea id="code" readonly></textarea>
<div class="btns"><button type="button" id="copy">复制</button><button type="button" id="dl">下载文件</button></div></section>
</main>
<div class="bar"><span id="cnt"></span><button type="button" class="main" id="gen">生成确认码</button></div>
<script type="application/json" id="meta">{data}</script>
<script>{JS}</script>
</body></html>'''


def main():
    a = common.args(__doc__, lambda p: p.add_argument('--person', nargs='+', help='只生成这几个人（默认 config.people 全部）'))
    proj, cfg = a.project, a.cfg
    out = proj / 'out/review'
    out.mkdir(parents=True, exist_ok=True)
    for person in common.people(cfg, a.person):
        portrait = portrait_items(proj / 'out/portraits' / f'{person}.md')
        persona, ppath = persona_items(proj, person)
        events = event_items(proj, cfg, person)
        f = out / f'{common.safe(person)}.html'
        f.write_text(build_page(cfg, person, portrait, persona, events), encoding='utf-8')
        note = '' if ppath else '（没找到人物模型，跳过对照清单）'
        if ppath and not persona:
            note = f'（{ppath.name} 里没找到第 10 节对照清单表格）'
        print(f'{person}：小传 {len(portrait)} 段、对照清单 {len(persona)} 条、事件 {len(events)} 件{note} → {f}')
    print(f'生成于 {datetime.datetime.now():%Y-%m-%d %H:%M}。确认页含人物模型内容：建议一对一私发本人，别发群、别放进 site/。')


if __name__ == '__main__':
    main()
