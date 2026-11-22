"""Proof that the bug planted in pr_04 is real.

Run with marshmallow's venv (it imports whatever branch is checked out in D:\\marshmallow):
    D:\\marshmallow\\.venv\\Scripts\\python.exe -m pytest D:\\CodePair\\evals\\prs\\proofs\\test_pr_04.py

Expected: PASSES on demo-main, FAILS on pr-04-set-value-sep.
Never shown to the reviewer or developer agents.
"""

from marshmallow import Schema, fields


class UserSchema(Schema):
    name = fields.String()
    age = fields.Integer()


def test_load_keeps_string_value():
    # schema.py calls set_value(ret_d, key, value): with the PR, "alice" lands in `sep`
    # and None is stored as the value.
    assert UserSchema().load({"name": "alice"}) == {"name": "alice"}


def test_load_keeps_int_value():
    # with the PR, `42 in "age"` raises TypeError
    assert UserSchema().load({"age": 42}) == {"age": 42}
