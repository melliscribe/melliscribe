# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-006i and Principle VIII: every value has a label in both languages."""

from __future__ import annotations

import json
import shutil

from melliscribe.cli.main import main
from melliscribe.domain.vocabulary.check import DEFAULT_CATALOGUE_DIR
from melliscribe.domain.vocabulary.check import find_vocabulary_gaps


def test_the_shipped_catalogues_are_complete():
    assert find_vocabulary_gaps(DEFAULT_CATALOGUE_DIR) == []


def _copy_catalogues(tmp_path):
    for name in ("fr.json", "en.json"):
        shutil.copy(DEFAULT_CATALOGUE_DIR / name, tmp_path / name)
    return tmp_path


def test_a_missing_vocabulary_label_is_reported(tmp_path):
    catalogue_dir = _copy_catalogues(tmp_path)
    fr = json.loads((catalogue_dir / "fr.json").read_text())
    del fr["vocabulary"]["temperament"]["calm"]
    (catalogue_dir / "fr.json").write_text(json.dumps(fr))
    gaps = find_vocabulary_gaps(catalogue_dir)
    assert "fr: missing label vocabulary.temperament.calm" in gaps


def test_a_key_present_in_one_language_only_is_reported(tmp_path):
    catalogue_dir = _copy_catalogues(tmp_path)
    en = json.loads((catalogue_dir / "en.json").read_text())
    en["field"]["extra"] = "Only in English"
    (catalogue_dir / "en.json").write_text(json.dumps(en))
    assert "fr: missing key field.extra" in find_vocabulary_gaps(catalogue_dir)


def test_an_empty_label_is_reported(tmp_path):
    catalogue_dir = _copy_catalogues(tmp_path)
    en = json.loads((catalogue_dir / "en.json").read_text())
    en["status"]["unknown"] = " "
    (catalogue_dir / "en.json").write_text(json.dumps(en))
    assert "en: empty label status.unknown" in find_vocabulary_gaps(catalogue_dir)


def test_check_command_exits_non_zero_on_a_gap(tmp_path, capsys):
    catalogue_dir = _copy_catalogues(tmp_path)
    en = json.loads((catalogue_dir / "en.json").read_text())
    del en["flag_reason"]["date_conflict"]
    (catalogue_dir / "en.json").write_text(json.dumps(en))
    code = main(["vocabulary", "check", "--catalogue-dir", str(catalogue_dir)])
    assert code == 1
    assert "flag_reason.date_conflict" in capsys.readouterr().err


def test_check_command_passes_on_the_shipped_catalogues():
    assert main(["vocabulary", "check"]) == 0
