"""Proof that the bug planted in pr_13 is real.

Expected: FAILS on pr-13-timedelta-int-micros, PASSES with pr_13_fix.diff applied
(and on demo-main).
Never shown to the reviewer or developer agents.
"""

import datetime as dt

from marshmallow import fields


def test_fractional_microseconds_are_rounded_not_truncated():
    # The class docstring promises this; int() truncates 1123456.7 to 1123456.
    assert fields.TimeDelta().deserialize("1.1234567") == dt.timedelta(
        seconds=1, microseconds=123457
    )


def test_sub_microsecond_milliseconds_round_up():
    field = fields.TimeDelta(fields.TimeDelta.MILLISECONDS)
    assert field.deserialize("0.0009") == dt.timedelta(microseconds=1)
