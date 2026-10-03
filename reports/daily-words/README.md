# Daily conversation words

Requested: NAME, HOME, HAVE, WANT, LOVE.

Published functionality: a dedicated personal-practice group, verified external lessons, existing local HOME/HAVE practice videos, direct trainer selection, valid personal-example counts, and camera-practice readiness after three examples. Readiness is not a measured accuracy claim. These five labels are not a new pretrained vocabulary. Clearing personal examples removes readiness. No text is automatically inserted by the learning buttons.

## Pretrained attempt

The corrected PopSign development cache provided 21 usable HOME/HAVE training recordings. We fitted a separate two-word candidate with 120 other-sign training references and 300 deduplicated validation recordings. Source participant sets were asserted disjoint between training and validation. The selected zero-false-accept candidate rejected all eight supported validation clips; it failed the predeclared minimum recognition gate. No test recordings were used to tune thresholds, no further reserved test was run after that failure, and no candidate was deployed. See `home-have-validation.json` and `protocol.json`. Existing models and thresholds remain unchanged.

NAME and WANT were absent from the saved PopSign source labels. The advertised PopSign v2.1 LOVE training archive returned HTTP 404. Publisher previews are resampled in time and were not substituted for original-speed training recordings.

Microsoft ASL Citizen was investigated as another source. During the initial source review, only archive metadata and the included license were downloaded outside the website. Its included `use.txt` restricts use to noncommercial research and forbids redistributing the data or modifications. No ASL Citizen recordings or derived template model were downloaded or published during that initial review. A subsequent private training experiment is documented in `citizen-research.md`. The range-reader helper is retained for metadata inspection; using the full source requires respecting its license.

Sources:
- https://signdata.cc.gatech.edu/view/datasets/popsign_v2_1/index.html
- https://www.microsoft.com/en-us/research/project/asl-citizen/
- https://www.lifeprint.com/asl101/pages-signs/n/name.htm
- https://www.lifeprint.com/asl101/pages-signs/w/want.htm
- https://www.lifeprint.com/asl101/pages-signs/l/love.htm

Verification: 25 motion tests; browser checks for five entries, trainer selection, video handoff, rejecting malformed personal samples, three-example readiness, removal, and mobile width. Synthetic samples in browser checks validate UI behavior only, not signing accuracy.
