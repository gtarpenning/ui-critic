# ui-critic

A Claude skill that reviews UI screenshots in one person's taste, learned from their real design decisions. It picks between designs using two blind judges and draws boxes on what should change.

Plain Claude predicted the owner's choices 41-50% of the time, and this about 60% ([results, including what failed](eval/RESULTS.md)). `taste/` holds one person's decisions from building Beeri, a beer-ranking app. [Replace it with your own](references/tuning.md#using-your-own-taste).

Tune it with `python3 scripts/tune.py`. Needs Python 3 and Pillow; the eval and `distill.py` use the `claude` CLI.

Apache-2.0. Research this draws on: UICrit, UIClip, DesignPref, PerceptUI.
