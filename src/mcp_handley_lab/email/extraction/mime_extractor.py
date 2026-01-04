"""MIME part extraction with explicit iteration.

Never relies on get_body() alone - always walks the full MIME tree.
"""

from email.message import EmailMessage

from mcp_handley_lab.email.extraction.models import EmailPartInfo


def extract_mime_parts(
    msg: EmailMessage,
) -> tuple[str, str, list[EmailPartInfo], list[str]]:
    """
    Extract text/html content with explicit part iteration.

    Algorithm:
    1. Walk entire MIME tree, building parts_manifest
    2. Ignore parts with Content-Disposition: attachment (unless no other content)
    3. Ignore message/rfc822 (forwarded emails) - treat as attachment
    4. Ignore text/calendar - note in warnings if present
    5. For multipart/alternative: collect both plain and HTML
    6. Prefer text/plain that is inline and non-empty
    7. If no good plain, use text/html and convert
    8. If multiple text parts exist, prefer first inline

    Returns:
        tuple of (plain_content, html_content, parts_manifest, warnings)
        - Both plain and html can be non-empty
        - Never returns (empty, empty) unless email truly has no body
    """
    parts_manifest: list[EmailPartInfo] = []
    warnings: list[str] = []

    # Candidate body parts
    plain_parts: list[tuple[int, str]] = []  # (part_index, content)
    html_parts: list[tuple[int, str]] = []

    part_index = 0
    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = part.get_content_disposition() or ""
        filename = part.get_filename() or ""
        charset = part.get_content_charset() or "utf-8"

        # Build part info
        try:
            payload = part.get_payload(decode=True)
            size_bytes = len(payload) if payload else 0
        except Exception:
            size_bytes = 0

        part_info = EmailPartInfo(
            content_type=content_type,
            charset=charset,
            transfer_encoding=part.get("Content-Transfer-Encoding", ""),
            disposition=disposition,
            filename=filename,
            size_bytes=size_bytes,
            part_index=part_index,
            is_selected_body=False,
        )
        parts_manifest.append(part_info)

        # Skip multipart containers (they don't have content)
        if content_type.startswith("multipart/"):
            part_index += 1
            continue

        # Skip attachments (tracked via parts_manifest)
        # Only skip if explicitly marked as attachment, not just because it has a filename
        # Some broken clients add filename to inline body parts
        if disposition == "attachment":
            part_index += 1
            continue

        # Skip non-text parts with filenames (likely inline images/attachments)
        if filename and not content_type.startswith("text/"):
            part_index += 1
            continue

        # Skip forwarded messages
        if content_type == "message/rfc822":
            part_index += 1
            continue

        # Note calendar parts
        if content_type == "text/calendar":
            warnings.append("Calendar invitation present (text/calendar)")
            part_index += 1
            continue

        # Skip encrypted content
        if content_type in (
            "application/pkcs7-mime",
            "application/pgp-encrypted",
            "multipart/encrypted",
        ):
            warnings.append("Encrypted content not extracted")
            part_index += 1
            continue

        # Extract text content
        if content_type == "text/plain":
            content = _decode_part(part, charset, warnings)
            if content.strip():
                plain_parts.append((part_index, content))

        elif content_type == "text/html":
            content = _decode_part(part, charset, warnings)
            if content.strip():
                html_parts.append((part_index, content))

        part_index += 1

    # Concatenate all inline text parts (never silently lose content)
    # Multiple text parts are common in multipart/mixed (e.g., body + disclaimer)
    plain_content = ""
    html_content = ""
    selected_index = -1

    if plain_parts:
        # Concatenate all plain text parts with clear separation
        if len(plain_parts) == 1:
            selected_index, plain_content = plain_parts[0]
        else:
            # Multiple plain parts - concatenate with separator
            selected_index = plain_parts[0][0]  # Mark first as selected
            plain_content = "\n\n".join(content for _, content in plain_parts)
            if len(plain_parts) > 1:
                warnings.append(f"Concatenated {len(plain_parts)} text/plain parts")

    if html_parts:
        # Concatenate all HTML parts
        if len(html_parts) == 1:
            html_index, html_content = html_parts[0]
        else:
            html_index = html_parts[0][0]
            html_content = "\n\n".join(content for _, content in html_parts)
            if len(html_parts) > 1:
                warnings.append(f"Concatenated {len(html_parts)} text/html parts")

        if not plain_content:
            selected_index = html_index

    # Mark selected part (first part if multiple were concatenated)
    if selected_index >= 0 and selected_index < len(parts_manifest):
        parts_manifest[selected_index].is_selected_body = True

    return plain_content, html_content, parts_manifest, warnings


def _decode_part(part: EmailMessage, charset: str, warnings: list[str]) -> str:
    """Decode a MIME part with charset fallback."""
    try:
        return part.get_content()
    except (LookupError, UnicodeDecodeError) as e:
        # Charset fallback
        payload = part.get_payload(decode=True)
        if not payload:
            return ""

        for fallback_charset in ["utf-8", "latin-1", "cp1252"]:
            try:
                content = payload.decode(fallback_charset, errors="replace")
                warnings.append(
                    f"Charset fallback: declared={charset}, used={fallback_charset}"
                )
                return content
            except Exception:
                continue

        warnings.append(f"Failed to decode part: {e}")
        return ""
    except Exception as e:
        warnings.append(f"Error extracting content: {e}")
        return ""
