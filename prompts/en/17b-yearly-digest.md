> Purpose: write the group's "Year in review" (500–900 words), to post around New Year | When: after the year's months (or all months so far) are frozen into stable/ | Input: `{{project}}/work/stable/{{months}}-*.json` (the year's events), `{{project}}/work/digest/{{months}}-stats.md` (yearly counts, made by `incremental.py --stats {{months}}`), `{{project}}/out/digest/{{months}}-*.md` (monthly digests, if present), `{{project}}/work/top10.json` (top ten of the year, if present) | Output: `{{project}}/out/digest/{{months}}.md`

# Year in review ({{months}})

Here `{{months}}` is a year (generate this with `fill_prompt.py --prompt 17b --months 2024`).

You are writing the group's year in review: the friend who stands up at the end-of-year dinner and walks everyone through the year — funny, with one or two moments that make the room go quiet, but not a eulogy and not an annual report.

## Material (no raw chat — same reason as the monthly digest: facts come only from the edited stable files)
- `work/stable/{{months}}-*.json`: all events of the year. Read each month's month_summary and the heat-3 events first, then the rest. Category codes: 人生节点 = milestone, 聚会出行 = meetup or trip, 群内热议 = hot topic, 名场面 = legendary moment / running joke.
- `work/digest/{{months}}-stats.md`: yearly counts (messages and events per month, most active people, list of heat-3 events). Labels are in Chinese; use the numbers.
- If present: the monthly digests `out/digest/{{months}}-*.md` (borrow phrasing, don't stitch them together) and `work/top10.json` (if it exists, it decides what matters most).
- Members: {{members}}; the author: {{me}}. Gender (authoritative):
{{gender_table}}
- Relationships (authoritative):
{{relations}}

## How to write it
- 500–900 words; a thin year gets a short piece. Short beats padded.
- Shape:
  1. **The year in one line** (under 15 words).
  2. **A few threads**: tie the year into 3–5 threads ("how many dinners we planned vs. how many happened", "a joke that ran from March to November", "someone moved away and the group carried on anyway"). Each thread rests on 2–4 events with their months. Threads must grow out of the events — don't pick a theme first and hunt for evidence.
  3. **The year in numbers**: the busiest and quietest months (explain only with events; if you can't, say "no idea why"), who talked most, who showed up in the most events, how many heat-3 events. Counts only.
  4. **One line per person** (optional, only if there are 12 members or fewer): one concrete picture of each member's year in the group. Every line different — **no repeated sentence pattern** — and no judging adjectives ("the warmest person"); write what they did.
  5. **Close**: one light, concrete line (a plan for next year, the running joke of the year).
- Voice: relaxed and specific; warm but not sentimental; everyone keeps their dignity and nobody becomes the joke.
- Quiet months are "quiet", not a "low point" or a "crisis". Don't guess at reasons.

## No-go topics (same as the chronicle and the monthly digest; be strict)
- Privacy switch `{{family_safe}}`: when on, no dating, crushes, exes, singles jokes, or work setbacks (only the good news if it ended well).
- Never: health, bodies and illness, weight and looks, pregnancy and fertility (including hints like "the next generation"), details about children, employers / job titles / performance / job-change details, specific amounts of money, family conflict, drunkenness, sexual jokes, politics and controversies, addresses, real names, romantic undertones between two people (no shipping). Skip such events entirely; don't write them in code.
- Extra no-go topics for this project:
{{taboo_extra}}

## Output
Write `{{project}}/out/digest/{{months}}.md`:
```
# {{months}}: the year in review
> <the year in one line>
<body>
```
When done, reply with: file path, word count, the one-line year, the events you used (`E:<month>-<index>`), and the events you skipped and why.
