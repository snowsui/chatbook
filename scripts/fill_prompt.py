"""把 prompts/ 里的子任务说明模板填好占位 → 可以直接发给子任务的说明文本（打印到屏幕，或 --out 写文件）。

用法：
  python3 scripts/fill_prompt.py --project <dir> --prompt 01 --files 2023-01_p1.txt 2023-01_p2.txt [--family-safe on]
  python3 scripts/fill_prompt.py --project <dir> --prompt 02 --months 2023-01 2023-05
  python3 scripts/fill_prompt.py --project <dir> --prompt 07 --person 张三 [--out work/prompts/07-张三-01.md]
  python3 scripts/fill_prompt.py --project <dir> --prompt 05 --story-id 01 --story-brief brief.md
  python3 scripts/fill_prompt.py --project <dir> --prompt 14 --person 张三 --round 2 [--set 键=值 ...]
  python3 scripts/fill_prompt.py --project <dir> --prompt 00 --files 2023-01_p1.txt --from-line 301   补读没读完的剩余行

--prompt 可写编号（01）、文件名（01-extract-events）或路径。
语言：--lang（缺省取 config.lang，再缺省 zh）。lang=en 时先在 prompts/en/ 里找同名模板，找不到退回中文模板并提示；
  en 模式下 {{author_title}} 缺省 Chronicler，列表的空值写 (none)，人名用 ", " 连接。
通用占位从 chronicle.config.json 自动生成：
  {{project}} 项目目录绝对路径    {{me}} 作者显示名           {{author_title}} 「X曰」的称呼（缺省 史官）
  {{gender_table}} 性别表（列表）  {{relations}} 关系（列表）  {{taboo_extra}} 额外禁区（列表，空则写「（无）」）
  {{family_safe}} on/off（--family-safe > config.family_safe > off）
  {{groups}} 群列表（label 与 key）  {{members}} 全体成员（缺省按发言量推断）  {{skill}} 本 skill 目录绝对路径
  {{people}} 要写的人（缺省 config.people，00 用；--set people=… 可覆盖）
  {{public_detail}} standard/full（config.public_detail，缺省 standard：公开事件不写具体金额/住址/证件/诊断细节）
  {{sensitive_words}} {{real_names}} 本群敏感词 / 真名（列表；任何模式下都不写进公开产出）
  {{scale_rules}} 规模规则：按 config.scale（pair / large）填 references/12 的门槛段，group（缺省）为空
  {{run_<脚本>}} 调本 skill 脚本的完整命令前缀：python3 <skill 绝对路径>/scripts/<脚本>.py --project <项目绝对路径>（shlex 引号）
  {{check_cmd}} 子任务交稿前自检事件的完整命令（check_events.py，与 pipeline check 阶段同一口径，只查分给它的分段/月份）：
    01 → --dir events part_events --only <分段>；00 → --dir cards --only <分段>；02 → --dir events --only <月份>
任务占位来自参数：{{person}} --person、{{chunk_files}} --files、{{months}} --months、{{story_id}} --story-id、
  {{story_brief}} --story-brief（文本，或文件路径则读文件内容）、{{round}} --round；其他任意占位用 --set 键=值。
填完还有没填的 {{占位}} 就报错退出，并提示该补哪个参数。
--from-line N（只用于 00）：分段前 N-1 行已经读过，在说明末尾加一段“只读第 N 行起、产出写 work/cards/<分段>-b.json
  （已有就 -c、-d…）、JSON 里加 "from": N”，不覆盖原卡片；pipeline 和 collect_evidence 会把它和原卡片接起来。
"""
import json
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import args, members, safe  # noqa: E402
from privacy_gate import real_names  # noqa: E402

PROMPTS = Path(__file__).resolve().parent.parent / 'prompts'
SCALE_RULES = {
    'zh': {
        'pair': ('**本项目规模规则（两人私聊，门槛降低）**：两个人之间一起做过的事、第一次、约定、纪念日、一句被反复提起的话都收；'
                 '单人分享只要对方回应了也收（私聊里每句话都有对象）。category 仍用四类：人生节点（在一起、见家长、搬家、换城市）、'
                 '聚会出行（约会、旅行）、群内热议（两人反复聊的话题）、名场面（专属梗、第一次说某句话）。'),
        'large': ('**本项目规模规则（大群，门槛提高）**：只收下面之一——① 同一件事 ≥4 位不同发言人参与讨论；② 高热：当天或这一段讨论的消息数'
                  '明显高于本月日均（参照文件头“本月最热的几天”）；③ 群的公共事件：群规变动、线下活动、成员的人生节点（官宣类）、群名/群主变更；'
                  '④ 核心人物（config.people）的名场面。不收：两三个人的闲聊、单人求助有一两人回复、广告与转发。'),
    },
    'en': {
        'pair': ('**Scale rule for this project (a one-to-one chat, lower bar)**: collect everything the two of them did together, firsts, '
                 'promises, anniversaries, a line that keeps coming back; a solo share counts as soon as the other person responds. '
                 'Categories stay the same four codes.'),
        'large': ('**Scale rule for this project (a large group, higher bar)**: collect only if ① at least 4 different people took part, '
                  '② it was clearly hotter than the month\'s daily average (see "hottest days" in the header), ③ it is a group-wide event '
                  '(rules, meetups, announced milestones, group name/owner changes), or ④ it is a legendary moment of a core person '
                  '(config.people). Skip two- or three-person chit-chat, single help requests with one or two replies, ads and forwards.'),
    },
}
HINT = {'person': '--person', 'chunk_files': '--files', 'months': '--months', 'story_id': '--story-id',
        'story_brief': '--story-brief', 'round': '--round', 'check_cmd': '--files 或 --months'}
SCRIPTS = Path(__file__).resolve().parent


def extra(p):
    p.add_argument('--prompt', required=True, help='模板编号 / 文件名 / 路径')
    p.add_argument('--person', help='写谁（config.people 里的显示名）')
    p.add_argument('--files', nargs='*', help='分配给子任务的分段文件名（01 用）')
    p.add_argument('--months', nargs='*', help='分配给子任务的月份（02 用）')
    p.add_argument('--story-id', help='篇目编号（05 用）')
    p.add_argument('--story-brief', help='篇目任务说明：文本，或一个文件路径（05 用）')
    p.add_argument('--round', help='第几轮（14、15 用）')
    p.add_argument('--family-safe', choices=['on', 'off'], help='隐私开关（01 用），缺省取 config.family_safe')
    p.add_argument('--set', nargs='*', default=[], metavar='键=值', help='其他占位')
    p.add_argument('--out', help='写到文件（相对项目目录或绝对路径）；不写就打印')
    p.add_argument('--lang', choices=['zh', 'en'], help='模板语言，缺省取 config.lang（再缺省 zh）')
    p.add_argument('--from-line', type=int, help='补读：只读分段第 N 行起（00 用，--files 只能给一个）')


def find_prompt(x, lang='zh'):
    p = Path(x).expanduser()
    if p.is_file():
        return p
    for d in ([PROMPTS / lang] if lang != 'zh' else []) + [PROMPTS]:
        hits = [d / f'{x}.md'] if (d / f'{x}.md').is_file() else sorted(d.glob(f'{x}*.md'))
        if len(hits) == 1:
            if lang != 'zh' and d == PROMPTS:
                print(f'提示：prompts/{lang}/ 里没有 {x!r}，用中文模板 {hits[0].name}（子任务请用 {lang} 写产出）', file=sys.stderr)
            return hits[0]
        if len(hits) > 1:
            sys.exit(f'模板 {x!r} 在 {d.name}/ 下不唯一，候选：{"、".join(f.stem for f in hits)}（写更长的文件名前缀，如 '
                     f'{"、".join(f.stem.split("-")[0] if f.stem.split("-")[0] != x else "-".join(f.stem.split("-")[:2]) for f in hits)}）')
    sys.exit(f'找不到模板 {x!r}（prompts/ 下有：{"、".join(f.stem for f in sorted(PROMPTS.glob("*.md")))}）')


def bullets(items, empty='（无）'):
    items = [str(x) for x in items or [] if str(x).strip()]
    return '\n'.join(f'- {x}' for x in items) if items else f'- {empty}'


def from_line_note(a, no, en):
    """补读说明：只读第 N 行起，产出写到不覆盖原卡片的 -b/-c… 卡片。"""
    if no != '00' or not a.files or len(a.files) != 1:
        sys.exit('--from-line 只用于 --prompt 00，且 --files 只给一个分段')
    stem = Path(a.files[0]).stem
    cards = a.work / 'cards'
    suffix = next(c for c in 'bcdefghijklmnopqrstuvwxyz' if not (cards / f'{stem}-{c}.json').exists())
    out = f'{a.project}/work/cards/{stem}-{suffix}.json'
    if en:
        return (f'\n\n## Continuation\n\nLines 1–{a.from_line - 1} of {a.files[0]} were already read by another task. '
                f'Read from line {a.from_line} to the end only. Write the card to `{out}` (do NOT overwrite `{stem}.json`), '
                f'with `"chunk": "{stem}"` and an extra field `"from": {a.from_line}`; `lines` is still the whole file.\n')
    return (f'\n\n## 补读说明\n\n{a.files[0]} 的第 1–{a.from_line - 1} 行已经由别的子任务读过，**这次只读第 {a.from_line} 行到最后一行**。'
            f'卡片写到 `{out}`（不要覆盖 `{stem}.json`），`chunk` 仍写 `{stem}`，另加一个字段 `"from": {a.from_line}`；'
            '`lines` 仍是整个文件的行数，`read_to` 写你实际读到的最后一行。\n')


def main():
    a = args(__doc__, extra)
    cfg = a.cfg
    lang = a.lang or cfg.get('lang') or 'zh'
    en = lang == 'en'
    tpl_path = find_prompt(a.prompt, lang)
    tpl = tpl_path.read_text(encoding='utf-8')
    no = re.match(r'\d+', tpl_path.name).group(0) if re.match(r'\d+', tpl_path.name) else ''
    allm = json.loads((a.work / 'all.json').read_text(encoding='utf-8')) if (a.work / 'all.json').exists() else None
    fs = a.family_safe or ('on' if cfg.get('family_safe') else 'off')
    v = {
        'project': str(a.project),
        'skill': str(PROMPTS.parent),
        'me': cfg.get('me') or ('(config.me not set)' if en else '（未配置 config.me）'),
        'author_title': cfg.get('author_title') or ('Chronicler' if en else '史官'),
        'gender_table': bullets([f'{k}: {g}' if en else f'{k}：{g}' for k, g in (cfg.get('gender') or {}).items()],
                                '(not configured — do not infer gender from nicknames; if unsure, avoid pronouns)' if en
                                else '（未配置，不要从称呼推断性别，拿不准就不写代词）'),
        'relations': bullets(cfg.get('relations'), '(not configured)' if en else '（未配置）'),
        'taboo_extra': bullets(cfg.get('taboo_extra'), '(none)' if en else '（无）'),
        'family_safe': fs,
        'groups': bullets([f'{g["label"]} (key {g["key"]})' if en else f'{g["label"]}（key {g["key"]}）' for g in cfg.get('groups') or []],
                          '(none)' if en else '（无）'),
        'members': (', ' if en else '、').join(members(cfg, allm)) if (cfg.get('members') or allm) else ('(not configured)' if en else '（未配置）'),
        'people': (', ' if en else '、').join(cfg.get('people') or []) or ('(not configured)' if en else '（未配置）'),
        'public_detail': 'full' if cfg.get('public_detail') == 'full' else 'standard',
        'sensitive_words': bullets(cfg.get('sensitive_words'), '(none)' if en else '（无）'),
        'real_names': bullets(real_names(cfg), '(none)' if en else '（无）'),
        'scale_rules': SCALE_RULES['en' if en else 'zh'].get(cfg.get('scale') or 'group', ''),
    }
    sep = ', ' if en else '、'
    if a.person:
        known = set(cfg.get('people') or []) | set(cfg.get('core') or []) | set(cfg.get('deep_read') or []) | {cfg.get('me')}
        if cfg.get('members') or allm:
            known |= set(members(cfg, allm))
        if a.person not in known:
            sys.exit(f'没有 {a.person!r} 这个人：--person 写 config.people 里的显示名（{"、".join(cfg.get("people") or []) or "config.people 为空"}）')
        if a.person not in (cfg.get('people') or []):
            print(f'提示：{a.person} 不在 config.people 里', file=sys.stderr)
        if safe(a.person) != a.person:
            print(f'提示：{a.person} 的目录名是 {safe(a.person)}，模板里的路径请按目录名找', file=sys.stderr)
        v['person'] = a.person
    if a.files:
        v['chunk_files'] = sep.join(a.files)
    if a.months:
        v['months'] = sep.join(a.months)
    if a.story_id:
        v['story_id'] = a.story_id
    if a.story_brief:
        bp = Path(a.story_brief).expanduser()
        if not bp.is_absolute():
            bp = a.project / bp if (a.project / bp).is_file() else bp
        v['story_brief'] = bp.read_text(encoding='utf-8').strip() if bp.is_file() else a.story_brief
    if a.round:
        v['round'] = a.round
    q = shlex.quote
    run = lambda name: f'python3 {q(str(SCRIPTS / (name + ".py")))} --project {q(str(a.project))}'  # noqa: E731
    if a.files or a.months:
        only = [Path(f).stem for f in a.files] if a.files else list(a.months)
        dirs = {'00': 'cards', '02': 'events'}.get(no, 'events part_events')
        v['check_cmd'] = f'{run("check_events")} --dir {dirs} --only {" ".join(q(x) for x in only)}'
    for kv in a.set:
        if '=' not in kv:
            sys.exit(f'--set 要写成 键=值：{kv!r}')
        k, val = kv.split('=', 1)
        v[k.strip()] = val
    def sub(m):
        k = m.group(1)
        if k in v:
            return v[k]
        if k.startswith('run_') and (SCRIPTS / (k[4:] + '.py')).is_file():
            return run(k[4:])
        return m.group(0)
    out = re.sub(r'\{\{(\w+)\}\}', sub, tpl)
    if a.from_line:
        out += from_line_note(a, no, en)
    left = sorted(set(re.findall(r'\{\{(\w+)\}\}', out)))
    if left:
        sys.exit(f'{tpl_path.name} 还有占位没填：' + '、'.join(f'{{{{{k}}}}}（{HINT.get(k, "--set " + k + "=…")}）' for k in left))
    if a.out:
        op = Path(a.out).expanduser()
        if not op.is_absolute():
            op = a.project / op
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(out, encoding='utf-8')
        print(f'{tpl_path.name} → {op}（{len(out)} 字）', file=sys.stderr)
    else:
        sys.stdout.write(out)


if __name__ == '__main__':
    main()
