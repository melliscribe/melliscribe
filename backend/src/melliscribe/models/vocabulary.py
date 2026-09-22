# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Controlled vocabularies for the observation fields (FR-006a, FR-006g).

Every value is a language-neutral identifier (FR-006c). Display labels live in
the frontend i18n catalogues under `vocabulary.<field>.<value>`, and
`melliscribe vocabulary check` fails the build when one is missing (FR-006i).

**Fields with a controlled vocabulary**: `queen_seen`, `brood`, `stores`,
`temperament`.

**Fields without one** (FR-006g requires listing them explicitly):
`treatments` (product and dose are kept as spoken, FR-014c), `actions_to_do`
(free text by design), `inspection_date` (a date) and `hive` (resolved against
the beekeeper's own hive identifiers).

**Ordering**: every vocabulary is unordered (spec Assumptions). Nothing in this
feature compares values or derives a trend from them.

**Stability** (FR-006h): a released value is never removed and never given a
different meaning.
[check_released_values][melliscribe.models.vocabulary.check_released_values]
compares the live definitions against `vocabulary.lock.json`, which records
every released value with its definition. A value that is no longer
appropriate is listed in its vocabulary's `superseded` mapping and stays in the
enum so historical records keep meaning what they meant.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
from pathlib import Path

VOCABULARY_VERSION = "1"
"""Bumped on any change to a vocabulary; recorded in every record's provenance."""

LOCK_FILE = Path(__file__).with_name("vocabulary.lock.json")


class QueenSeen(StrEnum):
    """Whether the queen herself was seen."""

    SEEN = "seen"
    NOT_SEEN = "not_seen"
    NOT_LOOKED_FOR = "not_looked_for"


class BroodState(StrEnum):
    """What the brood nest showed."""

    ALL_STAGES = "all_stages"
    NO_EGGS = "no_eggs"
    NO_BROOD = "no_brood"
    PATCHY = "patchy"
    DRONE_BROOD_ONLY = "drone_brood_only"


class StoresState(StrEnum):
    """How much honey and pollen the colony holds."""

    PLENTIFUL = "plentiful"
    ADEQUATE = "adequate"
    LOW = "low"
    NONE = "none"


class Temperament(StrEnum):
    """How the colony behaved during the inspection."""

    CALM = "calm"
    NERVOUS = "nervous"
    DEFENSIVE = "defensive"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class Vocabulary:
    """The documented definition of one field's controlled vocabulary.

    Attributes:
        field_name: The observation field this vocabulary constrains.
        values: The enum holding the language-neutral identifiers.
        membership: What makes a candidate value belong to this vocabulary.
        definitions: The meaning of each value. Released meanings never change.
        ordered: Whether the values form a scale. False for every field today.
        superseded: Values retained for history but no longer proposed,
            mapped to the reason they were retired.
    """

    field_name: str
    values: type[StrEnum]
    membership: str
    definitions: dict[str, str]
    ordered: bool = False
    superseded: dict[str, str] = field(default_factory=dict)

    def get_active_values(self) -> list[str]:
        """Return the values extraction may propose.

        Returns:
            The identifiers that are not superseded, in declaration order.
        """
        return [v.value for v in self.values if v.value not in self.superseded]


VOCABULARIES: dict[str, Vocabulary] = {
    "queen_seen": Vocabulary(
        field_name="queen_seen",
        values=QueenSeen,
        membership=(
            "The queen herself, not evidence of her. Eggs or young larvae are "
            "brood observations and never set this field."
        ),
        definitions={
            "seen": "The beekeeper saw the queen.",
            "not_seen": "The beekeeper looked for the queen and did not see her.",
            "not_looked_for": "The beekeeper says they did not look for the queen.",
        },
    ),
    "brood": Vocabulary(
        field_name="brood",
        values=BroodState,
        membership=(
            "The overall state of the brood nest as a single category. A value "
            "belongs here only if a beekeeper would act differently on it."
        ),
        definitions={
            "all_stages": "Eggs, larvae and capped brood are all present.",
            "no_eggs": "Larvae or capped brood present, but no eggs seen.",
            "no_brood": "No brood of any stage.",
            "patchy": "Brood present in a spotty or irregular pattern.",
            "drone_brood_only": (
                "Only drone brood, including drone brood in worker cells."
            ),
        },
    ),
    "stores": Vocabulary(
        field_name="stores",
        values=StoresState,
        membership=(
            "The colony's honey and pollen reserves as the beekeeper judged "
            "them. A value belongs here if it changes whether to feed."
        ),
        definitions={
            "plentiful": "More stores than the colony needs; room to harvest.",
            "adequate": "Enough stores for the colony's current needs.",
            "low": "Stores are short; feeding may be needed.",
            "none": "No stores to speak of.",
        },
    ),
    "temperament": Vocabulary(
        field_name="temperament",
        values=Temperament,
        membership=(
            "The colony's behaviour towards the beekeeper during this "
            "inspection, not a judgement of the colony's genetics."
        ),
        definitions={
            "calm": "Bees stay on the frames; little or no reaction.",
            "nervous": "Bees run on the frames or take to the air, no stinging.",
            "defensive": "Bees fly at the beekeeper; some stings.",
            "aggressive": "Sustained attack; many stings; bees follow.",
        },
    ),
}


def check_released_values(lock_file: Path = LOCK_FILE) -> list[str]:
    """Compare the live vocabularies against the released lock file.

    Args:
        lock_file: The JSON file recording every released value and meaning.

    Returns:
        One message per violation of FR-006h; empty when the vocabularies are
        compatible with every released record.
    """
    released: dict[str, dict[str, str]] = json.loads(lock_file.read_text("utf-8"))
    problems: list[str] = []
    for field_name, values in released.items():
        vocabulary = VOCABULARIES.get(field_name)
        if vocabulary is None:
            problems.append(f"{field_name}: released vocabulary was removed")
            continue
        live = {v.value for v in vocabulary.values}
        for value, meaning in values.items():
            if value not in live:
                problems.append(f"{field_name}.{value}: released value was removed")
            elif vocabulary.definitions.get(value) != meaning:
                problems.append(f"{field_name}.{value}: released meaning changed")
    return problems


def build_lock() -> dict[str, dict[str, str]]:
    """Build the lock file content from the live vocabularies.

    Returns:
        Every value of every vocabulary with its definition.
    """
    return {
        name: {v.value: vocabulary.definitions[v.value] for v in vocabulary.values}
        for name, vocabulary in VOCABULARIES.items()
    }
