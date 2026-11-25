"""Proof that the bug planted in pr_09 is real.

Expected: FAILS on pr-09-decimal-places-int, PASSES with pr_09_fix.diff applied
(and on demo-main, where places=0 already rounds correctly).
Never shown to the reviewer or developer agents.
"""

import decimal

from marshmallow import fields


def test_places_zero_rounds_to_whole_number():
    # places=0 means "round to an integer"; the PR's `if self.places` treats 0 as unset.
    field = fields.Decimal(places=0)
    assert field.deserialize("12.6") == decimal.Decimal(13)


def test_places_zero_with_rounding():
    field = fields.Decimal(0, decimal.ROUND_DOWN)
    assert str(field.deserialize("12.9")) == "12"
