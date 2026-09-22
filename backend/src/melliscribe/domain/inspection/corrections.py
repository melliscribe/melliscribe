# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The beekeeper's corrections and confirmations (FR-010, FR-022, FR-024).

A value the beekeeper sets or confirms becomes `CONFIRMED` and permanently wins
over any later extraction. The phrase it was heard as is kept, so the record
still shows where the field came from.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.models.inspection import OBSERVATION_FIELD_NAMES
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import InspectionRecord
from melliscribe.models.inspection import ObservationField

if TYPE_CHECKING:
    import uuid

    from melliscribe.models.api import RecordPatch


class OpenFlagsError(Exception):
    """The record still has fields needing the beekeeper's attention."""


def confirm_field(field: ObservationField[Any], value: Any) -> dict[str, Any]:  # noqa: ANN401
    """Confirm a field with the beekeeper's value, keeping its provenance.

    Args:
        field: The field as it was.
        value: The value the beekeeper set; None confirms "not observed".

    Returns:
        The confirmed field, as a dict to validate into its typed slot.
    """
    return {
        "status": FieldStatus.CONFIRMED,
        "value": value,
        "verbatim": field.verbatim,
        "segment_refs": [ref.model_dump() for ref in field.segment_refs],
    }


def _confirmed_text(text: str) -> dict[str, Any]:
    return {"status": FieldStatus.CONFIRMED, "value": text}


def apply_patch(record: InspectionRecord, patch: RecordPatch) -> InspectionRecord:
    """Apply a beekeeper's correction.

    Args:
        record: The record.
        patch: The fields to set; each present field becomes `CONFIRMED`.

    Returns:
        The corrected record.
    """
    document = record.model_dump()
    present = patch.model_fields_set - {"version"}
    for name in ("inspection_date", *OBSERVATION_FIELD_NAMES):
        if name in present:
            document[name] = confirm_field(getattr(record, name), getattr(patch, name))
    if "treatments" in present:
        document["treatments"] = [
            {
                "product": _confirmed_text(t.product),
                "dose": _confirmed_text(t.dose),
                "applied_on": t.applied_on,
            }
            for t in patch.treatments or []
        ]
    if "actions_to_do" in present:
        document["actions_to_do"] = [
            {"text": _confirmed_text(text)} for text in patch.actions_to_do or []
        ]
    return InspectionRecord.model_validate(document)


def resolve_hive(record: InspectionRecord, hive_id: uuid.UUID) -> InspectionRecord:
    """Attach the record to a hive the beekeeper chose (FR-015b).

    Args:
        record: The record.
        hive_id: The chosen or newly created hive.

    Returns:
        The record with a confirmed hive.
    """
    document = record.model_dump()
    document["hive"] = confirm_field(record.hive, hive_id)
    return InspectionRecord.model_validate(document)


def list_fields(record: InspectionRecord) -> list[ObservationField[Any]]:
    """List every field of a record, including treatments and actions.

    Args:
        record: The record.

    Returns:
        The fields.
    """
    fields: list[ObservationField[Any]] = [record.hive, record.inspection_date]
    fields += [getattr(record, name) for name in OBSERVATION_FIELD_NAMES]
    for treatment in record.treatments:
        fields += [treatment.product, treatment.dose]
    fields += [action.text for action in record.actions_to_do]
    return fields


def count_open_flags(record: InspectionRecord) -> int:
    """Count the fields still needing the beekeeper: uncertain, or no hive.

    Args:
        record: The record.

    Returns:
        The number of open flags.
    """
    open_flags = sum(f.status is FieldStatus.UNCERTAIN for f in list_fields(record))
    if record.hive.status is FieldStatus.UNKNOWN:
        open_flags += 1
    return open_flags


def confirm_record(
    record: InspectionRecord, now: datetime | None = None
) -> InspectionRecord:
    """Confirm the whole record: every derived value becomes confirmed.

    Unknown fields stay unknown — confirming a record does not invent values.

    Args:
        record: The record.
        now: The confirmation time.

    Returns:
        The confirmed record.

    Raises:
        OpenFlagsError: When a field is still uncertain or the hive unresolved.
    """
    if count_open_flags(record):
        raise OpenFlagsError
    document = record.model_dump()

    def confirm(data: dict[str, Any]) -> dict[str, Any]:
        if data["status"] is FieldStatus.SYSTEM_DERIVED:
            return data | {"status": FieldStatus.CONFIRMED, "confidence": None}
        return data

    for name in ("hive", "inspection_date", *OBSERVATION_FIELD_NAMES):
        document[name] = confirm(document[name])
    for treatment in document["treatments"]:
        treatment["product"] = confirm(treatment["product"])
        treatment["dose"] = confirm(treatment["dose"])
    for action in document["actions_to_do"]:
        action["text"] = confirm(action["text"])
    document["confirmed_at"] = now or datetime.now(UTC)
    return InspectionRecord.model_validate(document)
