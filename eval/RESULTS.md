# Results

All on 17 real design decisions by one owner, each judged in both orders. With n=17, treat differences under about 15 points as noise. The rules and prompts were written after reading these decisions, so only new picks are a truly clean test. The owner's self-consistency hasn't been measured yet.

## Predicting the owner's choice

Leave-one-topic-out: each decision sees evidence from other topics only.

| Config | Accuracy |
|---|---|
| Plain Claude, Sonnet | 41-44% |
| Plain Claude, Opus | 50% |
| Careful general procedure, Sonnet, no taste | 17% on the first 9, 50% on the last 8 |
| Hand-written rules, Sonnet | 83% on the decisions they came from, 31% on later ones |
| **Production: rules + 4 cases, Sonnet, final prompts** | **59%, 62%** |
| Rules + 4 cases, Sonnet, earlier case selection | 68%, 68% |
| Rules + 4 cases, Opus | 71% |
| 8 cases, Opus | 74%, 68% |
| Rules + 8 cases, Opus | 71% |

The drop from 68% to about 60% came with a new case selection (matching `scripts/cases.py`) and neutral pronouns in the prompts. A rerun with the earlier selection failed, so the cause is unknown; it may be noise. Opus's edge over Sonnet is within noise too.

Compare's "both orders agreed" isn't proof of a stable verdict: on one Profile pair, Opus with 8 cases picked A and Sonnet with 4 cases picked B, each agreeing with itself across orders.

## Critique

On the rejected design, does a finding match the owner's stated reason? On the chosen design, does a finding tell them to undo it?

| Config (Sonnet) | Recall | Top finding | Reversal | Findings |
|---|---|---|---|---|
| Generic framework | 35% | 18% | 41% | 7.1 |
| Taste procedure + 4 cases | 53% | 29% | 24% | 3.0 |
| Production: + rules | 47% | 18% | 18% | 3.0 |

## Bounding boxes

60 DOM-measured elements, Sonnet, element named by its text: mean IoU 0.82, median 0.98, 85% at IoU 0.5 or better, 95% center inside. Rulers overlaid on the image didn't help. Boxes for real critique findings aren't validated against human-marked regions.

## Public data

60 UIClip pairs: plain Claude 62%, careful procedure 56%. UIClip declares no license, so its images aren't in this repo.

## Storyboards

Three Beeri flows rendered from the prototype at `fb62fcb` (B · Photo-first), 11 screens in all, critiqued by the shipped skill with Sonnet, twice. The flows were rank a beer (camera, pick, how was it, compare, done), social (Home, a friend's post, the friend's page) and own (Profile, My List, Top rated).

- **Boxes:** all 9 in the first run sat on what their finding described, checked by eye. In the rerun, the 3 boxes on new findings were checked and right; the other 6 nearly repeat the first run's coordinates.
- **Decisions this prototype predates:** the own flow flagged all three in both runs (Top rated style and "You" scores, no My List link to Top rated, Settings as a bottom row).
- **Stability:** own repeated all 3 findings; rank and social repeated their top 2 and changed the third.
- **New calls on screens with no decision behind them:** the Done screen restates friends' scores three ways, and the compare step shows names where a tile would be recognized faster.
- **Failure fixed:** in the first run the rank critic skipped most of the evidence (2 winner images, no rejected ones). `cases.py --sheet` now makes one chosen|rejected image per case, and on the rerun every critic read all four.

About $0.25 per storyboard.
