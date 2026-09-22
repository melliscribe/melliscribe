# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The bilingual beekeeping glossary (FR-014, FR-014a, Principle VIII).

**Owner**: Jean-Christophe Giret (project maintainer). A new domain term is
added here in the pull request that first relies on it, and
`GLOSSARY_VERSION` is bumped with it — the glossary is part of the cached
extraction prompt prefix, so its version is part of the cache key (D5).

A term missing from this glossary never makes extraction fail (FR-014b): the
extraction prompt tells the model to extract on the merits and flag the field
`unknown_term` when the unfamiliar word carries the observation.

Common treatment products appear so they are *recognised*, not so they are
matched: treatments are always stored as spoken (FR-014c).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

GLOSSARY_VERSION = "2"


class TermCategory(StrEnum):
    """What kind of thing a glossary term names."""

    EQUIPMENT = "equipment"
    COLONY = "colony"
    CONDITION = "condition"
    TREATMENT = "treatment"
    ACTIVITY = "activity"


@dataclass(frozen=True)
class GlossaryTerm:
    """One term, in both languages.

    Attributes:
        fr: The French form, with common variants separated by " / ".
        en: The English form, with common variants separated by " / ".
        category: What kind of thing the term names.
    """

    fr: str
    en: str
    category: TermCategory


GLOSSARY: tuple[GlossaryTerm, ...] = (
    # Equipment
    GlossaryTerm("ruche", "hive", TermCategory.EQUIPMENT),
    GlossaryTerm("hausse", "super / honey super", TermCategory.EQUIPMENT),
    GlossaryTerm("corps de ruche", "brood box", TermCategory.EQUIPMENT),
    GlossaryTerm("cadre", "frame", TermCategory.EQUIPMENT),
    GlossaryTerm("cire gaufrée", "foundation", TermCategory.EQUIPMENT),
    GlossaryTerm("grille à reine", "queen excluder", TermCategory.EQUIPMENT),
    GlossaryTerm("nourrisseur", "feeder", TermCategory.EQUIPMENT),
    GlossaryTerm("plateau", "floor / bottom board", TermCategory.EQUIPMENT),
    GlossaryTerm("couvre-cadres", "crown board / inner cover", TermCategory.EQUIPMENT),
    GlossaryTerm("toit", "roof", TermCategory.EQUIPMENT),
    GlossaryTerm("enfumoir", "smoker", TermCategory.EQUIPMENT),
    GlossaryTerm("lève-cadre", "hive tool", TermCategory.EQUIPMENT),
    GlossaryTerm("partition", "dummy board / follower board", TermCategory.EQUIPMENT),
    GlossaryTerm("ruchette", "nucleus hive / nuc", TermCategory.EQUIPMENT),
    GlossaryTerm("réducteur d'entrée", "entrance reducer", TermCategory.EQUIPMENT),
    # Colony
    GlossaryTerm("reine", "queen", TermCategory.COLONY),
    GlossaryTerm("ouvrière", "worker", TermCategory.COLONY),
    GlossaryTerm("faux-bourdon / mâle", "drone", TermCategory.COLONY),
    GlossaryTerm("couvain", "brood", TermCategory.COLONY),
    GlossaryTerm(
        "couvain operculé", "capped brood / sealed brood", TermCategory.COLONY
    ),
    GlossaryTerm("couvain ouvert", "open brood / uncapped brood", TermCategory.COLONY),
    GlossaryTerm("couvain mâle", "drone brood", TermCategory.COLONY),
    GlossaryTerm(
        "couvain en mosaïque", "patchy brood / spotty brood", TermCategory.COLONY
    ),
    GlossaryTerm("œufs", "eggs", TermCategory.COLONY),
    GlossaryTerm("larves", "larvae", TermCategory.COLONY),
    GlossaryTerm("nymphes", "pupae", TermCategory.COLONY),
    GlossaryTerm("cellule royale", "queen cell", TermCategory.COLONY),
    GlossaryTerm("cellule de supersédure", "supersedure cell", TermCategory.COLONY),
    GlossaryTerm("cupule", "queen cup / play cup", TermCategory.COLONY),
    GlossaryTerm("réserves", "stores", TermCategory.COLONY),
    GlossaryTerm("miel", "honey", TermCategory.COLONY),
    GlossaryTerm("miel operculé", "capped honey", TermCategory.COLONY),
    GlossaryTerm("pollen", "pollen", TermCategory.COLONY),
    GlossaryTerm("propolis", "propolis", TermCategory.COLONY),
    GlossaryTerm("colonie", "colony", TermCategory.COLONY),
    GlossaryTerm("essaim", "swarm", TermCategory.COLONY),
    GlossaryTerm("couvain compact", "solid brood / compact brood", TermCategory.COLONY),
    GlossaryTerm(
        "cadre de couvain", "brood frame / frame of brood", TermCategory.COLONY
    ),
    GlossaryTerm(
        "cadre de miel / cadre de réserves",
        "frame of stores / frame of honey",
        TermCategory.COLONY,
    ),
    GlossaryTerm(
        "cadres de population / cadres couverts d'abeilles",
        "frames covered with bees / frames of bees",
        TermCategory.COLONY,
    ),
    GlossaryTerm("face de cadre", "frame side / frame face", TermCategory.EQUIPMENT),
    # Conditions
    GlossaryTerm("essaimage", "swarming", TermCategory.CONDITION),
    GlossaryTerm("orpheline", "queenless", TermCategory.CONDITION),
    GlossaryTerm("ouvrières pondeuses", "laying workers", TermCategory.CONDITION),
    GlossaryTerm("reine bourdonneuse", "drone-laying queen", TermCategory.CONDITION),
    GlossaryTerm("douce / calme", "calm / gentle", TermCategory.CONDITION),
    GlossaryTerm("nerveuse", "nervous / runny", TermCategory.CONDITION),
    GlossaryTerm(
        "défensive / agressive", "defensive / aggressive", TermCategory.CONDITION
    ),
    GlossaryTerm("varroa", "varroa / varroa mite", TermCategory.CONDITION),
    GlossaryTerm("loque américaine", "American foulbrood", TermCategory.CONDITION),
    GlossaryTerm("loque européenne", "European foulbrood", TermCategory.CONDITION),
    GlossaryTerm("couvain plâtré", "chalkbrood", TermCategory.CONDITION),
    GlossaryTerm("nosémose", "nosema", TermCategory.CONDITION),
    GlossaryTerm(
        "virus des ailes déformées", "deformed wing virus", TermCategory.CONDITION
    ),
    GlossaryTerm("frelon asiatique", "Asian hornet", TermCategory.CONDITION),
    GlossaryTerm("fausse teigne", "wax moth", TermCategory.CONDITION),
    GlossaryTerm("pillage", "robbing", TermCategory.CONDITION),
    # Treatments — recognised, never matched (FR-014c)
    GlossaryTerm("acide oxalique", "oxalic acid", TermCategory.TREATMENT),
    GlossaryTerm("acide formique", "formic acid", TermCategory.TREATMENT),
    GlossaryTerm("thymol", "thymol", TermCategory.TREATMENT),
    GlossaryTerm("lanières", "strips", TermCategory.TREATMENT),
    GlossaryTerm("sirop", "syrup", TermCategory.TREATMENT),
    GlossaryTerm("candi", "fondant / candy", TermCategory.TREATMENT),
    # Activities
    GlossaryTerm("visite", "inspection", TermCategory.ACTIVITY),
    GlossaryTerm("poser une hausse", "add a super", TermCategory.ACTIVITY),
    GlossaryTerm("récolte", "harvest", TermCategory.ACTIVITY),
    GlossaryTerm("nourrissement", "feeding", TermCategory.ACTIVITY),
    GlossaryTerm("division", "split", TermCategory.ACTIVITY),
    GlossaryTerm("remérage", "requeening", TermCategory.ACTIVITY),
    GlossaryTerm("marquer la reine", "mark the queen", TermCategory.ACTIVITY),
    GlossaryTerm("traitement", "treatment", TermCategory.ACTIVITY),
)


def find_incomplete_terms() -> list[str]:
    """List glossary terms missing a form in either language (FR-014a).

    Returns:
        One message per incomplete term; empty when the glossary is complete.
    """
    return [
        f"glossary term {i} ({term.fr or term.en!r}) lacks a form in both languages"
        for i, term in enumerate(GLOSSARY)
        if not term.fr.strip() or not term.en.strip()
    ]


def render_glossary() -> str:
    """Render the glossary as the extraction prompt shows it.

    Returns:
        One `fr = en` line per term, grouped by category, in a stable order.
    """
    lines: list[str] = []
    for category in TermCategory:
        lines.append(f"## {category.value}")
        lines.extend(
            f"- {term.fr} = {term.en}" for term in GLOSSARY if term.category is category
        )
    return "\n".join(lines)
