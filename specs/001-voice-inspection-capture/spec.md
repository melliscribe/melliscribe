# Feature Specification: Voice Inspection Capture

**Feature Branch**: `001-voice-inspection-capture`

**Created**: 2026-09-21

**Status**: Draft

**Input**: User description: "As a beekeeper, I record a spoken description of a hive inspection and get a structured inspection record (hive id, date, queen seen, brood, stores, temperament, treatments, actions to do). Missing or uncertain fields are flagged rather than guessed. Recordings can be processed later, from a file."

## Clarifications

### Session 2026-09-21

- Q: When a beekeeper dictates at a hive with no signal, should they get the finished structured record there, or a safely-stored recording that becomes a record once connectivity returns? → A: B — offline capture stores the recording durably; the structured record is produced when connectivity returns.
- Q: Should fields like brood, stores and temperament be recorded as values from a fixed list, or as whatever words the beekeeper actually used? → A: C — a coded value from a controlled vocabulary per field, stored together with the verbatim phrase it was derived from.
- Q: Does this feature assume hives are already registered elsewhere, or must it let a beekeeper create one? → A: B — this feature includes minimal hive creation (identifier and nothing else); full apiary management stays out of scope.
- Q: How long should original recordings be kept after the record made from them is confirmed? → A: C — 12 months by default, beekeeper-adjustable, with delete-now always available; transcript and record outlive the audio.
- Q: Does the app already know the dictation language, or should it detect it from the recording? → A: B — a sticky account setting, applied to every recording, with a language override and re-processing available at review.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dictate an inspection at the hive (Priority: P1)

A beekeeper opens a hive, works through it, and speaks what they see —
naturally, in their own words, in French or English. They say which hive it is,
whether they saw the queen, how the brood and stores look, how the colony
behaved, anything they treated, and what they want to come back and do. Closing the
hive, they get an explicit confirmation that their words are safely stored —
that much works with the phone in a pocket and no signal at all.

Once the device has connectivity, that recording becomes a structured
inspection record: the things the system understood are filled in, and the
things it did not hear or is unsure about are visibly marked as unknown rather
than filled with a guess. The beekeeper confirms or corrects it, and the record
is theirs.

**Why this priority**: This is the entire product promise. A beekeeper who can
speak an inspection and later find a trustworthy record of it has received the
core value; nothing else in this feature matters if this does not work. It is
also the smallest slice that is genuinely usable in a real apiary — the part
that must survive the field is the capture, and it does.

**Independent Test**: Put a tester in airplane mode, have them dictate a
complete inspection out loud, confirm the app tells them the recording is
safely stored, then restore connectivity and confirm they end up with a
structured record whose filled fields match what they said and whose
unmentioned fields are marked unknown. Delivers a usable inspection log with no
other part of this feature built.

**Acceptance Scenarios**:

1. **Given** a beekeeper at a hive with no network connection, **When** they
   dictate an inspection naming the hive, the queen, brood, stores and
   temperament, **Then** the recording is stored durably on the device and the
   beekeeper is told it is safe, with no network involved at any point.
2. **Given** that stored recording, **When** the device regains connectivity,
   **Then** a structured record is produced from it with those fields
   populated, and the beekeeper is able to review it.
3. **Given** a dictation that never mentions stores, **When** the record is
   produced, **Then** the stores field is marked unknown and is not populated
   with an inferred or default value.
4. **Given** a dictation where a field was heard but ambiguously ("the brood
   looked, well, maybe patchy"), **When** the record is produced, **Then** that
   field is marked uncertain and the beekeeper is prompted to confirm it.
5. **Given** a beekeeper whose account language is French, **When** they start
   a recording, **Then** no language choice is presented, and the record is
   populated to the same standard as an equivalent English dictation, with
   identical coded values regardless of the language spoken.
6. **Given** a record produced against the wrong language setting, **When** the
   beekeeper corrects the language at review, **Then** the recording is
   re-processed and any fields they had already confirmed are kept.
7. **Given** a produced record, **When** the beekeeper corrects a field,
   **Then** their correction is kept and is never overwritten by the system's
   own interpretation of that recording.
8. **Given** a completed dictation, **When** the beekeeper reviews the record,
   **Then** they can tell at a glance which values came from the system and
   which they entered or confirmed themselves.
9. **Given** a beekeeper with no hives yet, **When** they create one by giving
   it an identifier they can say out loud, **Then** that hive exists and can be
   named in a dictation, with nothing else required of them.
10. **Given** a dictation naming a hive identifier that matches nothing known,
    **When** the beekeeper reviews the record, **Then** the hive field is
    flagged and they can either pick an existing hive or create that hive on
    the spot — and the system has created nothing on its own.
11. **Given** an identifier already used by one of the beekeeper's hives,
    **When** they try to create another hive with it, **Then** the system
    refuses and explains why, rather than accepting it and later attaching a
    record to the wrong colony.

---

### User Story 2 - Process a recording later, from a file (Priority: P2)

A beekeeper has audio that was not captured through the live flow — a voice
memo taken on a phone in a bee suit, a handheld recorder used through a whole
apiary visit, or a recording captured earlier by this app while a long backlog
was still waiting. They hand that file to the system and get the same
structured record they would have gotten live, without having to re-dictate
anything.

**Why this priority**: It decouples capture from processing. Recording is
cheap, reliable and battery-light in the field; interpretation is neither.
This is also what makes a long offline visit survivable — twenty hives recorded
in a valley with no signal, all processed on the drive home. Valuable, but only
once P1 proves the extraction itself is trustworthy.

**Independent Test**: Supply a pre-existing audio file of a dictated
inspection, with no live capture involved, and confirm it yields a structured
record equivalent to the one the live flow would produce from the same speech.

**Acceptance Scenarios**:

1. **Given** an audio file of a dictated inspection, **When** the beekeeper
   submits it for processing, **Then** a structured record is produced from it
   with the same fields, flagging and review flow as a live dictation.
2. **Given** several recordings captured offline across an apiary visit,
   **When** connectivity returns, **Then** each is processed and each produces
   its own separate record, with no recording silently skipped or merged into
   another.
3. **Given** a recording that is still waiting to be processed, **When** the
   beekeeper looks at their pending work, **Then** they can see it is queued
   and has not been lost.
4. **Given** processing fails for a recording, **When** the beekeeper checks
   it, **Then** the recording is still intact and retrievable, and the failure
   is shown rather than silently swallowed.
5. **Given** an audio file in an unsupported format or one that contains no
   intelligible speech, **When** it is submitted, **Then** the beekeeper is
   told why no record could be produced and the file is not discarded.

---

### User Story 3 - Hear what was actually said (Priority: P3)

A beekeeper looking at a record — especially at a flagged field, or at a value
that looks wrong a week later — wants to hear it, not just read it. Every field
already shows the phrase it came from, but the phrase itself can be a
mis-transcription. They open the field and play that passage of the original
recording back, in their own voice.

**Why this priority**: It is the last resort when the stored phrase is itself
wrong — the only way to distinguish "the system misunderstood me" from "I
misspoke". It makes a disputed record resolvable months later, when memory of
the inspection is gone. Real value, but the product is usable without it, since
every field already carries its originating phrase.

**Independent Test**: Take a record produced by either of the flows above,
open any populated field, and confirm the corresponding passage of the original
audio is playable and lands on the right words.

**Acceptance Scenarios**:

1. **Given** a populated field on a record, **When** the beekeeper plays it
   back, **Then** the audio starts at the passage that phrase was taken from,
   not at the beginning of the recording.
2. **Given** a field the beekeeper believes is wrong, **When** they play back
   the associated audio, **Then** they hear what they actually said and can
   correct the field in place.
3. **Given** a record produced from a recording, **When** the beekeeper opens
   it at any later time, **Then** the original recording and full transcript
   remain retrievable.

---

### User Story 4 - Decide how long my voice is kept (Priority: P4)

A beekeeper's recordings are their own voice describing their own colonies.
They can see how long recordings are kept, change that period, and delete any
recording immediately. When a recording eventually ages out, the inspection
record it produced stays — the history of the colony is not what expires.

**Why this priority**: It is the part of the product that is about trust rather
than function. Nothing here helps anyone inspect a hive, which is why it is
last, but shipping voice capture with no answer to "where does my voice go and
for how long" is the kind of gap that stops people using it at all.

**Independent Test**: Produce a record from a recording, delete the recording,
and confirm the record and transcript survive intact while playback is honestly
reported as unavailable. Then change the retention period and confirm it takes
effect.

**Acceptance Scenarios**:

1. **Given** a beekeeper who has never touched the setting, **When** they look
   at how long recordings are kept, **Then** it says 12 months.
2. **Given** the retention setting, **When** the beekeeper changes it, **Then**
   the new period applies to their recordings.
3. **Given** any recording, **When** the beekeeper chooses to delete it, **Then**
   the audio is gone immediately, regardless of the retention period.
4. **Given** a recording that has been deleted or has aged out, **When** the
   beekeeper opens the inspection record made from it, **Then** the record and
   its transcript are fully intact, and every field still shows the phrase it
   came from.
5. **Given** a field whose recording is no longer available, **When** the
   beekeeper tries to play it back, **Then** they are told the audio is no
   longer kept — not shown a control that silently fails.
6. **Given** a recording approaching its retention expiry, **When** that expiry
   is near, **Then** the beekeeper is told before anything is removed.
7. **Given** a recording whose record still has unconfirmed or flagged fields,
   **When** its retention expiry falls due, **Then** the beekeeper is warned
   that the evidence for those fields is about to go.

---

### Edge Cases

- The beekeeper names a hive that does not exist in their apiary, or says an
  identifier the system cannot match to any hive.
- Two hives have similar-sounding identifiers, or the beekeeper uses a nickname
  rather than the formal identifier.
- The dictation covers more than one hive in a single continuous recording.
- The beekeeper never names a hive at all.
- The dictation contains a correction spoken aloud ("queen seen — no wait, I
  didn't actually see her, just eggs").
- Background noise dominates: wind, a running smoker, a nearby road, or the
  colony itself roaring.
- The recording is cut off mid-sentence because the device ran out of battery
  or storage.
- The beekeeper switches language mid-recording, or uses the French term for a
  piece of equipment inside an otherwise English dictation.
- A whole dictation is recorded while the account language is set to the wrong
  one, and the resulting record is nonsense.
- The beekeeper dictates a treatment including a dose and a product name that
  sounds like an ordinary word.
- The beekeeper dictates a date that conflicts with the date the recording was
  actually made ("this is Tuesday's inspection, I'm only doing it now").
- Local storage fills up while recordings are queued and unprocessed.
- The same recording is submitted for processing twice.
- The beekeeper opens a field for playback after its recording has passed
  retention expiry.
- Retention expiry falls due for a recording whose record still has
  unconfirmed or flagged fields.
- Processing succeeds but produces a record where every single field is flagged.

## Requirements *(mandatory)*

### Functional Requirements

**Capture**

- **FR-001**: The system MUST allow a beekeeper to record a spoken inspection
  with no network connection available.
- **FR-002**: The system MUST persist a recording to durable local storage
  before indicating to the beekeeper that the recording succeeded.
- **FR-003**: The system MUST NOT delete or discard a locally held recording
  until it has been durably stored beyond the device.
- **FR-004**: The system MUST allow starting, stopping and confirming a
  recording using controls operable with beekeeping gloves, without requiring
  precise pointing, hovering, or long-press-only gestures.
- **FR-005**: The system MUST allow a beekeeper to submit an existing audio
  file for processing, producing the same kind of record as a live dictation.

**Extraction**

- **FR-006**: The system MUST produce, from a dictation, a structured
  inspection record containing at minimum: hive identity, inspection date,
  whether the queen was seen, brood state, stores state, colony temperament,
  treatments applied, and actions to do.
- **FR-006a**: Each observation field MUST hold a coded value drawn from a
  controlled vocabulary defined for that field, so that records are comparable
  across inspections and across seasons.
- **FR-006b**: Each populated field MUST also store the verbatim phrase from
  the dictation that it was derived from, and MUST display that phrase to the
  beekeeper alongside the coded value.
- **FR-006c**: Controlled vocabulary values MUST be language-neutral
  identifiers with a display label in each supported language. A record
  dictated in French and an equivalent one dictated in English MUST store the
  same coded value.
- **FR-006d**: When a spoken observation cannot be mapped to a value in the
  field's controlled vocabulary, the system MUST flag that field as uncertain
  and retain the verbatim phrase. It MUST NOT force the observation into the
  nearest available value.
- **FR-007**: The system MUST mark as unknown any field the dictation did not
  cover, and MUST NOT populate it with an inferred, default, or carried-over
  value.
- **FR-008**: The system MUST mark as uncertain any field it extracted with low
  confidence, and MUST surface that uncertainty to the beekeeper for
  confirmation.
- **FR-009**: The system MUST distinguish, visibly and in the stored record,
  between values it derived itself and values the beekeeper entered or
  confirmed.
- **FR-010**: The system MUST treat every extracted value as a draft until the
  beekeeper confirms it, and a beekeeper's correction MUST permanently take
  precedence over any later automated interpretation of the same recording.
- **FR-011**: The system MUST store, with every record it produces, which
  interpretation method and version produced it, so that two records can be
  compared and a past result can be reproduced.
- **FR-012**: The system MUST retain the original recording and its transcript
  and keep both retrievable alongside the record derived from them.
- **FR-013**: The system MUST produce structurally identical records whether the
  dictation was in French or in English.
- **FR-014**: The system MUST interpret the beekeeping vocabulary listed in
  the project's bilingual domain glossary — equipment, colony conditions and
  common treatment products — at the accuracy threshold set in SC-005, in both
  supported languages.
- **FR-015**: The system MUST associate each record with exactly one hive, and
  MUST flag rather than guess when it cannot determine which hive was meant.
- **FR-015a**: Beekeepers MUST be able to create a hive by giving it an
  identifier they can say out loud, without having to supply anything else.
- **FR-015b**: Beekeepers MUST be able to create a hive from the review flow,
  when a dictation named an identifier that matches no existing hive.
- **FR-015c**: The system MUST NOT create a hive on its own. Creation is always
  an explicit beekeeper action.
- **FR-015d**: Hive identifiers MUST be unique within a beekeeper's hives, and
  the system MUST refuse a duplicate rather than silently attaching the record
  to the wrong colony.
- **FR-016**: The system MUST default the inspection date to when the recording
  was made, and MUST use a date spoken in the dictation in preference to that
  default when one is given.

**Processing and queueing**

- **FR-017**: The system MUST allow recordings to be processed separately from
  when they were captured, including after an arbitrary delay.
- **FR-018**: The system MUST show the beekeeper which recordings are awaiting
  processing and which have failed.
- **FR-019**: The system MUST retry failed processing without the beekeeper
  having to re-record, and MUST preserve the recording across failures.
- **FR-020**: The system MUST ensure that submitting the same recording more
  than once does not produce duplicate inspection records.
- **FR-021**: The system MUST warn the beekeeper before local storage is
  exhausted by unprocessed recordings.

**Review and correction**

- **FR-022**: Beekeepers MUST be able to review, correct, and confirm every
  field of a produced record.
- **FR-023**: Beekeepers MUST be able to see the transcript passage each
  populated field was derived from, and play back the corresponding audio.
- **FR-024**: The system MUST allow a record to be saved in an unconfirmed
  state and reviewed later, so that review is never a prerequisite for closing
  the hive and moving on.

**Language and privacy**

- **FR-025**: The entire flow — capture, review, correction, and every message
  and error — MUST be available in both French and English.
- **FR-026**: The beekeeper's language MUST be a persistent account setting
  that applies to every recording, MUST remain available offline, and MUST NOT
  be inferred from network location.
- **FR-026a**: The system MUST NOT require the beekeeper to choose a language
  at recording time. Starting a recording takes no language decision.
- **FR-026b**: Beekeepers MUST be able to change the language of a produced
  record at review and have the recording re-processed against the corrected
  language.
- **FR-026c**: Re-processing after a language correction MUST preserve any
  fields the beekeeper had already confirmed.
- **FR-027**: Recordings and transcripts are personal operational data and MUST
  NOT be exposed beyond the beekeeper's own account, nor sent to any external
  service the beekeeper has not been informed about.
- **FR-027a**: The system MUST retain original recordings for 12 months by
  default, and MUST allow the beekeeper to change that period.
- **FR-027b**: The system MUST allow a beekeeper to delete any recording
  immediately, regardless of the retention setting.
- **FR-027c**: Deleting a recording MUST NOT delete the transcript or the
  inspection record derived from it. The record outlives the audio.
- **FR-027d**: When a recording is no longer available, the system MUST say so
  where playback would otherwise be offered, rather than failing silently or
  appearing broken.
- **FR-027e**: The system MUST tell the beekeeper, before retention expiry
  removes anything, that it is about to happen.
- **FR-027f**: A beekeeper's recordings MUST NOT be used as evaluation material
  without their explicit, separately given consent.
- **FR-028**: The system MUST record the cost and latency of each automated
  interpretation it performs.

### Key Entities *(include if feature involves data)*

- **Recording**: A captured audio segment of a spoken inspection. Holds when it
  was captured, how long it is, what language was selected, its processing
  state (pending, processing, processed, failed), its retention expiry, and the
  audio itself. Has a stable identity assigned at capture time so it survives
  retries and sync. It is the shortest-lived thing in the system: the
  transcript and record it produces both outlive it.
- **Transcript**: The text of what was said in a Recording, retained in full
  and linked back to positions in the audio so any passage can be replayed.
- **Inspection Record**: The structured outcome of one inspection of one hive.
  Holds hive identity, inspection date, queen seen, brood state, stores state,
  temperament, treatments applied, and actions to do. Linked to the Recording
  and Transcript it was derived from, and to the provenance of the
  interpretation that produced it.
- **Observation Field**: One field of an Inspection Record. Carries a coded
  value from its controlled vocabulary, the verbatim phrase that value was
  derived from, a pointer into the audio for that phrase, and a status —
  unknown, uncertain, system-derived, or beekeeper-confirmed.
- **Controlled Vocabulary**: The permitted values for one observation field,
  each a language-neutral identifier with a display label per supported
  language. Owned by the project, versioned, and extended deliberately rather
  than growing from whatever a dictation happened to contain.
- **Hive**: The colony being inspected, identified by a stable identifier the
  beekeeper recognises and can say out loud, unique among their hives.
  Inspection Records attach to it and form its history. In this feature a hive
  is its identifier and nothing more — location, equipment, lineage and the
  rest belong to apiary management, which is out of scope.
- **Treatment**: A product applied to a colony, with what was applied, how much,
  and when. Part of an Inspection Record and significant for regulatory and
  harvest-timing reasons, so it is never inferred.
- **Action To Do**: Something the beekeeper decided during the inspection to
  come back and do, captured as it was spoken and attached to the hive.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A beekeeper can dictate a routine inspection and end up with a
  saved record in under 90 seconds of their attention, including review.
- **SC-002**: 100% of inspection dictations can be captured with no network
  connection, and no recording is lost between capture and processing.
- **SC-003**: Of the fields a beekeeper has to correct after review, at least
  85% were already flagged as unknown or uncertain — that is, fewer than 15% of
  corrections are of values the system asserted confidently and got wrong.
- **SC-004**: No field is ever populated from a dictation that did not mention
  it: zero tolerance, measured on the evaluation set.
- **SC-005**: Extraction quality on French dictations is within 5 percentage
  points of English on the same evaluation set.
- **SC-006**: 90% of beekeepers complete their first dictated inspection
  without assistance, wearing gloves, outdoors.
- **SC-007**: A recording captured offline is processed and its record
  available within 5 minutes of connectivity returning.
- **SC-008**: Beekeepers dictate rather than type for at least 80% of
  inspections after the first week of use.
- **SC-009**: Every record can be traced to its originating audio for at least
  12 months after the inspection, and to its transcript for the full life of
  the record.

## Assumptions

- **Minimal hive creation is in scope**: A beekeeper can create a hive by
  giving it a sayable identifier, either up front or from the review flow when
  a dictation names something unrecognised. This is deliberately the smallest
  registry that makes voice capture shippable on its own. Everything else about
  managing an apiary — locations, equipment, queen lineage, colony history
  beyond inspections, moving or merging hives — is a separate feature and out
  of scope here.
- **One hive per recording**: A recording covers a single hive. A dictation
  spanning several hives is treated as an edge case to be flagged for the
  beekeeper, not silently split.
- **Unmatched hive identifiers are parked, not invented**: If the spoken hive
  identifier matches no known hive, the record is produced with the hive field
  flagged and the beekeeper resolves it at review — by picking an existing hive
  or by creating one then and there. The system never creates a hive on its
  own.
- **Review is deferrable**: Records save in an unconfirmed state. A beekeeper
  can dictate ten hives and review all ten later, because forcing review at the
  hive would defeat the point of dictating in the first place.
- **Free-text actions**: Actions to do are captured as the beekeeper phrased
  them and attached to the hive — they are the one part of a record with no
  controlled vocabulary, because the space of things a beekeeper decides to
  come back and do is not enumerable. Turning them into scheduled, assignable
  or reminder-driven tasks is a separate feature.
- **Vocabularies are a deliverable**: Defining the controlled vocabulary for
  each observation field, in both languages, is part of this feature's work.
  They are a domain decision, not an implementation detail, and getting them
  wrong is expensive to undo once records exist.
- **Single beekeeper per account**: No sharing, delegation, or multi-operator
  apiaries in this feature.
- **Recording length**: A single inspection dictation is on the order of
  seconds to a few minutes, not hours. Whole-visit recordings covering an
  entire apiary are out of scope for this feature.
- **One language at a time**: The beekeeper speaks either French or English,
  set once as an account preference rather than chosen at each hive. A
  dictation that mixes the two, or one recorded under the wrong setting, is
  recoverable at review by correcting the language and re-processing. Other
  languages are out of scope.
- **Evaluation data exists**: Building this feature includes assembling an
  evaluation set of real dictated inspections in both languages, held in
  private storage. Without it, none of the quality criteria above are
  measurable. That set is built from consented or purpose-made recordings —
  a beekeeper's own inspections are not quietly repurposed as eval material.
- **Retention applies to audio only**: Inspection records and transcripts are
  kept for the life of the account. Twelve months is the default lifespan of
  the audio alone, chosen because disputes surface a season later and because
  audio is the bulkiest and most personal thing the system holds.
