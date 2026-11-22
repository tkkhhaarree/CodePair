"""Proof that the bug planted in pr_01 is real.

Expected: FAILS on pr-01-list-max-items, PASSES with pr_01_fix.diff applied.
Never shown to the reviewer or developer agents.
"""

import pytest
from marshmallow import ValidationError, fields


def test_list_with_exactly_max_items_is_allowed():
    # max_items=3 must accept 3 items; the PR uses >= and rejects them.
    field = fields.List(fields.Int(), max_items=3)
    assert field.deserialize([1, 2, 3]) == [1, 2, 3]


def test_list_with_one_more_than_max_items_is_rejected():
    field = fields.List(fields.Int(), max_items=3)
    with pytest.raises(ValidationError):
        field.deserialize([1, 2, 3, 4])
