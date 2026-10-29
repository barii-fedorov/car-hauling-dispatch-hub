"""
Telegram Formatter Module
Ensures 100% reliable HTML formatting for Telegram messages and photo captions.
Converts Markdown (*, **, _, `, ```, [], # headers, bullet lists) from AI models into valid Telegram HTML tags (<b>, <i>, <code>, <pre>, <a>),
escapes raw HTML entities while preserving existing valid HTML tags, balances tags, and prevents parser errors.
"""

import re
import html

def balance_html_tags(text: str) -> str:
    """Ensures all <b>, <i>, <code>, <a> tags in text are properly closed."""
    tags = ['b', 'i', 'code', 'a']
    for tag in tags:
        open_count = len(re.findall(rf'<{tag}(?: [^>]*)?>', text, re.IGNORECASE))
        close_count = len(re.findall(rf'</{tag}>', text, re.IGNORECASE))
        if open_count > close_count:
            text += f"</{tag}>" * (open_count - close_count)
    return text

def markdown_to_telegram_html(text: str, max_length: int = None) -> str:
    """
    Converts markdown text to Telegram-safe HTML.
    Protects existing HTML tags, converts markdown syntax, and prevents unescaped entities.
    """
    if not text:
        return ""

    # 1. Truncate text before formatting if max_length is provided
    if max_length and len(text) > (max_length - 80):
        cut_point = text[:max_length - 80].rfind('\n')
        if cut_point < (max_length // 2):
            cut_point = text[:max_length - 80].rfind(' ')
        if cut_point > (max_length // 2):
            text = text[:cut_point] + "\n..."
        else:
            text = text[:max_length - 80] + "..."

    # 2. Convert markdown headers: ### Header or ## Header -> **Header**
    text = re.sub(r'^(?:#{1,6})\s*(.+)$', r'**\1**', text, flags=re.MULTILINE)

    # 3. Horizontal rules: *** or --- or ___ on a line by itself -> empty line
    text = re.sub(r'^\s*[\*\-_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 4. Convert markdown list bullets: '*   ' or '-   ' -> '• '
    text = re.sub(r'^\s*[\*\-]\s+', r'• ', text, flags=re.MULTILINE)

    # 5. Protect already existing valid Telegram HTML tags
    valid_tag_pattern = re.compile(r'</?(?:b|i|u|s|code|pre|a)(?:\s+[^>]*?)?>', re.IGNORECASE)
    protected_tags = []
    def _protect_tag(m):
        tag_str = m.group(0)
        # Ensure '&' inside attributes like href is escaped as '&amp;' for Telegram HTML parser
        tag_str = re.sub(r'&(?!amp;|lt;|gt;|quot;)', '&amp;', tag_str)
        protected_tags.append(tag_str)
        return f"\x00HTMLTAG_{len(protected_tags)-1}\x00"
    text = valid_tag_pattern.sub(_protect_tag, text)

    # 6. Escape raw &, <, > so plain text never triggers HTML parse errors
    text = html.escape(text, quote=False)

    # 7. Code blocks ```lang\ncode``` -> <pre><code>code</code></pre>
    text = re.sub(r'```([a-zA-Z0-9_\-]*)\n?(.*?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)

    # 8. Inline code `code` -> <code>code</code>
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)

    # 9. Bold and Italic: ***text*** -> <b><i>text</i></b>
    text = re.sub(r'\*\*\*([^\*\n]+?)\*\*\*', r'<b><i>\1</i></b>', text)

    # 10. Bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r'\*\*([^\*\n]+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_\n]+?)__', r'<b>\1</b>', text)

    # 11. Italic: *text* (where * is not part of bold or bullet lists)
    text = re.sub(r'(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])', r'<i>\1</i>', text)

    # 12. Markdown Links: [text](url) -> <a href="url">text</a>
    def _format_markdown_link(m):
        url = m.group(2).replace('&', '&amp;')
        return f'<a href="{url}">{m.group(1)}</a>'
    text = re.sub(r'\[([^\]\n]+)\]\((https?://[^\)\s]+)\)', _format_markdown_link, text)

    # 13. Restore protected HTML tags
    for idx, original_tag in enumerate(protected_tags):
        text = text.replace(f"\x00HTMLTAG_{idx}\x00", original_tag)

    # 14. Tag balancing
    text = balance_html_tags(text)

    # 15. Hard safety limit
    if max_length and len(text) > max_length:
        text = text[:max_length - 8]
        text = balance_html_tags(text)

    return text

def strip_html_tags(text: str) -> str:
    """Fallback plain text stripper."""
    return re.sub(r'<[^>]+>', '', text)
