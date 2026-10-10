# Release readiness and focused training

No new signs are ready for deployment. Existing live vocabulary remains unchanged.

26 development-only candidates: AIRPLANE, BECAUSE, BOY, BROTHER, CALL, CHAIR, FIND, GIRL, GRANDFATHER, HAVE, HEAR, HOME, HOT, LISTEN, NIGHT, PAIN, PEN, PENCIL, RIDE, SEE, SHOES, SICK, STAY, TABLE, THIRSTY, TOMORROW.

24 training priorities: BED, BOOK, CAN, CAR, CHILD, FINE, FINISH, FISH, GIVE, GRANDMOTHER, HUNGRY, LATER, LIKE, LOOK, MAN, MILK, MORNING, NOW, READ, ROOM, SHOWER, SPEAK, STORE, YESTERDAY.

The shortlist uses reused development validation (at least 75% correct with no incoming wrong suggestions). It is not independent accuracy or a promise to release these signs. All candidates still require fresh recorded-video/OBS, ordinary-movement and integration/regression checks.

Focused retraining keeps all original development recordings, signer separation and separate rejection labels. Target classes receive twice the per-class loss weight; no rejection class is dropped. Acceptance gates stay unchanged. The target subset is explicitly development-selected and is not presented as a successful 50-word model. Production files are not modified.
