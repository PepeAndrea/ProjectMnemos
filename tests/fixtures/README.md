# Safe replay fixture

`scenario.json` is authored synthetic data, contains no real people, biometrics or recorded
private conversations. WAV and PPM bytes are generated deterministically by the harness into
runtime/datasets/synthetic. The signal is a test tone, not speech. These validate clock,
contracts, privacy and event replay; they cannot establish detector/ASR/identity accuracy.
