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

    # Collect all tags to remove (avoids mutation-during-iteration issues)
    to_remove = []

    # Dangerous/useless elements
    to_remove.extend(
        soup.find_all(["script", "style", "noscript", "meta", "link", "head"])
    )

    # Hidden elements
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if (
            "display:none" in style
            or "display: none" in style
            or "visibility:hidden" in style
            or "visibility: hidden" in style
        ):
            to_remove.append(tag)

    # 1x1 tracking pixels
    for img in soup.find_all("img"):
        if img.get("width") == "1" and img.get("height") == "1":
            to_remove.append(img)

    # Now decompose all at once
    for tag in to_remove:
        tag.decompose()

    return str(soup)
