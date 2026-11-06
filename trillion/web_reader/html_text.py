"""
html_text — turn a page's HTML into plain readable text plus its links, using
the stdlib parser (no new dependency). Script, style and head content never
reach the model; links are resolved to full addresses so the allowlist can take
them.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

from .urls import normalize_url, UrlError

_SKIP = {"script", "style", "noscript", "template", "svg", "head"}
_BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "header", "footer",
          "ul", "ol", "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
_MAX_LINKS = 40


class _Parser(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.title = ""
        self._skip = 0
        self._in_title = False
        self._chunks: list[str] = []
        self.links: list[str] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in _BLOCK:
            self._chunks.append("\n")
        if tag == "a" and self._skip == 0:
            for k, v in attrs:
                if k == "href" and v:
                    self._add_link(v)

    def handle_endtag(self, tag):
        if tag in _SKIP and self._skip > 0:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in _BLOCK:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
            return
        if self._skip:
            return
        self._chunks.append(data)

    def _add_link(self, href):
        if len(self.links) >= _MAX_LINKS:
            return
        try:
            u = normalize_url(urljoin(self.base, href))
        except UrlError:
            return
        if u not in self._seen:
            self._seen.add(u)
            self.links.append(u)

    @property
    def text(self) -> str:
        t = "".join(self._chunks)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r"\n[ \t]*", "\n", t)
        t = re.sub(r"\n{2,}", "\n", t)
        return t.strip()


def html_to_text(html: str, base: str) -> tuple[str, str, list[str]]:
    """Return (title, text, links) for a page. Never raises."""
    p = _Parser(base)
    try:
        p.feed(html or "")
    except Exception:
        pass
    return p.title.strip(), p.text, p.links
