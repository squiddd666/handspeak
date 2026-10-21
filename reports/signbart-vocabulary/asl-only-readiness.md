# ASL-only readiness decision

Checked October 21, 2026. This review includes only American Sign Language
vocabulary from WLASL and ASL-Citizen. LSA-64 and KArSL are excluded because
they are different sign languages.

The current live 100-word model is available, and all 100 output labels occur
in the official ASL-Citizen vocabulary. Sixteen also occur in WLASL. Its
published recorded-clip result is 68.85% top-1 and 87% top-5; real-camera
accuracy remains unverified, so it stays clearly labeled experimental.

No additional SignBart word is ready. SignBart's ASL checkpoint downloads are
unavailable, exact checkpoint label maps are absent, the published source has
preprocessing and import failures, and the repository provides no reuse
license. The remaining dataset glosses are catalog entries only and must not be
shown as supported camera recognition.

Microsoft's accompanying dataset license permits noncommercial research but
prohibits distributing or publishing the data or modifications. The complete
2,731-label export therefore remains a private research artifact and must not
be copied into the public website without written permission from Microsoft.

**Deployment decision:** retain the existing separately licensed 100-label
model on the live website, add zero SignBart labels to recognition, and link to
Microsoft's official ASL-Citizen project instead of republishing its catalog.
