"""Open in Lattice (Why these readings, table cells) lands on the asked-for Group."""


def test_open_in_lattice_finds_a_provided_starter_even_when_starters_are_hidden():
    import lattice_view

    key = "starter:starter:trend"
    labels, _ = lattice_view._sources([], "me", key, provided=False)
    assert key in labels and "starter:starter:stretch" not in labels
    labels, _ = lattice_view._sources([], "me", None, provided=True)
    assert key in labels
