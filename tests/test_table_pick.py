import table_pick as tp


class Obj:
    def __init__(self, picked):
        self.picked = picked


def test_reads_click_from_either_table_and_ignores_destination():
    assert tp.clicked_pick({"score_table_Stock": {"picked": "Stock|AAPL|breakdown"}}) == ("Stock", "AAPL")
    assert tp.clicked_pick({"score_table_Crypto": Obj("Crypto|bitcoin")}) == ("Crypto", "bitcoin")


def test_no_click_or_bad_value_gives_none():
    assert tp.clicked_pick({}) is None
    assert tp.clicked_pick({"score_table_Crypto": {"picked": None}}) is None
    assert tp.clicked_pick({"score_table_Crypto": {"picked": "junk"}}) is None
    assert tp.clicked_pick({"score_table_Crypto": {"picked": "Other|x"}}) is None
