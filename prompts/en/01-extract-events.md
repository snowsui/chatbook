> Purpose: read chunked chat logs line by line and extract events for the group chronicle | When: first step of the chronicle; the coordinator hands the chunk files in `work/chunks/` to several parallel subtasks | Input: the chunk files assigned to you under `{{project}}/work/chunks/` (`{{chunk_files}}`), switch `{{family_safe}}` (on/off), public detail level `{{public_detail}}` | Output: one JSON per chunk, written to `{{project}}/work/part_events/` or `{{project}}/work/events/`

# Event extraction (no cap on events; read every line)

You are extracting events for a "chronicle" web page about a group of friends. Your input is a set of chunked chat files, each at most 50,000 characters.

## How to read (hard requirement)
- Read each file in order with the Read tool, 300–400 lines at a time (offset/limit). **Start at line 1 and finish at the last line. Look at every line.**
- **Do not** skim by any means: no grep, no scripts, no filtering by message length, no reading only the busy days.
  Why: the liveliest moments are usually a wall of short replies ("LMAO", "no way", "😂😂😂"). Filter by length or keyword and you will miss exactly the moment the whole group was laughing.
- Finish one file and write its result before you open the next one. Do not batch everything to the end — if you are interrupted, all of it is lost.

## Data format
The first three lines of each file: the month, which chunk this is ("第 i/n 段" = chunk i of n), message counts for the month, line counts for this chunk and the whole file, and the busiest days of the month. After that, one message per line:
`message_id|group|day hh:mm|speaker: content`
- Groups in this project (the letter prefix of a message ID is the group key; the `groups` field takes the label):
{{groups}}
  A project can have several groups (for example a small core group plus a larger group that includes partners and family). Tell them apart by label.
- `⏎` is a line break; `（回复 X: …）` is a quoted reply (X is already normalised to a display name); `[图片] [语音] [表情] [文章] title [链接] …` are placeholders for image, voice note, sticker/emoji, article, link and so on. In `[图片] caption`, the text after the placeholder is the sender's own caption.
- Speaker `me` is the author of the site (display name `{{me}}`).
- **Gender and relationships — use only this** (never infer pronouns or relationships from nicknames; keep cross-gender or kinship nicknames as they are, without comment):
{{gender_table}}
Relationships:
{{relations}}

## Hard rules (apply in every mode, before everything below)
1. **No-go topics the user named**: do not collect these, and do not mention them in any field (not even in summary form):
{{taboo_extra}}
2. **Sensitive words for this group**: never put these in a title, summary or month summary (the privacy gate will flag them at build time):
{{sensitive_words}}
3. **Real names**: use group nicknames / display names only; never write these real names:
{{real_names}}
4. **Public detail level `{{public_detail}}`**:
   - standard (default): you may collect the event, but **leave out specifics** — exact amounts ("28k", "$3,000"), addresses / neighbourhoods / unit numbers, IDs and accounts, medical details (diagnoses, test results), other people's private matters. Summarise instead: "got an offer", "went to see a doctor", "moved house".
   - full (only if the user explicitly chose it): record as it happened, amounts and health details included.

## What to collect (no cap)
**Collect anything that several people discussed, that concerns people in the group, or that is worth remembering.** Take as many as there are:
- Life milestones: dating, engagement, marriage, babies, buying/renovating/moving home, new job / promotion / quitting / graduating, exams, pets, illness or hospital stays, and so on
- Meetups and trips: dinners, games nights, sports, watching a show together, anyone organising anything
- Topics several people argued or riffed about (if multiple people go back and forth on it, it counts)
- Legendary moments and running jokes: great one-liners, absurd things that happened, jokes that keep coming back, people roasting each other
- A personal share that got several people to respond

Skip: one person talking to themselves with no reply; a bare forwarded link nobody discussed.
{{scale_rules}}

## What counts as "one event" (follow this; do not invent your own rule)
- **One event**: one activity (from making the plan, to going, to posting the photos); or one continuous discussion of a topic (gaps of no more than about 3 days). Merge it into one entry and pick refs from that stretch.
- **Separate events**: a running joke that comes back days or weeks later, an old argument that flares up again, another round of plans. Each occurrence is its own event, and the summary says so ("once again the group …", "the X joke returns"). **Do not** merge several occurrences across a month into one event with refs spanning the whole month.
- When unsure: can all the refs fit inside 3 days? If not, split it.
Why no cap: the next step (merge) only removes duplicates, it never cuts. Cutting is left to the user on the finished site. Anything missed here cannot be recovered later; anything extra can be deleted at any time.

Tone: plain, light, like an old friend keeping the group's diary. Write titles and summaries in English.

## Privacy switch `{{family_safe}}`

**off (default — only group members will read it)**: none of the tact filters below (relationships, work setbacks and gossip may be collected). The hard rules above still apply in every mode: named no-go topics, sensitive words and real names are never written, and specifics follow `{{public_detail}}`.

**on (the finished site will be read by everyone's partners and family, including periods before those partners were in the group)** — **additionally do not collect**:
1. Dating, flirting, crushes, confessions, set-ups and blind dates, exes, jokes about being single, who likes whom. These may have been everyday banter back then, but a current partner reading them would be embarrassed.
   The only exception: an engagement / marriage / wedding the person announced themselves. Collect it and keep it festive.
2. Complaints about work, bosses or colleagues; failed exams; job rejections and similar setbacks. If it ended in good news, record only the good news.

With the switch on there is still no cap; only these categories are left out.

## Output
Write one valid JSON file per chunk (no comments):
- If the header says chunk 1 of 1 ("第 1/1 段", the whole month is one chunk) → write `{{project}}/work/events/<month>.json` directly
- Otherwise → write `{{project}}/work/part_events/<chunk file name without .txt>.json`; `month_summary` describes this chunk only, and a merge task will deduplicate later

```json
{"month":"YYYY-MM","month_summary":"summary of this chunk (≤90 characters)","events":[
 {"date":"YYYY-MM-DD","title":"≤48 characters","summary":"≤240 characters: who, what happened, how the group reacted",
  "people":["display name"],"category":"人生节点|聚会出行|群内热议|名场面","heat":1,
  "refs":["A1234","B56"],"groups":["group label"]}]}
```
- `category` uses the internal codes below exactly as written (the checker validates them; the site shows English labels):

  | code | meaning |
  |---|---|
  | 人生节点 | life milestone |
  | 聚会出行 | meetup / trip |
  | 群内热议 | hot topic |
  | 名场面 | legendary moment / running joke |

- `heat`: 3 = the whole group went wild / a major life event, 2 = several people got into it, 1 = worth a line
- Length limits in English mode (what `check_events.py` enforces when `config.lang` is `"en"`): `title` ≤ 48 characters, `summary` ≤ 240 characters (about 40 words), `month_summary` ≤ 90 characters. Over the limit gets flagged.
- `refs`: the 2–6 message IDs that best represent the event. They **must exist in this file**, listed in time order.
- `date`: **equals the date of the earliest message in refs** (not earlier, not later).
- `people`: display names as used in the chat; the author is written as `{{me}}`.
- `groups`: which group(s) the event happened in.
- For what counts as one event, see "What counts as one event" above. Events that obviously cross chunk boundaries are written as usual; the merge step deduplicates them.
- **Self-check before you report** (the same script and rules as the coordinator's check stage; do not write your own checker):
  `{{check_cmd}}`
  It checks refs count and existence, date, lengths, people, refs span and pronouns vs. gender. Fix until it says 0 unresolved warnings. If you believe a warning is a legitimate exception (e.g. a span with only one message at each end), do not force a split; name the event and the reason in your reply and the coordinator decides.

When done, report one line per file: `<file name>: N events (M lines, read to end)`, where M is the total number of lines in the file. If you did not finish: `<file name>: N events (read to line X of M)`. Separate files with semicolons.
