import data_fetchers as df


def test_period_for_days_grows_with_the_request():
    assert df.period_for_days(60) == "3mo"
    assert df.period_for_days(365) == "1y"
    assert df.period_for_days(730) == "2y"
    assert df.period_for_days(1825) == "5y"
    assert df.period_for_days(3650) == "max"
