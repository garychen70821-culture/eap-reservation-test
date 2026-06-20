from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen


SOURCE_PAGE = "https://www.tainan.gov.tw/News.aspx?n=4981&sms=13702"
TARGET_TEXT = "市徽JPG圖檔"
OUTPUT = Path("assets") / "logos" / "tainan-city-logo.jpg"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125 Safari/537.36",
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_href = ""
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            values = {key.lower(): value or "" for key, value in attrs}
            self.current_href = values.get("href", "")

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if self.current_href and text:
            self.links.append((text, self.current_href))

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self.current_href = ""


def fetch(url: str) -> bytes:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=20) as response:
        return response.read()


def main() -> int:
    html = fetch(SOURCE_PAGE).decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    logo_href = next((href for text, href in parser.links if TARGET_TEXT in text), "")
    if not logo_href:
        raise RuntimeError(f"Cannot find download link for {TARGET_TEXT}")

    logo_url = urljoin(SOURCE_PAGE, logo_href)
    data = fetch(logo_url)
    if len(data) < 1024:
        raise RuntimeError(f"Downloaded file is too small: {len(data)} bytes")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(data)
    print(f"{OUTPUT.as_posix()} <- {logo_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
