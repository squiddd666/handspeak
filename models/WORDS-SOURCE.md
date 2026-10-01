# Pretrained word vocabulary

Source: **PopSign ASL v1.0**, game category, by Thad Starner, Sean Forbes,
Matthew So, David Martin, Rohit Sridhar, Gururaj Deshpande, Sam Sepah,
Sahir Shahryar, Khushi Bhardwaj, and collaborators (2023).

- Dataset and download guide: https://signdata.cc.gatech.edu/view/guides/downloading_popsign/index.html
- Author paper and dataset license statement: https://signdata.cc.gatech.edu/res/doc/popsign_v1_0/popsign_v1_0.pdf
- License: **Creative Commons Attribution 4.0 International** — https://creativecommons.org/licenses/by/4.0/

Changes: Selected a small subset of the original labeled video archive; extracted
MediaPipe hand coordinates, removed untracked lead-in/end frames, interpolated
short internal tracking gaps, corrected for image aspect ratio, normalized positions,
centered movements over all usable frames, selected a dominant continuous run
when it contains at least 70% of usable frames, and resampled to 20 frames.
Only coordinate templates are bundled; the original videos are not included.
This project and its evaluation are not endorsed by the dataset authors.

Included words: HELLO, THANK YOU, PLEASE, YES, NO, FINISH.
DRINK is reserved as an unsupported-word check, not a training class.

Original training, validation, and test partitions are preserved. Participant IDs
are checked for overlap. Validation selects rejection thresholds; test examples
are not used as templates. `asl-words-evaluation.json` records sample counts,
tracking exclusions, the small-subset results, and limitations. These results are
not a benchmark of continuous ASL translation or live-camera accuracy.
