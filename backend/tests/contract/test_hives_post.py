# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""POST /hives: an identifier and nothing else, unique (FR-015a, FR-015d)."""

from __future__ import annotations


def test_a_hive_is_created_from_an_identifier_alone(api):
    response = api.client.post("/hives", json={"identifier": "  Ruche 3 "})
    assert response.status_code == 201
    assert response.json()["identifier"] == "Ruche 3"
    assert [h["identifier"] for h in api.client.get("/hives").json()] == ["Ruche 3"]


def test_a_duplicate_identifier_is_refused_not_disambiguated(api):
    api.client.post("/hives", json={"identifier": "La Grise"})
    response = api.client.post("/hives", json={"identifier": "La Grise"})
    assert response.status_code == 409
    assert response.json()["code"] == "duplicate_hive"
    assert len(api.client.get("/hives").json()) == 1


def test_an_empty_identifier_is_a_localised_validation_error(api):
    response = api.client.post("/hives", json={"identifier": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["message"]
