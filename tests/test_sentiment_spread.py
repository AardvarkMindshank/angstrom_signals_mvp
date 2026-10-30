import sentiment_spread as ss


def report(*scores):
    return {"headlines": [{"title": f"t{i}", "score": s} for i, s in enumerate(scores)] + [{"title": "unscored"}]}


def test_spread_words():
    assert ss.spread_word([50, 52, 48, 55])[0] == "agree"
    assert ss.spread_word([35, 50, 65, 45])[0] == "mixed"
    assert ss.spread_word([10, 15, 85, 90])[0] == "split"
    assert ss.spread_word([50])[0] == ""


def test_strip_has_a_dot_per_scored_article_and_a_hover():
    out = ss.spread_html(report(20, 40, 60, 80, 81), 56.2)
    assert out.count("<circle") == 5 and "5 articles" in out and "split" in out
    assert "average (56)" in out
    assert ss.spread_html(report(50)) == "" and ss.spread_html(None) == ""


def test_market_score_averages_articles_and_readings():
    from sentiment import combine_mood_score
    rep = {"score": 40.0, "headlines": [{"score": 40}, {"score": 50}, {"title": "x"}],
           "gauges": [{"title": "Central banks", "items": [{"score": 70}, {"score": 80}]}, {"items": [{"label": "none"}]}]}
    combine_mood_score(rep)
    assert rep["score"] == 60.0
    assert rep["score_parts"] == {"news": 2, "readings": 2, "news_score": 45.0, "readings_score": 75.0}
    out = ss.spread_html(rep, rep["score"])
    assert out.count("<circle") == 4 and "4 sources" in out and "2 news articles and 2 public readings" in out
