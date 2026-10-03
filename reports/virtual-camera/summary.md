# Virtual-camera diagnostic — 3 October 2026

Real-time Chromium CPU MediaPipe through the live camera/automatic segmentation path using canvas captureStream(30). Face tracking off, default and seven-extra-word preview enabled. No threshold or model changes. Existing public lesson clips, not held-out accuracy data.

| Input | WATER | PLEASE | FINISH |
|---|---|---|---|
| Landscape 1280×720 | Miss | Match | Miss |
| Landscape horizontally flipped | Miss | Match | Miss |
| Portrait 480×640 | Match | Match | Miss |
| Portrait, FINISH slowed to 0.35× | Match | Match | Match |

One run per condition. Timing/detector output is in adjacent JSON files. These runs do not isolate every cause, but do not support display mirroring as the source of missed matches. Resizing and slower FINISH improved this diagnostic. The new Mirror preview setting updates webcam and overlay CSS only; verified live. Fourteen existing model tests passed.
