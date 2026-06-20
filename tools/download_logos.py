from __future__ import annotations

import re
import ssl
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


CENTERS = [
    ("natureiswell", "自然就好心理諮商所", "https://www.natureiswell.com.tw/"),
    ("hopelight", "看見光亮心理諮商所", "https://www.hopelight.com.tw/"),
    ("eosgrace", "曙光角落心理諮商所", "https://www.eosgrace.com/"),
    ("togetherwithheart", "這會心理諮商所", "https://togetherwithheart.com/"),
    ("kxmind", "寬欣心理治療所", "https://www.kxmind.com/"),
    ("kxmind2", "芯寬欣心理治療所", "https://www.kxmind.com/"),
    ("goodday", "日安心理治療所", "https://good-day-psy.blogspot.com/"),
    ("up3", "上善心理治療所", "http://www.up3.url.tw/"),
    ("cheerpsy", "慈恩心理治療所", "https://www.cheerpsy.com/"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept": "text/html,image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

EXT_BY_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.meta_images: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        if tag.lower() == "link" and attr.get("href"):
            rel = attr.get("rel", "").lower()
            if "icon" in rel or "apple-touch-icon" in rel:
                self.links.append(attr)
        if tag.lower() == "img" and attr.get("src"):
            self.images.append(attr)
        if tag.lower() == "meta":
            prop = (attr.get("property") or attr.get("name") or "").lower()
            if prop in {"og:image", "twitter:image"} and attr.get("content"):
                self.meta_images.append(attr["content"])


def fetch(url: str, timeout: int = 12) -> tuple[bytes, str]:
    context = ssl.create_default_context()
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=timeout, context=context) as response:
        return response.read(), response.headers.get("Content-Type", "").split(";")[0].lower()


def html_text(url: str) -> str:
    data, _ = fetch(url)
    return data.decode("utf-8", errors="replace")


def score_image(attrs: dict[str, str], center_name: str) -> int:
    haystack = " ".join(attrs.get(key, "") for key in ("src", "alt", "title", "class", "id")).lower()
    score = 0
    for token in ("logo", "brand", "mark", "商標", "識別", "諮商所", "治療所"):
        if token.lower() in haystack:
            score += 40
    for piece in re.split(r"[心理諮商治療所\s]+", center_name):
        if piece and piece in haystack:
            score += 25
    if attrs.get("width", "").isdigit() and attrs.get("height", "").isdigit():
        width, height = int(attrs["width"]), int(attrs["height"])
        if 40 <= width <= 500 and 40 <= height <= 500:
            score += 15
    return score


def candidate_urls(site_url: str, center_name: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    try:
        parser = AssetParser()
        parser.feed(html_text(site_url))
        for image in parser.images:
            score = score_image(image, center_name)
            if score > 0:
                candidates.append((score + 100, urljoin(site_url, image["src"])))
        for link in parser.links:
            rel = link.get("rel", "").lower()
            score = 80 if "apple-touch-icon" in rel else 65
            candidates.append((score, urljoin(site_url, link["href"])))
        for image_url in parser.meta_images:
            candidates.append((45, urljoin(site_url, image_url)))
    except (URLError, HTTPError, TimeoutError, ssl.SSLError) as exc:
        print(f"[warn] cannot parse {site_url}: {exc}", file=sys.stderr)

    parsed = urlparse(site_url)
    candidates.extend(
        [
            (50, f"{parsed.scheme}://{parsed.netloc}/favicon.ico"),
            (45, f"{parsed.scheme}://{parsed.netloc}/apple-touch-icon.png"),
        ]
    )

    unique: dict[str, int] = {}
    for score, url in candidates:
        if url.startswith("data:"):
            continue
        unique[url] = max(score, unique.get(url, 0))
    return [url for url, _ in sorted(unique.items(), key=lambda item: item[1], reverse=True)]


def extension_for(url: str, content_type: str) -> str:
    if content_type in EXT_BY_TYPE:
        return EXT_BY_TYPE[content_type]
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".img"


def save_logo(center_id: str, center_name: str, site_url: str, out_dir: Path) -> str | None:
    for url in candidate_urls(site_url, center_name):
        try:
            data, content_type = fetch(url)
            if len(data) < 100:
                continue
            if not (content_type.startswith("image/") or Path(urlparse(url).path).suffix.lower() in {".ico", ".png", ".jpg", ".jpeg", ".webp", ".svg"}):
                continue
            ext = extension_for(url, content_type)
            target = out_dir / f"{center_id}{ext}"
            target.write_bytes(data)
            print(f"{center_id}: {target.as_posix()} <- {url}")
            return target.name
        except (URLError, HTTPError, TimeoutError, ssl.SSLError, OSError) as exc:
            print(f"[warn] cannot fetch {url}: {exc}", file=sys.stderr)
    print(f"[warn] no logo saved for {center_id}", file=sys.stderr)
    return None


def main() -> int:
    out_dir = Path("assets") / "logos"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = []
    for center_id, center_name, site_url in CENTERS:
        filename = save_logo(center_id, center_name, site_url, out_dir)
        if filename:
            manifest.append(f"{center_id}=assets/logos/{filename}")
    (out_dir / "manifest.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
