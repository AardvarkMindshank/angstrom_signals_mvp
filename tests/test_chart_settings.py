import ast
import pathlib


def test_chart_choices_are_saved_through_the_account_settings():
    """app.py cannot be imported here, so check the wiring in its source."""
    source = pathlib.Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    ast.parse(source)
    for key in ("chart_indicators", "chart_overlay", "chart_earnings"):
        assert f'"{key}"' in source
    assert "save_account_settings(chart_choices)" in source
    # A widget given a session value must not also be given its own default.
    block = source[source.index('"Show earnings report dates"'): source.index('"Show earnings report dates"') + 200]
    assert "value=True" not in block
