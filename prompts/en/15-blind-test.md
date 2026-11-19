> Purpose: acceptance blind test for a character model — predict what the person said in real situations using only the model, then check the answers | When: after each revision round (14); one subtask per person; the tester must not have seen the raw text | Input: `{{project}}/out/personas/{{person}}.md`, `{{project}}/work/holdout/{{person}}-q.md` (questions), `{{project}}/work/holdout/{{person}}-a.md` (answers — only in step 4) | Output: `{{project}}/work/test/{{person}}-r{{round}}.md`

# Blind test

You are the tester. Follow the steps in order. **Do not look at the answers first.**

1. Read `out/personas/{{person}}.md` (the character model). **Do not read** chunks, cards, review, base, attr or any other material.
2. Read `work/holdout/{{person}}-q.md`: a set of real situations (usually 12). Each gives the context before this person spoke; the last line is "**{{person}}**: ?" (the script may write it with a full-width colon, "：？").
3. For each situation, predict from the model alone. The unit is **one turn** (they may send several messages in a row):
   - do they reply at all;
   - intent (riff on the joke / complain / ask / organize / show care / talk about their own day / jump to another topic / ignore …);
   - tone;
   - the turn as a whole: roughly how many messages, and what each says (one-line summary).
   Where sections 0.6/7 of the model give proportions or branch probabilities, predict the most likely branch; you may add a second branch.
   Write **all** predictions into the "Predictions" section of the output file **first** and save it.
4. Only then read `work/holdout/{{person}}-a.md` (the actual replies) and score each item:
   - Hit: intent and tone both right
   - Partial: one of the two right (counts 0.5)
   - Miss
   Give one sentence on why each one deviated.
5. Compute the hit rate and summarize: where is the model still systematically biased (e.g. still overestimates caring, underestimates randomness, predicts too short / too long)? Give 3 concrete improvement suggestions, each pointing to a model section.

Why the order is so rigid: if you look at the answers and then "predict", you're testing the tester's memory, not the model.

Notes: the questions are not filtered for short replies; score on overall intent and tone, exact wording is not required. The sample is small — each question is about ±8% — so say how many questions support each suggestion.

## Output: `work/test/{{person}}-r{{round}}.md`
```
# <person> blind test (round {{round}})
## Predictions (written in step 3, not changed afterwards)
## Scoring (# | prediction summary | actual summary | hit/partial/miss | why it deviated)
## Hit rate and systematic bias
## Improvement suggestions (3, pointing to sections; note how many questions support each)
```
Privacy: don't restate specific private content in predictions or summaries.

When done, reply with: hit rate, and the main bias in one sentence.
