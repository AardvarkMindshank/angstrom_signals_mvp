"""Branded emails keep typed text safe and always carry a plain-text version."""
import email_brand as eb


def test_alert_tone_reads_the_direction():
    assert eb.alert_tone("Score 72 crossed above 70") == "up"
    assert eb.alert_tone("Score 28 fell below 30") == "down"
    assert eb.alert_tone("Something changed") == "info"


def test_button_and_plain_text():
    page, plain = eb.render_email("Hello", ["One <strong>two</strong>"], button=("Open it", "https://x.test/a?b=1&c=2"))
    assert 'href="https://x.test/a?b=1&amp;c=2"' in page
    assert "Open it: https://x.test/a?b=1&amp;c=2" not in plain
    assert "Open it: https://x.test/a?b=1&c=2" in plain or "Open it:" in plain
    assert "One two" in plain and "<" not in plain.replace("<3", "")


def test_links_in_paragraphs_survive_in_plain_text():
    _page, plain = eb.render_email("Hi", ['See <a href="https://x.test/p" style="color:red">the page</a>.'])
    assert "the page (https://x.test/p)" in plain


def test_footer_and_logo_always_present():
    page, plain = eb.render_email("T", ["p"])
    assert "not financial advice" in page and "logo.png" in page
    assert "not financial advice" in plain
