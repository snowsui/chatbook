> Purpose: write a nonfiction profile of one group member | When: once the unified read is summarized (00 + collect_evidence) and the statistics and everyday baseline are ready; one subtask per person | Input: `{{project}}/work/people/{{person}}/evidence.md`, `{{project}}/work/stats/{{person}}.md`, the raw chunks; if present: deep-read cards (07), story profiles, metrics/turnmix/base | Output: `{{project}}/out/portraits/{{person}}.md`

# How to write a profile (required reading for the writer)

Write a **nonfiction profile** of {{person}}. The readers are everyone in the group, including {{person}} and their family.
The goal: {{person}} finishes it and says "that's me" — and feels seen and understood. Everyone else laughs, nods, and knows them a little better.

## Your material (all paths under `{{project}}/`; items marked "if present" may not exist — skip that step, do not stop)
- `work/people/{{person}}/evidence.md`: the evidence readers picked out for this person after reading every line of the chat (in time order; each item has a stable key `k=`, date, speaker, the original words, and a kind (the file uses Chinese labels): memorable moment / verbal fingerprint / how they treat others / others' view / what they care about and fear / contrast / everyday). **Read all of it.** Items under "to verify" (待核对) at the end are ones where the script found the speaker or text doesn't match — **don't use them directly**; "no-go topics" (禁区主题) is only a reminder, never write it into the text.
- If present: `work/people/{{person}}/cards/*.md`: deep-read evidence cards (only for very talkative people). Read all of them too; when you quote one, find that message's k in the raw chat.
- `work/stats/{{person}}.md`: the numbers (messages per year / hour of day, catchphrases, who they talk with most).
- If present: `work/metrics.md`, `work/turns/{{person}}.md`, `work/base/{{person}}.md` — cross-member metrics, how they speak turn by turn, and an everyday baseline of 500 random messages (use these for the "everyday self").
- Cross-reference (how others see them): the "others' view" (他评) items in evidence.md; then grep other people's `work/people/*/evidence.md` for this person's name and nicknames. When only one person is being written about, you can also use the `[bracketed]` context in their own blocks and the raw chat to find what others said to them.
- To check a quote or find its k: `work/all.json` (every message has `k`, `t`, `s`, `c`; grep the words or the date); `work/people/{{person}}/chunks/*.txt` has times but no k — use it to read the context.
- If present: `work/stories/profiles/{{person}}.md`: an earlier story profile (with no-go topics) — reference only.
- Names: use the names the group actually uses (display names / nicknames), **never the pseudonyms from the short stories**. Name mappings are in `aliases` in `chronicle.config.json` (and `work/stories/names.md` if present).
- Members of this group: {{members}}. The author is {{me}}.
- Gender (authoritative):
{{gender_table}}
- Relationships (authoritative):
{{relations}}

## Method (draw on these as needed)
1. **Show, don't tell — the New Yorker profile.** Do not label the person with adjectives. Give 3–5 true episodes and let the reader reach the conclusion. Every episode has a date, their actual words, and the choice they made at that moment.
2. **Talese: open on a scene, let others talk.** Like "Frank Sinatra Has a Cold", start with one concrete moment (a date, a time, what they said in the chat) — never "X is the kind of person who…". What other people say about them is the best indirect portrait; quote friends' lines about them.
3. **McPhee: structure first, and the telling detail.** Before writing, sketch the structure — which episodes, in what order, what each section is for — the way McPhee draws a diagram before a single sentence. Prefer one exact, telling detail over three general ones. Accuracy is non-negotiable: creative nonfiction is still nonfiction.
4. **McKee: choice under pressure.** True character shows only in choices that cost something (everyone else was joking and they turned serious; they said they weren't coming and were first to arrive at 2 a.m.). Prefer those moments. If the Skill `sw-character-conflict` is installed (three-dimensional character, characterization vs true character, contrast), you may use it; otherwise follow the points here.
5. **Forster: a round character.** Include at least one contradiction that is "surprising but convincing" — something that makes even close friends think "oh, of course".
6. **Epigraph and key line.** Before the opening, write a one-line characterization of 8–16 words — the spirit of the whole piece, like an epigraph or the line under a magazine headline. In the body, pick the person's own single most telling line as the **key line**.
7. **The obituary/tribute form — for the living.** Borrow the discipline of the good newspaper obituary and the NYT "Portraits of Grief": each person gets at least one specific, concrete, unmistakably *theirs* detail (when they post, the emoji they always use, the thing they always order); plain, warm sentences; no eulogy inflation ("an amazing person who touched everyone"). One or two "digressions" — a small habit that seems beside the point — are allowed; they make a person come alive.
8. **Arc.** Within the period the data covers (see the start and end dates in stats: write months if it covers months, years only if it covers years), what changed and what didn't — use data and events (e.g. their posting hour moved from 2 a.m. to 8 a.m.). If the span is short and no change is visible, do not force an arc. Only visible changes; do not speculate about private matters.
9. **{{author_title}}'s note.** Close with a short note from the author, headed `## {{author_title}}'s note`: warm but with a real judgement, saying what this person means to this group.

**The author's voice (fixed — do not decide this yourself)**: the author is {{me}} from the group.
- "{{author_title}}'s note" is the author speaking: always first person, "I".
- In the body, refer to the author by their group name "{{me}}" (third person, like any other member). On first mention, write "{{me}} (that's me, the {{author_title}})".
- If {{person}} is the author: replace the closing note with **"What the group says"** (assembled from friends' actual words about them over the years) + a short, restrained, self-deprecating **"{{author_title}}'s self-portrait"** (first person).

Also: **don't write only the highlights.** Evidence cards lean toward big moments; follow them blindly and the person comes out deeper and more dependable than in real life. Keep a sentence or two of their everyday self (their "private channel" topics, how they usually reply).

## Structure (Markdown)
```
# <the name the group uses most>
> <one-line characterization: 8–16 words>

<opening scene>

## <subheading 1: one of their lines, or an image>
… (3–5 sections like this, each built on one true episode or a cluster of them)

## {{author_title}}'s note
…

---
## Data card
- Messages: N (most active year: YYYY)
- Usually around: HH:00
- Catchphrases: "…" "…" "…"
- Talks most with: A, B, C
- In one line: "their representative quote" (date)
```
Length depends on how many text messages {{person}} sent (see stats): under 1,000 → 1,000–1,600 words; 1,000–5,000 → 1,600–2,300 words; more → 1,600–2,600 words. **Rather short than padded** — if material runs thin, do not stretch the piece by retelling the same joke. If they repeated a line many times, write it once and call it their signature bit; do not claim "they meant it every single time".
Every fact must be traceable to a card or the raw chat; if unsure, leave it out. Quotes may be trimmed, never reworded in meaning. Keep their spelling, capitalization and emoji in quotes as they wrote them.

**Citation tags (required)**: put a hidden tag right after every quote's closing mark, copying the `k=` from evidence.md (or the message's `k` in all.json):
- said by this person: `"original words"<!--k:A:7000123-->`
- one quote spanning consecutive messages: `<!--k:A:7000123,A:7000124-->`
- said by someone else (cross-reference, others' view): `"their words"<!--k:A:7000130@display name-->`
- not a quote (nickname, meme name, title): `"nickname"<!--k:none-->`
The build strips these tags; `verify_citations.py` checks each one (key exists, speaker matches, text matches) and lists untagged quotes.

## Never touch (violations mean a rewrite)
Health / body / illness, weight and looks, relationships / dating / being single / set-ups / exes, pregnancy / trying for a baby (including hints about "the next generation"), details about children (one warm passing mention at most), job changes / quitting / layoffs / performance reviews / anything negative about a named employer, money and specific amounts, family conflict / friction with partners, dirty jokes, politics, addresses / neighbourhoods / specific streets, other people's private matters, drunken behaviour, jokes about self-harm or suicide, long rants on divisive issues.
Do not discuss sexual orientation; a same-sex partner is family — mention naturally and move on.
Never write romantic or flirtatious undertones between any two people. Teasing is fine; making anyone the butt of the joke is not. Everyone keeps their dignity.
Extra no-go topics for this project:
{{taboo_extra}}

## Material users have cut before (avoid)
- Two people (especially of different genders, each with a partner) spending time alone together: dinner at someone's place, helping tidy someone's flat, going down to meet them — don't write it.
- Any "shipping", matchmaking, "they'd make a cute couple" — don't write it.
- Employers, job titles, probation, performance ratings, office politics — don't write it.
- Phone numbers, neighbourhood names, addresses — don't write it.
- Comforting someone: you may write *how* the person comforts others, but **do not reveal the other person's specific trouble** (family, health, work) — just "when someone was having a hard time".

## Common misreadings (cards often get these wrong; the raw chat is the authority)
- **One person, many names**: display names change; old names, names in quoted replies and nicknames all point to the same person. Normalise with `aliases`; don't treat them as two people.
- **Name collisions**: one person's nickname resembles another's real name or nickname, so cards mix them up. When unsure, read the context in the raw chat.
- **Non-people**: pets, game characters, celebrities taken for group members.
- **Group marker read as content**: the group tag after the timestamp read as part of the message.
- **Ironic forms of address misread as gender**: a woman called "bro", "dude" or "my guy", a man jokingly called "girl" or "sis", "mom"/"dad" for whoever organises things. Gender of family members also follows config, never guesses from forms of address (a card once turned someone's husband into a "wife").
- **Bracketed lines taken as the person's own**: `[someone: …]` is context.
- **Jokes taken as sincere, sarcasm read straight**: especially self-deprecation and mutual roasting. "lol", "lmao", "💀" and "I'm dead" are usually tone markers, not literal; "great, love that for me" is often a complaint.
- **Possible real names**: if a card contains someone's legal name or a partner's name, the profile uses only group names.
- If cards contradict each other, check the raw chunks.

When finished, self-check: grep for no-go keywords and real names; run `python3 "{{skill}}/scripts/verify_citations.py" --project "{{project}}" --person "{{person}}" --md "out/portraits/{{person}}.md" --strict` and clear every "problem" and "untagged" item (its report `work/review/{{person}}-citations.md` doubles as the quote-source table for the final reviewer, with context around each quote). Reply with: file path, word count, the one-line characterization, the subheading of the section you are happiest with, and any points the user needs to confirm.
