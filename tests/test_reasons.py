"""Tests for reasons paragraph helpers and ReasonsPatch."""

from __future__ import annotations

import pytest

from schemai_builder.models import ReasonReplace, ReasonsPatch
from schemai_builder.reasons import (
    apply_reasons_patch,
    format_numbered,
    split_paragraphs,
)


def test_split_and_number():
    text = "first\n\n\n second \n\n\n\n\nthird"
    paragraphs = split_paragraphs(text)
    assert paragraphs == ["first", "second", "third"]
    assert format_numbered(paragraphs) == "[1] first\n\n[2] second\n\n[3] third"


def test_delete_replace_append():
    text = "one\n\ntwo\n\nthree"
    patch = ReasonsPatch(
        delete=[3], replace=[ReasonReplace(id=1, text="ONE")], append=["four"]
    )
    assert apply_reasons_patch(text, patch) == "ONE\n\ntwo\n\nfour"


def test_ids_resolve_against_original_paragraphs():
    text = "one\n\ntwo\n\nthree\n\nfour"
    patch = ReasonsPatch(delete=[1], replace=[ReasonReplace(id=3, text="THREE")])
    assert apply_reasons_patch(text, patch) == "two\n\nTHREE\n\nfour"


def test_bad_id_raises():
    with pytest.raises(ValueError):
        apply_reasons_patch("one", ReasonsPatch(delete=[2]))
    with pytest.raises(ValueError):
        apply_reasons_patch("one", ReasonsPatch(replace=[ReasonReplace(id=0, text="")]))
