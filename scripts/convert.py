#!/usr/bin/env python3
"""Convert one upstream HTML page to mdBook-flavored Markdown.

Usage: scripts/convert.py <slug>
Reads raw-html/<slug>.html, writes src/<slug>.md.
Run with the project venv: .venv/bin/python scripts/convert.py <slug>
"""
import subprocess
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent


def clean(soup: BeautifulSoup) -> BeautifulSoup:
    article = soup.find("article")
    if not article:
        sys.exit("no <article> found")

    # Strip self-link wrappers inside headings.
    for h in article.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        a = h.find("a")
        if a is not None:
            a.replace_with(*a.contents) if a.contents else a.decompose()

    # Drop word-break opportunity hints.
    for w in article.find_all("wbr"):
        w.decompose()

    # Tag bare <pre> blocks with a language so pandoc emits fenced code blocks
    # with syntax highlighting. Heuristic: compiler diagnostics start with
    # "error[" / "error:" / "warning:"; everything else is treated as Rust.
    for pre in article.find_all("pre"):
        if pre.find("code"):
            continue
        text = pre.get_text("", strip=False).lstrip()
        lang = "text" if text.startswith(("error[", "error:", "warning:")) else "rust"
        code = soup.new_tag("code")
        code["class"] = [f"language-{lang}"]
        for child in list(pre.contents):
            code.append(child.extract())
        pre.append(code)

    # Unwrap structural <section> wrappers (keep their children). Pandoc would
    # otherwise emit them as <div class="section"> in the markdown.
    for s in article.find_all("section"):
        s.unwrap()

    # Rewrite admonitions into a single semantic div with a labeled paragraph.
    for d in article.find_all("div", class_="note"):
        label = d.get("aria-label", "note").capitalize()
        text_div = d.find("div", class_="text")
        new = soup.new_tag("div")
        new["class"] = ["admonition", f"admonition-{label.lower()}"]
        label_p = soup.new_tag("p")
        label_p["class"] = ["admonition-label"]
        strong = soup.new_tag("strong")
        strong.string = label
        label_p.append(strong)
        new.append(label_p)
        if text_div is not None:
            for child in list(text_div.contents):
                new.append(child.extract() if hasattr(child, "extract") else child)
        d.replace_with(new)

    return article


def to_markdown(html: str) -> str:
    proc = subprocess.run(
        ["pandoc", "-f", "html", "-t", "gfm", "--wrap=preserve"],
        input=html, capture_output=True, text=True, check=True,
    )
    return proc.stdout


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: convert.py <slug>")
    slug = sys.argv[1]
    src = ROOT / "raw-html" / f"{slug}.html"
    dst = ROOT / "src" / f"{slug}.md"
    soup = BeautifulSoup(src.read_text(), "html.parser")
    article = clean(soup)
    md = to_markdown(str(article))
    dst.write_text(md)
    print(f"wrote {dst} ({len(md)} bytes, {md.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
