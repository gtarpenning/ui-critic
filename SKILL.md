---
name: ui-critic
description: Reviews UI screenshots, mockups and storyboards, in a named person's taste. Picks the best of several designs and draws boxes on what needs to change. Use when asked to critique or review a UI, design or screenshot, to compare or choose between designs or variants, to say which layout is better or what to change on a screen, or to tune or teach the design taste.
---

# ui-critic

Judges screens the way one specific person would, using their past decisions as evidence. Plain Claude scored 44-50% at predicting this person's real design choices, and this procedure about 60%, on decisions it had no same-topic evidence about ([results](eval/RESULTS.md)). It is a strong second opinion, not an oracle.

| Ask | Do |
|---|---|
| Which design is better? | [Compare](#compare) |
| What should change on this screen or flow? | [Critique](#critique) |
| Teach it, tune it, it got this wrong | [Tune](#tune) |
| The person just decided between designs | [Record it](#record-a-decision) |

Scripts live next to this file. Run them with `python3`; `prepare.py` and `annotate.py` need Pillow (`pip install pillow`).

## Always

- **Get the job first.** If you don't know what the screen is for and who it's for, ask once. Otherwise state your assumption.
- **Past decisions beat these rules and beat general design opinion.** Newer beats older.
- **Don't reason from "best practice" alone.** Careful general reasoning scored *below chance* on this person's decisions, because it argues for more information, labels and counts. Argue from what they actually chose.
- **Don't generalize a preference past its evidence.** "Less" on a list doesn't mean "less" everywhere. They chose a map picture over a shorter text chip, and added photos and notes to a comparison step, because those let people recognize things faster.
- **Lead with the answer.** Verdict first, then detail. Your report follows the same progressive disclosure you're judging.

## Compare

1. **Prepare.** `python3 scripts/prepare.py --out <tmp> <images...>`, then use the prepared copies. For a flow, each design is an ordered list of screens.
2. **Get evidence.** Read `taste/taste.md`. Run `python3 scripts/cases.py --context "<what this screen is for>" --k 4`.
3. **Judge twice, blind.** Spawn two sub-agents with no shared context, using the prompt in [references/judge.md](references/judge.md). One sees the designs in order X, Y labeled A, B; the other sees Y, X. Use Sonnet: Opus cost several times more and scored no better. Give each the case image paths and tell it to Read every image. Don't tell them which design you favor, who made which, or which is newer.

   More than two designs: compare the two strongest-looking pairwise, then the winner against the next. Don't ask for a ranking in one go.
4. **Decide.**
   - Both pick the same design: that's the verdict.
   - They split: say **too close to call**, give each side's best argument in a line, and name the deciding question for the person. Don't break the tie yourself.
5. **Look past the options.** If both designs share a flaw, or the loser has one idea worth keeping, propose the merged version in a sentence or two. Past winners often came from exactly this.
6. **Report.**
   ```
   **B.** <one sentence: the difference that decides it.>
   Confidence: both orders agreed (not proof: a different model or evidence can still flip it) / too close to call
   - Why: <the deciding differences, citing the past decisions they echo>
   - Worth keeping from A: <if anything>
   - Better than both: <if there is one>
   ```
   Add a boxed overlay of the winner's remaining issues only if asked.

## Critique

1. **Prepare** the screens as above, and note each one's pixel size. Coordinates only line up on the prepared copies.
2. **Get evidence.** Read `taste/taste.md` and run `cases.py --k 4`, then Read both images of every case before looking at the new screens. The scores below assume you saw them.
3. **Review**, in this order:
   - What is the one thing someone came to this screen for? What must they grasp at a glance?
   - Go element by element: does this earn its place here, or could it be one tap away? Is anything said twice? Is the same kind of thing drawn two different ways, on this screen or elsewhere in the app? Is a second action competing with the main one? Would a picture be understood faster than the words?
   - For a flow, also ask: does an opened thing look like what you tapped? Is any step a dead end?
4. **Cut.** At most 3 findings, most important first. Drop accessibility boilerplate, generic polish, and anything you can't point to. If the design is good, say so and report nothing. Padding with minor issues is a failure. Before finishing, check each finding doesn't undo a past decision.
5. **Draw.** Write `findings.json` next to the prepared screens, with boxes as tight absolute pixels `[x1, y1, x2, y2]` on the prepared copy:
   ```json
   {"verdict": "One sentence.",
    "screens": [{"path": "/abs/prepared.png", "label": "Home"}],
    "findings": [{"screen": 0, "box": [40, 120, 300, 180], "severity": "high", "title": "...", "why": "...", "fix": "..."}]}
   ```
   Run `python3 scripts/annotate.py findings.json --out <tmp>`. Read each `.annotated.png` and check that every box sits on what its finding describes. If one is off, fix the numbers and re-run. A box around a whole card is fine when the finding is about the card.
6. **Report** the verdict, the findings, and the paths to `report.html` and the annotated images.

## Record a decision

When the person picks between designs or states a preference while looking at screens, offer to record it: `python3 scripts/record.py --context "..." --winner a.png --loser b.png --reason "their words" --topic <short-slug>`. Use their words for the reason. This is how the skill improves, and one sentence of "why" is worth more than several unexplained picks.

## Tune

Start `python3 scripts/tune.py`, run it in the background, and give the person the URL. It has four tabs:

- **Pick**: choose between designs with the arrow keys. About 5 minutes.
- **Misses**: where the judge disagrees with them, and its argument. They keep their call or say the judge is right.
- **Rules**: edit `taste/taste.md`.
- **Score**: re-scores, including how consistent their own picks are.

After picks or edits, run `python3 scripts/distill.py` to rebuild `taste/taste.md` from all decisions. See [references/tuning.md](references/tuning.md) for the numbers and for using this with someone else's taste.
