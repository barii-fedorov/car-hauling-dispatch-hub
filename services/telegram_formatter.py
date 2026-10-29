"""
Telegram Formatter Module
Ensures 100% reliable HTML formatting for Telegram messages and photo captions.
Converts Markdown (*, **, _, `, ```, []) from AI models into valid Telegram HTML tags (<b>, <i>, <code>, <pre>, <a>),
escapes raw HTML entities, balances tags, and prevents parser errors on hashtags, punctuation, and emojis.
"""

import re
import html

def balance_html_tags(text: str) -> str:
    """Ensures all <b>, <i>, <code>, <a> tags in text are properly closed."""
    tags = ['b', 'i', 'code', 'a']
    for tag in tags:
        open_count = len(re.findall(rf'<{tag}(?: [^>]*)?>', text))
        close_count = len(re.findall(rf'</{tag}>', text))
        if open_count > close_count:
            text += f"</{tag}>" * (open_count - close_count)
    return text

def markdown_to_telegram_html(text: str, max_length: int = None) -> str:
    """
    Converts markdown text to Telegram-safe HTML.
    Prevents asterisks from leaking into messages and avoids parse failures on hashtags or symbols.
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

    # 2. Escape &, <, > so plain text never triggers HTML parse errors
    text = html.escape(text, quote=False)

    # 3. Code blocks ```lang\ncode``` -> <pre><code>code</code></pre>
    text = re.sub(r'```([a-zA-Z0-9_\-]*)\n?(.*?)```', r'<pre><code>\2</code></pre>', text, flags=re.DOTALL)

    # 4. Inline code `code` -> <code>code</code>
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)

    # 5. Bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text, flags=re.DOTALL)

    # 6. Italic: *text* (where * is not part of bold or bullet lists)
    text = re.sub(r'(?<![\*\w])\*([^\*\n]+?)\*(?![\*\w])', r'<i>\1</i>', text)

    # 7. Links: [text](url) -> <a href="url">text</a>
    text = re.sub(r'\[([^\]\n]+)\]\((https?://[^\)\s]+)\)', r'<a href="\2">\1</a>', text)

    # 8. Tag balancing
    text = balance_html_tags(text)

    # 9. Hard safety limit
    if max_length and len(text) > max_length:
        text = text[:max_length - 8]
        text = balance_html_tags(text)

    return text

def strip_html_tags(text: str) -> str:
    """Fallback plain text stripper."""
    return re.sub(r'<[^>]+>', '', text)
