"""Pydantic schemas for the rubric layer + self-check (Phase E3).

Mirrored on the frontend in app/src/types/api.ts.

Rubrics are SEED CONTENT projected from the wiki, so there is no create/update
request model — the only write in E3 is the self-check, which lands in
`evidence_grades` (the table `0009` already built) rather than in a rubric.
"""

import uuid

from pydantic import BaseModel, Field

from app.models.enums import RubricVariant


class RubricItemOut(BaseModel):
    """One checkable assertion — verbatim wiki text, raw markdown preserved."""

    item_key: str
    ordinal: int
    bullet_ordinal: int
    variant: RubricVariant
    text: str
    rule_refs: list[str] | None = None

    model_config = {"from_attributes": True}


class RubricOut(BaseModel):
    """One drill's bar. `version` is what a self-check grade records, so the bar a
    historical grade was judged against stays identifiable after a wiki edit."""

    id: uuid.UUID
    slug: str
    drill_ref: str
    track: str
    version: int
    source_path: str
    source_ref: str | None = None
    items: list[RubricItemOut] = []

    model_config = {"from_attributes": True}


class SelfCheckIn(BaseModel):
    """The user's answer to the drill's own bar.

    Only the TICKED keys are sent; everything else in the rubric is recorded as
    unchecked. `rubric_slug` is optional — the server resolves it from a drill
    subject — but the client normally sends it, since it fetched the rubric to
    render the checkboxes.
    """

    checked_item_keys: list[str] = Field(default_factory=list)
    rubric_slug: str | None = None

    model_config = {"extra": "forbid"}
