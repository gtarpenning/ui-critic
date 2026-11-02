Context: {context}

Above are this product owner's past choices between designs. The image after them is a new screen, {w}x{h} pixels.

Critique it the way they would. Work in this order:
1. What is the one thing a person came to this screen for? What must they grasp at a glance?
2. Go through the screen element by element and ask: does this earn its place here, or could it be one tap away? Is anything said twice? Is the same kind of thing drawn two different ways, here or compared with the rest of the app? Is there a second action competing with the main one? Would a picture be understood faster than the words here?
3. Keep the changes they would actually make. Leave out accessibility boilerplate, generic polish and anything you couldn't point to. Say nothing rather than pad: fewer findings is fine.

Reply with only JSON: {"verdict": "...", "findings": [{"box": [x1,y1,x2,y2], "severity": "high|medium|low", "title": "...", "why": "...", "fix": "..."}]}. At most 3 findings, most important first. Boxes are tight, absolute pixel coordinates of the element to change.
