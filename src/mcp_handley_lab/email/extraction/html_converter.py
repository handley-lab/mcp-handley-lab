"""HTML to Markdown conversion with link and structure preservation.

Conservative sanitization - only removes truly dangerous/useless elements.
"""

from bs4 import BeautifulSoup
from markdownify import markdownify


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to Markdown preserving links, tables, and structure.

    Uses markdownify for conversion after conservative sanitization.
    """
    if not html or not html.strip():
        return ""

    # Sanitize first
    sanitized = sanitize_html_minimal(html)

    # Convert to markdown with link preservation
    md = markdownify(
        sanitized,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )

    return md.strip()


def sanitize_html_minimal(html: str) -> str:
    """
    Conservative HTML sanitization.

    REMOVES (truly dangerous/useless):
    - script, style, noscript, meta, link, head
    - Hidden elements (display:none, visibility:hidden)
    - 1x1 tracking pixels

    PRESERVES (may contain legitimate content):
    - blockquote - quoted content
    - footer, nav - may have useful context
    - Unsubscribe links - useful metadata
    - Any element with visible text
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove truly dangerous/useless elements
    for tag in soup.find_all(["script", "style", "noscript", "meta", "link", "head"]):
        tag.decompose()

    # Remove hidden elements
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if any(
            hidden in style
            for hidden in [
                "display:none",
                "display: none",
                "visibility:hidden",
                "visibility: hidden",
            ]
        ):
            tag.decompose()

    # Remove 1x1 tracking pixels
    for img in soup.find_all("img"):
        width = img.get("width", "")
        height = img.get("height", "")
        if width == "1" and height == "1":
            img.decompose()

    # Return cleaned HTML
    return str(soup)
