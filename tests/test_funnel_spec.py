"""Funnel validation fixtures (docs/design/funnels_v2_spec.md, part 4)."""

import copy

import funnel_spec as fs
import funnel_templates as ft


def test_every_provided_funnel_validates_without_blocks():
    for market in ("crypto", "equity"):
        for direction in ("long", "short"):
            blocks, warns = fs.validate(ft.trend_funnel(direction, market))
            assert blocks == [] and warns == [], (market, direction, blocks, warns)


def test_blocks():
    f = ft.trend_funnel("long")
    assert fs.validate({**f, "stages": f["stages"][:2]})[0]                         # too few stages
    assert fs.validate({**f, "direction": "sideways"})[0]
    bad = copy.deepcopy(f)
    bad["stages"][0]["timeframe"] = "2h"
    assert fs.validate(bad)[0]
    shares = ft.trend_funnel("long", "equity")
    twelve = copy.deepcopy(shares)
    twelve["stages"][1]["timeframe"] = "12h"
    assert any("6½ hours" in b for b in fs.validate(twelve)[0])
    no_decision = copy.deepcopy(f)
    no_decision["stages"][1]["set_body"].pop("decision")
    assert fs.validate(no_decision)[0]
    assert fs.validate({**f, "pool": {"top": 75}})[0]


def test_warnings():
    f = copy.deepcopy(ft.trend_funnel("long"))
    f["stages"][0], f["stages"][2] = f["stages"][2], f["stages"][0]                 # 4h before the daily
    blocks, warns = fs.validate(f)
    assert not blocks and any("longest timeframe" in w for w in warns)
    mixed = copy.deepcopy(ft.trend_funnel("long"))
    mixed["stages"][2]["timeframe"] = "1h"                                          # a 4-hour Set checked hourly
    mixed["stages"][3]["timeframe"] = "1h"
    assert any("sets when it is checked" in w for w in fs.validate(mixed)[1])
