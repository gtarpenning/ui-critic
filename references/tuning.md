# Tuning

Everything the skill knows about taste is in `taste/`. There are three ways to teach it, best first.

1. **Pick with a reason.** `python3 scripts/tune.py`, then the Pick tab. One sentence of "why" teaches more than several silent picks.
2. **Answer the misses.** On the Misses tab, the judge argues against a call you made. Keep your call and say why, or admit your mind changed, which flips the decision and dates it today. Either answer sharpens the evidence.
3. **Edit the rules.** On the Rules tab, write under `## My additions`. Rebuilds keep that section and replace the rest.

## The loop

```
python3 scripts/tune.py          # Pick and Misses, about 5 minutes
python3 scripts/distill.py       # rebuild taste/taste.md, about $0.30
python3 eval/score.py            # or Re-score on the Score tab
```

Scoring judges every decision with evidence from other topics only, so a decision can't help predict itself. Results are cached against the exact set of decisions.

## Reading the score

- **Judge vs Plain Claude**: the gap is what your evidence adds. Only trust a change of more than about 15 points with fewer than 30 decisions.
- **Both orders agree**: how often the judge picks the same design when A and B swap. When it doesn't agree, it was reacting to position, not design. The skill reports these as too close to call.
- **Your own consistency**: some Pick pairs are hidden repeats with the sides swapped. The judge can't reliably beat your agreement with yourself.

Beware of tuning until the score goes up. Rewriting rules while looking at the misses raises the score on those decisions and tells you nothing about new ones. My hand-written rules scored 83% on the decisions they were written from and 31% on later ones. New picks are the only clean test.

## Adding pairs to the queue

Each line of `taste/queue.jsonl`:

```json
{"id": "settings-1", "context": "What the screen is for", "a": "queue/settings-1_a.png", "b": "queue/settings-1_b.png", "source": "where it came from"}
```

Add `"repeat_of": "<id>"` with the sides swapped to measure consistency. Variety helps: decisions from one app teach that app's conventions as much as your taste.

## Using your own taste

Replace the owner's data and rebuild:

```
rm -rf taste/img taste/queue taste/answers.jsonl taste/taste.md eval/scores.jsonl eval/misses.jsonl
: > taste/decisions.jsonl
: > taste/queue.jsonl
python3 scripts/record.py --context "..." --winner a.png --loser b.png --reason "..." --topic home   # repeat
python3 scripts/distill.py
```

Start from design choices you actually made and can explain: commit messages, review threads and design notes are good sources. Use several `--topic` values, since scoring needs other topics to learn from. Expect noise under about 15 decisions.
