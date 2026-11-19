> Purpose: revise a character model using the review, baseline, quote attribution and blind-test results (can run several rounds) | When: one round after review (12) + baseline (13); optionally another round after each blind test (15); two to three rounds in total is plenty | Input: `{{project}}/out/personas/{{person}}.md`, `work/review/{{person}}.md`, `work/base/{{person}}.md`, `work/attr/{{person}}.md`, `work/turns/{{person}}.md`, `work/turnmix.md`, `work/metrics.md`, `work/test/{{person}}-r*.md` (if any), raw chunks | Output: edit `out/personas/{{person}}.md` in place (first copy it to `{{project}}/out/personas/.v{{round}}/{{person}}.md`), and append this round's entry to section 11

# Revising a character model

This is revision round {{round}}. What past projects taught us: first drafts usually score 6–7/10 on accuracy and 35–70% in blind tests; after three rounds, chasing individual question scores is chasing noise. **Accurate beats complete; stable beats high-scoring.**

## Materials
- `work/review/{{person}}.md`: the independent review — **go through every suggestion in its section 5** (adopt / don't adopt + reason).
- `work/base/{{person}}.md`: everyday baseline on a random 500 messages (counted per message).
- `work/turns/{{person}}.md`, `work/turnmix.md`: full statistics per turn plus conditional distributions (was mentioned / question in the preceding context / ordinary reply). **When the two units disagree, the turn statistics win.**
- `work/attr/{{person}}.md`: the script's quote-attribution check. Look at each "not by this person" (非本人) entry in context: if it's something someone else said *to* them and the model uses it that way, keep it; if it was treated as their own words, fix it. "Not found" (未找到) entries are mostly truncation or paraphrase — spot-check 10 to make sure nothing was invented.
- `work/test/{{person}}-r*.md`: blind-test reports and their improvement suggestions at the end (if any).
- `work/metrics.md`, raw chunks (for checking and new examples; grep).

## Revision rules
1. **Everyday first, highlights second.** 0.5 Everyday baseline and 0.6 Turn-type distribution must exist and match the statistics; section 0 sketch, section 3 behavior patterns and section 4 voice model must agree with the baseline — any behavior with a high baseline share must have a place in the model.
2. **Turns, not single messages.** Per-message statistics split bursts and make the person look like they "only reply with a word or two". Per turn, pure reaction (纯反应) is usually around a tenth, and substantive longer turns are 30–60%. Delete or rewrite every sentence implying "mostly replies with a word or two".
3. **But don't overshoot into "always replies with a thoughtful sentence".** In the full statistics, 30–50% of everyone's turns share no word with the previous 4 messages (off-thread (跳线) / talking past each other / several threads at once), and single-message turns are 50–70%. Write everyday replies as a **proportional mix** (consistent with 0.6) and delete absolute single-rule phrasing like "by default / usually / mostly they …".
4. **People differ in *what* they say and *how*, not in *how many messages*.** Turn-type distributions differ little from person to person; the real differences are in topics (private channels), wording, catchphrases and who they address. Spend revision effort there.
5. **Threshold for deep claims.** Each core motivation / core fear / Misbelief / Need needs **≥3 mutually independent pieces of evidence, none in a joking context** (list dates); otherwise downgrade to [low] and mark "inferred", or rewrite as "no clear … is visible; on the surface …". Don't invent depth to complete the framework.
6. **Counterexamples go in.** Every [high] claim is followed by one exception / counterexample.
7. **Quotes.** Every quote must be the person's own words (or explicitly marked "X said to them"), correctly dated. New or changed quotes carry source tags: their own words `"quote"<!--k:A:7000123-->`; several consecutive messages `<!--k:A:1,A:2-->`; someone else's words `<!--k:A:7000130@speaker-->`; quotation marks around something that is not a real quote (nickname, name of a running joke) `<!--k:none-->`. The tag goes right after the closing quotation mark.
   When done, run `python3 "{{skill}}/scripts/verify_citations.py" --project "{{project}}" --person "{{person}}" --md "out/personas/{{person}}.md" --strict` and clear it to zero.
8. **Truthful but not exposing.** Record honestly how often they swear, how they gossip, how much they join dirty jokes (frequency and style only), direct comments on looks, how hard they pile on, topic-hopping / not replying / replying hours later; still no concrete private facts. Extra taboos for this project:
{{taboo_extra}}
9. **Scenario projections (section 7).** Each scenario gets **two or more possible reactions with rough probabilities** ("about half …, about a third …, occasionally …"); in at least 2 scenarios the main branch is "doesn't care much / tosses off a joke"; avoid uniform "teases first, helps later" or "tough on the outside, soft inside".
10. **Sentence templates (section 4)** ordered by frequency, one-word reaction templates last.
11. **Consistency pass.** Read the whole file and fix sentences that contradict each other across sections — prioritize "leftover contradictions" mentioned in earlier revision logs (e.g. the epigraph line, the checklist, or section 8 still stating an old conclusion).
12. **Structure stays the same** (sections 0, 0.5, 0.6, 1–11).

## Don't overfit (mandatory when handling blind-test suggestions)
- A blind-test round has only a dozen or so questions; **each question is about ±8%**, so most score movement is noise. Don't change the model for one question.
- Correcting the "default reply" item by item swings back and forth (last round predicted too short → this round too long and too earnest).
- **Only adopt suggestions consistent with the full statistics (turnmix/turns/base/metrics).** Suggestions that contradict the statistics, or rest on only 1–2 blind-test questions, are not adopted — record the reason in the revision log.
- Concentrate changes in sections the statistics or the review showed to be wrong; **leave other sections' conclusions alone**.
- Don't chase one person's score. Don't read the blind-test answer file (holdout `-a.md`) for examples — that would invalidate the next blind test.
- Later rounds can be shorter than earlier ones: accurate beats complete.

## Section 11 revision log (append this round)
- Version line: update the first line of the file to "Version N · Blind-test hit rate: vX xx% / vY xx% (N questions, ±8% per question, for reference only)" — read the scores from `work/test/`.
- This round's entry: suggestions adopted (source: review/base/attr/test), claims changed (old → new), what was deleted, suggestions not adopted and why, contradictions fixed.

When done, reply with: file path, the top five functions in 0.5 plus the one-sentence "typical turn", the private-channel list from 0.6, the revised one-line essence / core fear / Misbelief (if any), number of suggestions adopted / not adopted, number of contradictions fixed.
