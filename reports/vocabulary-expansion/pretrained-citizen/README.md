# Pretrained ASL Citizen compatibility pilot

**Not adopted or deployed.** On one deterministic PopSign development clip per
source label, the frozen model recognized 3/50 targets, produced no wrong target
suggestions and accepted 0/7 other-sign negatives. Eleven target names had no exact
class match. This small pilot cannot establish accuracy or release readiness.

The exact input transformation matched the upstream implementation on six clip
lengths. A separate sanity check on five existing ASL Citizen training recordings
returned NAME, HOME, HAVE, WANT1 and LOVE for the corresponding project labels.
Four are exact label matches; the WANT variant was not collapsed automatically.
This supports further investigation of recording/style/geometry differences,
rather than assuming a broken checkpoint loader. It is not independent testing.

- [Pilot results and frozen protocol](pilot.json)
- [Training-source sanity check](sanity.json)
- [Official checkpoint release](https://github.com/microsoft/ASL-citizen-code/releases/tag/checkpoints_v1)
- [Official preprocessing/model code](https://github.com/microsoft/ASL-citizen-code/tree/17f0148b00ef87a5957ec103da8d10bd8eb1fa23/ST-GCN)
- [Repository MIT license](https://github.com/microsoft/ASL-citizen-code/blob/main/LICENSE)
- [Separate dataset research terms](https://www.microsoft.com/en-us/research/project/asl-citizen/dataset-license/)

Reviewed upstream source, downloaded weights and landmark caches remain private
under `/opt/handspeak-training/pretrained-asl-citizen`. No public model-distribution
permission or production suitability is claimed. Pretraining population overlap
with PopSign has not been verified.
