# Ordinary-movement source check — resolved for an initial screen

The Google Storage ZIP referenced by TensorFlow Datasets returned HTTP 403.
The publisher's own page also provides individual videos. Its TLS failure was
resolved by supplying the missing InCommon intermediate, after OpenSSL verified
the certificate chain and hostname against the existing system root certificates.
No access control or TLS verification was disabled.

Twelve preselected UCF101 recordings were downloaded privately: groups 1–3,
clip 1 of Typing, BrushingTeeth, ApplyEyeMakeup and ShavingBeard. Three sampled
frames per clip were reviewed before inference. This is not exhaustive annotation
or verified unique-person coverage. Raw media is not published or used to train.

The frozen 17-label candidate made zero suggestions on these 12 whole clips.
Nine clips had usable tracking; each action had at least one usable clip. This
passes the limited whole-clip screen, not rolling-window, camera-path or broad
everyday-movement validation. See [results](../ordinary-actions/evaluation.json).

Sources:
- https://www.crcv.ucf.edu/THUMOS14/download.html
- https://www.crcv.ucf.edu/data/UCF101.php
- https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/video/ucf101.py

Private provenance, original files, content-review notes and certificate material
are in `/opt/handspeak-training/ordinary-movement-ucf101`.
