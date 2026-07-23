"""HTML parser edge cases."""
from __future__ import annotations

from bs4 import BeautifulSoup

from app.services.html_parser_service import HtmlParserService


def test_strip_noise_handles_tags_with_none_attrs():
    soup = BeautifulSoup("<html><body><div class='menu'>nav</div></body></html>", "lxml")
    broken = soup.new_tag("span")
    broken.attrs = None
    soup.body.append(broken)

    HtmlParserService._sanitize_broken_tags(soup)
    HtmlParserService._strip_noise(soup)

    assert soup.find("div", class_="menu") is None


def test_parse_malformed_class_attr_does_not_crash():
    html = """
    <html><head><title>Test page</title></head>
    <body><main><h1>Hello</h1><p>Body text here.</p></main></body></html>
    """
    soup = BeautifulSoup(html, "lxml")
    broken = soup.new_tag("div")
    broken.attrs = None
    soup.body.insert(0, broken)

    parsed = HtmlParserService().parse(str(soup), "https://example.com/test")
    assert "Hello" in parsed.main_content_text
    assert parsed.title == "Test page"
