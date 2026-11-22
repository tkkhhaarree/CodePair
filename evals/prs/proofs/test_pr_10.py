"""Proof that the bug planted in pr_10 is real.

Expected: FAILS on pr-10-boolean-enabled-disabled, PASSES with pr_10_fix.diff applied.
Never shown to the reviewer or developer agents.
"""

from marshmallow import fields


def test_lowercase_disabled_is_false():
    # The PR put "disabled" in the truthy set (instead of "enabled"); truthy is checked first.
    assert fields.Boolean().deserialize("disabled") is False


def test_lowercase_enabled_is_true():
    assert fields.Boolean().deserialize("enabled") is True
