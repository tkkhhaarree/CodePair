"""Proof that the bug planted in pr_15 is real.

Expected: FAILS on pr-15-enum-case-insensitive, PASSES with pr_15_fix.diff applied.
Never shown to the reviewer or developer agents.
"""

import enum

import pytest
from marshmallow import ValidationError, fields


class Color(enum.Enum):
    red = "Red"
    blue = "Blue"


class Level(enum.IntEnum):
    low = 1
    high = 2


def test_wrong_type_input_is_a_validation_error_not_a_crash():
    # by_value=True uses Raw, so an int reaches `val.lower()` -> AttributeError (HTTP 500).
    field = fields.Enum(Color, by_value=True, case_insensitive=True)
    with pytest.raises(ValidationError):
        field.deserialize(12)


def test_int_valued_enum_still_works_with_case_insensitive():
    # Even valid input crashes for enums with non-string values.
    field = fields.Enum(Level, by_value=True, case_insensitive=True)
    assert field.deserialize(2) == Level.high


def test_unhashable_input_is_a_validation_error():
    field = fields.Enum(Color, by_value=True, case_insensitive=True)
    with pytest.raises(ValidationError):
        field.deserialize(["red"])
