import re
import markdown
from markdown.extensions import Extension
from markdown.extensions.codehilite import CodeHiliteExtension
from pygments.formatters import HtmlFormatter


def convert_relative_url(url, github_base_url=None):
    if not github_base_url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("./"):
        return f"{github_base_url}/{url[2:]}"
    elif url.startswith("../"):
        return f"{github_base_url}/{url.lstrip('../')}"
    elif url.startswith("/"):
        return f"{github_base_url}{url}"
    elif not "://" in url and not url.startswith("#"):
        return f"{github_base_url}/{url}"
    return url


def render_markdown(content, github_base_url=None):
    # Clean up encoding issues
    html = (
        content.replace("â", "")
        .replace("â€", '"')
        .replace("â€œ", '"')
        .replace("â€™", "'")
        .replace("â€¢", "•")
        .replace('â€"', "—")
        .replace("â€“", "–")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    html = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", html)

    # Markdown conversion with code highlighting
    md = markdown.Markdown(
        extensions=[
            "tables",
            "fenced_code",
            CodeHiliteExtension(linenums=True, guess_lang=False, css_class="highlight"),
        ]
    )
    html = md.convert(html)

    # Inline code styling
    html = re.sub(
        r"<code>([^<\n]+)</code>",
        r'<code class="bg-gray-800 text-orange-300 px-2 py-1 rounded text-sm font-mono border border-gray-700">\1</code>',
        html,
    )

    # Headers
    html = re.sub(
        r"<h1>(.*?)</h1>",
        r'<h1 class="text-2xl font-bold mb-4 text-white border-b border-gray-700 pb-2">\1</h1>',
        html,
    )
    html = re.sub(
        r"<h2>(.*?)</h2>",
        r'<h2 class="text-xl font-semibold mb-3 text-white/90 mt-6">\1</h2>',
        html,
    )
    html = re.sub(
        r"<h3>(.*?)</h3>",
        r'<h3 class="text-lg font-medium mb-2 text-white/80 mt-4">\1</h3>',
        html,
    )
    html = re.sub(
        r"<h4>(.*?)</h4>",
        r'<h4 class="text-base font-medium mb-2 text-white/70 mt-3">\1</h4>',
        html,
    )

    # Bold and italics
    html = re.sub(
        r"<strong>(.*?)</strong>",
        r'<strong class="font-semibold text-white">\1</strong>',
        html,
    )
    html = re.sub(
        r"<em>(.*?)</em>",
        r'<em class="italic text-white/90">\1</em>',
        html,
    )

    # Images
    def img_replacer(match):
        alt, src = match.group(1), match.group(2)
        full_src = convert_relative_url(src, github_base_url)
        return f'<img src="{full_src}" alt="{alt}" class="max-w-full h-auto rounded-lg border border-gray-700 my-4 mx-auto block" />'

    html = re.sub(r'<img alt="([^"]*)" src="([^"]*)" ?/?>', img_replacer, html)

    # Links
    def link_replacer(match):
        text, url = match.group(1), match.group(2)
        full_url = convert_relative_url(url, github_base_url)
        return f'<a href="{full_url}" target="_blank" class="text-orange-400 hover:text-orange-300 underline transition-colors">{text}</a>'

    html = re.sub(r'<a href="([^"]+)">(.*?)</a>', lambda m: link_replacer(m), html)

    # Lists (add classes)
    html = re.sub(
        r"<ul>",
        '<ul class="my-3 space-y-1 list-disc pl-6">',
        html,
    )
    html = re.sub(
        r"<ol>",
        '<ol class="my-3 space-y-1 list-decimal pl-6">',
        html,
    )
    html = re.sub(
        r"<li>",
        '<li class="text-white/80 mb-1 ml-6">',
        html,
    )

    # Tables
    html = re.sub(
        r"<table>",
        '<div class="overflow-x-auto my-6"><table class="min-w-full bg-gray-800/20 border border-gray-700 rounded-lg overflow-hidden">',
        html,
    )
    html = re.sub(
        r"</table>",
        "</table></div>",
        html,
    )
    html = re.sub(
        r"<thead>",
        '<thead class="bg-gray-800/40">',
        html,
    )
    html = re.sub(
        r"<th>",
        '<th class="px-4 py-3 text-left text-sm font-medium text-white/90 border-b border-gray-600">',
        html,
    )
    html = re.sub(
        r"<td>",
        '<td class="px-4 py-3 text-sm text-white/80 border-b border-gray-700/50">',
        html,
    )
    html = re.sub(
        r"<tr>",
        '<tr class="hover:bg-gray-800/30 transition-colors">',
        html,
    )

    # Paragraphs
    html = re.sub(
        r"<p>(.*?)</p>",
        r'<p class="text-white/70 mb-4 leading-relaxed">\1</p>',
        html,
    )

    # Add pygments CSS for code highlighting
    pygments_css = HtmlFormatter(style="monokai").get_style_defs(".highlight")
    style_block = f"<style>{pygments_css}</style>"

    return style_block + html
