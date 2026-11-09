# Fresh recognition audit intake

No new-signer audit has run. All 11 official test signers have appeared in the
previous audit, so more clips from that split are regression data, not a fresh
signer cohort.

Provide a local folder/path or upload consented new-signer recordings. Annotate
each clip with its true sign label, a pseudonymous signer ID, a unique source
ID, and whether the sign is outside the frozen 24-word candidate vocabulary.
Do not place names, contact details, or other identifying information in IDs.

The intake-template.json examples are placeholders. Consent and new-signer
declarations must be confirmed by the provider; the script does not infer consent
or identity from a face. Keep audit clips out of training and calibration.
Include several independent new signers, all target words (especially NO),
different speeds/viewpoints, and unsupported signs. Missing labels and tracking
failures will remain in the audit denominator; no best-of retries are selected.

The intake validator checks declared signer/source separation, duplicates, and
known downloaded/Watch clip hashes. This is not independent identity proof or
a guarantee that every historical private recording has a known content hash.
It writes a local metadata index only; it does not copy or upload video.
