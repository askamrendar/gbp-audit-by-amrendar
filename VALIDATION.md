# Validation

Tested on macOS, Python 3.14 and Chrome for Testing. Windows/Linux setup is documented but not live-tested.

- 55 automated tests passed, covering identity/URL handling, unknown states, registry integrity, bulk validation, coordinate pairs, runner authorization/origin/consent, job-to-download flow, path isolation and editable seven-slide single-store and combined portfolio report generation.
- Desktop and mobile browser interface tested for pairing, mode switching, horizontal overflow and script errors.
- Live pilot collected one target and three keyword-selected comparison profiles, including displayed categories and public linked-site evidence. Physical customer origin was unverified.
- Gallery exposed one item for three profiles and no usable entry for another. This is partial sampling, not complete media coverage. The attempted Reviews-tab method exposed no review sample; review reply rates remain unresolved.
- All seven v1.2 report slides rendered. Form tables were revised after detecting overflow. Slide summaries may abbreviate values; supporting JSON/CSV preserve detailed findings.
- Mocked HTTP jobs test transfer/download behavior, not live Google accuracy.

Local pilot evidence, client screenshots and browser profiles are excluded from the public repository. Client reports require visual/editorial review. Automatic semantic image classification, private owner checks and controlled geographic ranks have not been implemented or validated.

Version 1.1: live CID-only pilot automatically resolved the exact same business CID to pin 28.5288008,77.2189987 and used it for the requested keyword search, then collected three comparison profiles and generated the report. No manual coordinates supplied. Desktop/mobile UI and one-click submission/report-ready/PPT-download flow passed using a mocked job and the real generated PPT. Short-link host handling and search normalization are covered by unit tests; not every short-link provider was live-tested.

Version 1.2: native tables, seven-slide single-store format and rank-ordered bulk portfolio layout tested; displayed photo totals remain separate from sampled gallery counts. Conflict comparison, rank censoring and incompatible keyword grouping have automated coverage. Local logo validation/storage has automated coverage. Desktop/mobile one-click submission, branding/logo payload and real PPT download passed with a mocked collection job. The report was rendered using existing pilot evidence; this update does not represent a fresh live audit or validation of every Google UI variant.

Interface fix 1.2.1: reproduced the disabled audit state on the open public page with no listening local runner, empty pairing code and unchecked consent. Browser checks verified missing-code guidance, rejected-code error, a real local connection, consent gating, single-store required-field validation and bulk-file validation. The upload limit now matches the enforced 3.5 MB file limit; combined encoded payloads are checked against the 5 MB runner limit. No fresh Google audit was performed for this interface fix.
