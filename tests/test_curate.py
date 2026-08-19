import curate

SAMPLE_RSS = """<?xml version="1.0"?>
<rss><channel>
  <item><title>New 777X milestone</title><description>Boeing hits a test target</description><link>https://ex.com/a</link><pubDate>Mon, 18 Aug 2026 10:00:00 GMT</pubDate></item>
  <item><title>Airline revives retro livery</title><description>Fan favorite returns</description><link>https://ex.com/b</link><pubDate>Sun, 17 Aug 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_parse_rss_extracts_items():
    items = curate.parse_rss(SAMPLE_RSS)
    assert len(items) == 2
    assert items[0]["title"] == "New 777X milestone"
    assert items[0]["url"] == "https://ex.com/a"


def test_select_reactionable_filters_and_limits():
    raw = [
        {"title": "ok", "summary": "s", "url": "https://ex.com/a", "date": ""},
        {"title": "", "summary": "no title", "url": "https://ex.com/b", "date": ""},
        {"title": "dupe", "summary": "s", "url": "https://ex.com/a", "date": ""},
    ]
    out = curate.select_reactionable(raw, limit=5)
    assert len(out) == 1
    assert out[0]["url"] == "https://ex.com/a"
