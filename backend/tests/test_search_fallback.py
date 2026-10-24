"""Web search: the lite page as a fallback, its parsing, and the short cache (no network)."""
import asyncio
import unittest
from unittest.mock import patch

from app.tools.web import sources

LITE_PAGE = """
<tr><td>1.&nbsp;</td><td>
  <a rel="nofollow" href="https://open.spotify.com/track/abc" class='result-link'>Kesariya - song by <b>Pritam</b> - Spotify</a>
</td></tr>
<tr><td>&nbsp;</td><td class='result-snippet'>Listen to <b>Kesariya</b> on Spotify.</td></tr>
<tr><td>2.&nbsp;</td><td>
  <a rel="nofollow" href="https://duckduckgo.com/y.js?ad=1" class='result-link'>An ad</a>
</td></tr>
<tr><td>3.&nbsp;</td><td>
  <a rel="nofollow" href="https://en.wikipedia.org/wiki/Kesariya" class='result-link'>Kesariya - Wikipedia</a>
</td></tr>
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeClient:
    def __init__(self, text):
        self.text = text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None):
        return FakeResponse(self.text)


def run(coro):
    return asyncio.run(coro)


class LiteTests(unittest.TestCase):
    def test_lite_page_is_parsed_without_ads(self):
        with patch.object(sources, "_client", lambda timeout: FakeClient(LITE_PAGE)):
            results = run(sources._search_lite("kesariya", 8))
        self.assertEqual([r["url"] for r in results], ["https://open.spotify.com/track/abc", "https://en.wikipedia.org/wiki/Kesariya"])
        self.assertEqual(results[0]["title"], "Kesariya - song by Pritam - Spotify")
        self.assertEqual(results[0]["snippet"], "Listen to Kesariya on Spotify.")


class FallbackAndCacheTests(unittest.TestCase):
    def setUp(self):
        sources._cache.clear()
        self.calls = []

    def engines(self, html_results, lite_results):
        async def html(query, limit):
            self.calls.append("html")
            return html_results

        async def lite(query, limit):
            self.calls.append("lite")
            return lite_results
        return patch.object(sources, "_search_html", html), patch.object(sources, "_search_lite", lite)

    def test_lite_is_used_only_when_the_main_page_is_empty(self):
        a, b = self.engines([{"url": "https://a"}], [{"url": "https://b"}])
        with a, b:
            self.assertEqual(run(sources.search("x"))[0]["url"], "https://a")
        self.assertEqual(self.calls, ["html"])
        sources._cache.clear()
        self.calls.clear()
        a, b = self.engines([], [{"url": "https://b"}])
        with a, b:
            self.assertEqual(run(sources.search("x"))[0]["url"], "https://b")
        self.assertEqual(self.calls, ["html", "lite"])

    def test_results_are_cached_but_empty_answers_are_not(self):
        a, b = self.engines([{"url": "https://a"}], [])
        with a, b:
            run(sources.search("Same Question"))
            run(sources.search("same question "))
        self.assertEqual(self.calls, ["html"])
        self.calls.clear()
        a, b = self.engines([], [])
        with a, b:
            run(sources.search("nothing"))
            run(sources.search("nothing"))
        self.assertEqual(self.calls, ["html", "lite", "html", "lite"])

    def test_cache_expires(self):
        a, b = self.engines([{"url": "https://a"}], [])
        with a, b:
            run(sources.search("q"))
            key = next(iter(sources._cache))
            sources._cache[key] = (sources._cache[key][0] - 601, sources._cache[key][1])
            run(sources.search("q"))
        self.assertEqual(self.calls, ["html", "html"])


if __name__ == "__main__":
    unittest.main()
