# Changelog

All notable user-visible changes. Versions follow MAJOR.MINOR.PATCH; the HTTP
API is versioned independently.

## Unreleased

### Added

- Dictate a hive inspection by voice, in French or in English, with no network:
  the recording is stored safely on the phone, with a confirmation, and sent
  when a connection returns.
- Each dictation becomes an inspection record: hive, date, queen seen, brood,
  stores, temperament, treatments and actions to do. Anything you did not
  mention is marked "not mentioned"; anything unclear is marked "needs
  checking" — never guessed.
- Every field shows the words it was heard as, and you can play back that
  passage of the recording.
- Review at your own pace: correct any field with one tap, confirm the record
  when you are ready. Your corrections are never overwritten.
- Create a hive by giving it a name you can say, including from a record that
  names a hive you have not created yet.
- Import an existing audio file (voice memo, handheld recorder) to get the same
  record as a live dictation.
- See which recordings are waiting and which failed, and retry a failed one
  without dictating again.
- Change a record's language and have it re-processed, keeping the fields you
  already confirmed.
- Audio is kept for 12 months by default, adjustable in Settings; delete any
  recording's audio immediately; get a warning before audio expires.
- Choose, per recording, whether it may be used to improve Melliscribe.
- The whole app, including every message, is available in French and English.
- `melliscribe` command line for maintainers: `transcribe`, `extract`,
  `pipeline`, `vocabulary`, `eval`, `retention`, `trace`, `worker`, `openapi`.
