> Purpose: independent review of one persona model (is it accurate, is it usable) | When: after the persona model (11) is written, one subtask per person; the reviewer must not be the model's author | Input: `{{project}}/out/personas/{{person}}.md`, raw chunks `work/people/{{person}}/chunks/*.txt`, `work/metrics.md`, other people's models | Output: `{{project}}/work/review/{{person}}.md` (report only; do not edit the model)

# Independent review of a persona model

You are an independent reviewer and had no part in building the model. The subject is a persona model abstracted from chat logs (structure: see `11-persona-build.md`). The user wants to know two things: **is it accurate** (against the original record) and **is it usable** (for writing fiction). **Write the report only. Do not edit the model file.**

Material: raw chunks (grouped under `## date`; `HH:MM` lines are this person's messages, `[someone: …]` is the preceding line from someone else, a group marker after the time says which group); `work/metrics.md`; other people's models in `out/personas/`. Gender and relationships follow config:
{{gender_table}}
{{relations}}

## Check 1: evidence audit (≥20 items)
Pick at least 20 claims from the model, covering: every claim marked [high] (up to 8), core motives / fears, the Misbelief, the value ranking, 3 behaviour patterns, 5 "sample lines" (check word for word), 2 relationship claims, 1 claim about change over time. Grep the raw chat for each and rate it:
- ✅ holds (enough evidence)
- ⚠️ overreach (evidence exists but can't carry this strength or generality)
- ❌ wrong (contradicts the chat, wrong speaker, wrong date, joke read as sincere, sarcasm read straight)
- ❓ insufficient evidence (can't find it)

Also count **counterexamples**: is there behaviour in the chat clearly opposite to the claim? Find the 1–2 strongest.

## Check 2: blind prediction (10 situations)
Draw 10 situations **at random** from the raw chat, by script or by hand (spread across different years, avoiding dates the model already cites). For each, take the 3–8 lines of context before the person speaks (including bracketed lines from others). **Without looking** at what the person said next, predict from the model alone: will they reply, with what attitude, roughly saying what. Then reveal the original and score: hit / partial / miss, with one sentence on "what the model missed".
(Sampling tip: read the chunk file with `python3 -c`, pick random line numbers with a fixed seed; the chosen line must be the person's own message with someone else's context before it; reveal a whole turn — consecutive messages from the same person — at a time.)
Report the hit rate and summarise the direction the model most often gets wrong (e.g. overestimates how often they comfort people, underestimates their flat "lol ok" replies). Note: with 10 items the hit rate is very noisy; the direction of the bias matters more than the score.

## Check 3: test write (usability)
Using only this model (other people's models are fine for supporting characters), write a short scene of 250–450 words: this person + 2 group members, in a new situation **not** covered in section 7 of the model (make one up: the shared flat floods, stuck at a motorway service station, someone announces they're leaving the group). Then assess:
- What worked directly (voice model? behaviour patterns? the proportions in 0.6?)
- Where you got stuck and what the model is missing (e.g. how angry they have to be before they say something harsh; no note on what they call X)
- Whether any trait, once written down, felt "not like a real person" (compared with the feel of the raw chat)

## Check 4: overall judgement
- Omissions: important sides of this person clearly present in the chat but absent from the model (read at least 300 lines of raw chat to look for them)
- Distortion: is the model overall flattering, stereotyped, too dark, or "highlights only"?
- Are the confidence labels honest?
- Templating: has group-wide boilerplate been written in as a personal trait ("tough exterior, soft heart", "shows love through actions", "says they're lazy but secretly grinding"…)?

## Output: `work/review/{{person}}.md`
```
# <person> model review
## Verdict (≤5 lines): accuracy 1–10, usability 1–10, the three biggest problems
## 1. Evidence audit (table: # | model claim (brief) | section | rating | evidence / counterexample (date + quote excerpt))
## 2. Blind prediction (table: # | date | situation | prediction | actual (quote) | hit? | what was missed) + hit rate and direction of bias
## 3. Test write (full scene + usability assessment)
## 4. Omissions and distortion
## 5. Recommended changes (by priority, down to section and sentence, marked "change / delete / add")
```
Do not write specific private facts (health, relationships, amounts of money, addresses, employers, etc.); when a quote contains them, write "[redacted]". Extra no-go topics for this project:
{{taboo_extra}}

When done, reply with: file path, the two scores, the hit rate, and the single biggest problem.
