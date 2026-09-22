# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-027e: warn before expiry removes anything; louder when evidence is at stake."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime

from melliscribe.cli.main import main
from melliscribe.domain.retention.expiry import apply_expiry
from melliscribe.domain.retention.expiry import find_due
from tests.support.builders import build_output
from tests.support.builders import heard

NOW = datetime(2027, 5, 1, tzinfo=UTC)


def _upload(api, output, captured_at="2026-05-12T09:30:00+00:00"):
    api.extractor.output = output
    return api.upload(captured_at=captured_at).json()["id"]


def test_recordings_about_to_expire_are_listed(api):
    recording_id = _upload(api, build_output())
    with api.services.session_factory() as session:
        due = find_due(session, now=NOW, within_days=30)
    assert [d.recording_id for d in due] == [recording_id]


def test_a_record_with_flagged_fields_warrants_the_louder_warning(api):
    """US4 scenario 7: the evidence for an open question is about to go."""
    flagged = _upload(
        api, build_output(temperament=heard("calm", "Elles", 1, confidence=0.2))
    )
    with api.services.session_factory() as session:
        [due] = find_due(session, now=NOW, within_days=30)
    assert due.recording_id == flagged
    assert due.needs_attention is True


def test_a_confirmed_record_gets_the_ordinary_warning(api):
    recording_id = _upload(api, build_output())
    [record] = api.client.get("/records").json()
    api.client.patch(
        f"/records/{record['id']}", json={"version": record["version"], "stores": "low"}
    )
    api.client.post(f"/records/{record['id']}/resolve-hive", json={"identifier": "3"})
    api.client.post(f"/records/{record['id']}/confirm")
    with api.services.session_factory() as session:
        [due] = find_due(session, now=NOW, within_days=30)
    assert due.recording_id == recording_id
    assert due.needs_attention is False


def test_expiry_deletes_only_expired_audio_and_keeps_records(api):
    _upload(api, build_output(), captured_at="2026-01-01T09:00:00+00:00")
    fresh = _upload(api, build_output(), captured_at="2027-04-01T09:00:00+00:00")
    with api.services.session_factory.begin() as session:
        removed = apply_expiry(session, api.services.audio_store, now=NOW)
    assert len(removed) == 1
    assert fresh not in removed
    assert len(api.client.get("/records").json()) == 2


def test_the_api_exposes_the_warning(api):
    _upload(api, build_output(), captured_at="2026-01-01T09:00:00+00:00")
    response = api.client.get("/recordings/expiring", params={"within_days": 3650})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_retention_cli_dry_run_changes_nothing(api, monkeypatch, capsys):
    _upload(api, build_output(), captured_at="2020-01-01T09:00:00+00:00")
    monkeypatch.setattr(
        "melliscribe.cli.retention.build_services", lambda: api.services
    )
    assert main(["retention", "apply", "--dry-run"]) == 0
    assert "would delete 1" in capsys.readouterr().out
    assert all(r["audio_available"] for r in api.client.get("/records").json())
