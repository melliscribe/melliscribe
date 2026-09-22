# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The uncertainty threshold (FR-008, FR-008a).

An explicit, versioned, documented value — not an implementation detail. It is
recorded in every record's provenance. Changing it changes extraction
behaviour and carries the same evaluation obligation as changing a prompt
(Principle II): run `melliscribe eval run` and put the result in the PR.

**Calibration status**: 0.7 is a starting value, not yet calibrated. T097
calibrates it against the full evaluation set so that fewer than 15% of
beekeeper corrections are of confidently-asserted values (SC-003), and records
the chosen value in ADR-0003.
"""

from __future__ import annotations

UNCERTAINTY_THRESHOLD = 0.7
"""A field extracted with confidence below this is `UNCERTAIN`."""

THRESHOLD_VERSION = "1"
