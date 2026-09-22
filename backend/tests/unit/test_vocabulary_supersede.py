# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-006h: a released vocabulary value is never removed or redefined."""

from __future__ import annotations

import json

from melliscribe.models.vocabulary import LOCK_FILE
from melliscribe.models.vocabulary import VOCABULARIES
from melliscribe.models.vocabulary import build_lock
from melliscribe.models.vocabulary import check_released_values


def test_live_vocabularies_honour_every_released_value():
    assert check_released_values(LOCK_FILE) == []


def test_removing_a_released_value_is_refused(tmp_path):
    lock = build_lock()
    lock["temperament"]["docile"] = "A value released once and since deleted."
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock))
    assert check_released_values(path) == [
        "temperament.docile: released value was removed"
    ]


def test_redefining_a_released_value_is_refused(tmp_path):
    lock = build_lock()
    lock["stores"]["low"] = "A meaning the value used to have."
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock))
    assert check_released_values(path) == ["stores.low: released meaning changed"]


def test_adding_a_value_is_allowed(tmp_path):
    lock = build_lock()
    del lock["brood_pattern"]["patchy"]
    path = tmp_path / "lock.json"
    path.write_text(json.dumps(lock))
    assert check_released_values(path) == []


def test_superseded_values_stay_in_the_enum_but_are_not_proposed():
    vocabulary = VOCABULARIES["temperament"]
    superseding = type(vocabulary)(
        field_name=vocabulary.field_name,
        values=vocabulary.values,
        membership=vocabulary.membership,
        definitions=vocabulary.definitions,
        superseded={"aggressive": "Merged into defensive."},
    )
    assert "aggressive" not in superseding.get_active_values()
    assert "aggressive" in {v.value for v in superseding.values}


def test_every_value_has_a_definition():
    for vocabulary in VOCABULARIES.values():
        assert {v.value for v in vocabulary.values} == set(vocabulary.definitions)
