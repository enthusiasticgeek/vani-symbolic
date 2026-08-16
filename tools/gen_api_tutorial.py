#!/usr/bin/env python3
r"""Generate an mdBook API-reference tutorial from this package's own
source, in the tutorials/ directory (same mdBook layout vani-compiler's
own tutorials/ uses, so `mdbook build tutorials/` + GitHub Pages just
works with no per-repo tooling changes).

Ecosystem-wide "publish a tutorial explaining every function, with a
real example" CI idea, rolled out to every vani-* package. Mostly
mechanical, not hand-authored prose: vāṇी has no formal doc-comment
syntax and no `vanic doc` extractor as of this writing, so per-function
text is EXTRACTED from the source, verbatim, not invented:

  1. The plain `//` comment block immediately preceding each `fn`
     (this package's own existing informal doc-comment convention --
     confirmed present above nearly every function in src/lib.vani).
     Skips over `#[attribute]` lines between the comment and the `fn`.
  2. The first real call site for that function name found in tests/
     or examples/ (tests searched first, since they're closer to
     "ground truth" usage) -- a single source line, not synthesized.

A function with neither is rendered honestly as a gap ("no comment
above this function" / "no usage example found"), not papered over --
the point is to surface real documentation debt, not manufacture the
appearance of completeness.

The one deliberate exception to "extract, don't invent": an optional
tools/tutorial_extras.json sidecar, hand-authored ONCE per package
(like book.toml -- scaffolded, not regenerated), supplying:

  - "why_use_this": a short paragraph explaining what real problem the
    package solves and when to reach for it -- the one thing a bare
    signature+example reference genuinely can't answer on its own.
    Rendered on the index page.
  - "math_notes": a {function_name: LaTeX string} map for the
    functions whose behavior is naturally a formula (e.g. a sparse
    matrix-vector product, a numerical-integration rule) -- authored
    by reading the actual algorithm, not invented notation. Rendered
    as a "**Math**" block under that function's section, using
    MathJax's \( \) / \[ \] delimiters (book.toml enables
    mathjax-support). Functions without an entry get no Math block --
    most functions (constructors, accessors, plumbing) don't need one.

    Author math_notes entries with NORMAL, single-backslash LaTeX
    (`\( y = Ax \)`, `\sum_{j}`, `\text{rows}`, `\,`, etc.) -- do NOT
    hand-double the backslashes. `escape_latex_for_markdown()` below
    does that mechanically at render time, because mdBook's CommonMark
    renderer otherwise silently strips a single backslash before any
    ASCII punctuation character (confirmed against a real build: `\(`
    in the source becomes bare `(` in the output, breaking MathJax,
    unless the generator doubles it first). Backslash-before-LETTER
    (`\sum`, `\text`, ...) is untouched by CommonMark either way.

Regenerate with:
    python3 tools/gen_api_tutorial.py

Usage: run from the package root (reads vani.toml's [package].entry).
Writes tutorials/src/api_reference.md, tutorials/src/index.md,
tutorials/src/SUMMARY.md, and tutorials/book.toml. Safe to re-run --
fully regenerates the three src/*.md files from current source state
each time (book.toml and tutorial_extras.json are scaffolded once and
left alone). Do not hand-edit the generated src/*.md files; edit the
// comments in src/lib.vani (or tutorial_extras.json for the two
hand-authored fields) and re-run.
"""

import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_package_meta():
    toml_path = os.path.join(ROOT, "vani.toml")
    with open(toml_path, "r", encoding="utf-8") as f:
        text = f.read()
    name = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M)
    version = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.M)
    entry = re.search(r'^\s*entry\s*=\s*"([^"]+)"', text, re.M)
    return {
        "name": name.group(1) if name else "package",
        "version": version.group(1) if version else "0.0.0",
        "entry": entry.group(1) if entry else "src/lib.vani",
    }


def preceding_comment_block(lines, decl_idx):
    """Walk upward from `decl_idx` (a `fn`/`struct` line), skipping
    #[attribute] lines, and collect the contiguous `//` comment block
    immediately above. Returns joined text or None."""
    i = decl_idx - 1
    while i >= 0 and lines[i].strip().startswith("#["):
        i -= 1
    comment_lines = []
    while i >= 0 and lines[i].strip().startswith("//"):
        comment_lines.append(lines[i].strip()[2:].strip())
        i -= 1
    comment_lines.reverse()
    # Drop a leading section-banner line (e.g. "── Construction ──...")
    # if present -- it's a file-organization header, not a
    # per-function description.
    while comment_lines and re.match(r"^[─\-=]{3,}", comment_lines[0]):
        comment_lines.pop(0)
    text = "\n".join(comment_lines).strip()
    return text if text else None


def extract_functions(src_path):
    with open(src_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    fns = []
    fn_start_re = re.compile(r"^fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    for idx, line in enumerate(lines):
        m = fn_start_re.match(line)
        if not m:
            continue
        name = m.group(1)
        if name.startswith("_"):
            continue  # underscore-prefixed = private-by-convention
        # Join lines until the opening `{` of the body (handles
        # multi-line signatures defensively, even though every
        # signature in this package today is single-line).
        sig_lines = []
        j = idx
        while j < len(lines):
            sig_lines.append(lines[j].rstrip("\n"))
            if "{" in lines[j]:
                break
            j += 1
        sig_text = "\n".join(sig_lines)
        sig_text = sig_text[: sig_text.rfind("{")].rstrip()
        fns.append(
            {
                "name": name,
                "signature": sig_text,
                "doc": preceding_comment_block(lines, idx),
                "line": idx + 1,
            }
        )
    return fns


def extract_structs(src_path):
    with open(src_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    structs = []
    struct_re = re.compile(r"^struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")
    for idx, line in enumerate(lines):
        m = struct_re.match(line)
        if not m:
            continue
        name = m.group(1)
        body = []
        j = idx
        while j < len(lines):
            body.append(lines[j].rstrip("\n"))
            if "}" in lines[j] and j > idx:
                break
            j += 1
        structs.append(
            {
                "name": name,
                "body": "\n".join(body),
                "doc": preceding_comment_block(lines, idx),
            }
        )
    return structs


def read_extras():
    """Optional hand-authored sidecar -- see module docstring. Missing
    file is fine (returns empty defaults); malformed JSON is a hard
    error (fail loud on a typo rather than silently dropping content)."""
    path = os.path.join(ROOT, "tools", "tutorial_extras.json")
    if not os.path.isfile(path):
        return {"why_use_this": None, "math_notes": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "why_use_this": data.get("why_use_this"),
        "math_notes": data.get("math_notes", {}),
    }


# CommonMark's escapable-ASCII-punctuation set (pulldown-cmark, mdBook's
# markdown engine, follows this). A backslash immediately before one of
# these is silently CONSUMED by the renderer -- the backslash disappears
# from the output HTML, only the punctuation character survives -- unless
# the source doubles it. LaTeX leans on backslash+punctuation constantly
# (`\(`, `\)`, `\[`, `\]`, `\,`, `\{`, `\}`, `\_`, ...), so hand-authored
# `math_notes` in tutorial_extras.json are written with NORMAL single-
# backslash LaTeX and this function mechanically doubles the punctuation-
# preceding ones at render time -- backslash-before-LETTER (`\sum`,
# `\text`, `\times`, `\cdot`, `\min`, `\in`, ...) is untouched by
# CommonMark and left alone. Confirmed empirically against a real mdBook
# build: single backslash before `(` is stripped; double survives as a
# single literal backslash in the output, which is what MathJax expects.
_MD_PUNCT = re.escape(r"""!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~""")
_ESCAPE_FOR_MARKDOWN_RE = re.compile(r"\\(?=[" + _MD_PUNCT + r"])")


def escape_latex_for_markdown(s):
    return _ESCAPE_FOR_MARKDOWN_RE.sub(r"\\\\", s)


def find_example(fn_name):
    """First real call site for `fn_name` in tests/ then examples/,
    tests searched first as closer-to-ground-truth usage. Returns
    (relative_file, line_text) or None."""
    call_re = re.compile(r"\b" + re.escape(fn_name) + r"\s*\(")
    for subdir in ("tests", "examples"):
        pattern = os.path.join(ROOT, subdir, "*.vani")
        for path in sorted(glob.glob(pattern)):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if call_re.search(line):
                        rel = os.path.relpath(path, ROOT)
                        return rel, line.strip()
    return None


GENERATED_NOTE = (
    "<!-- AUTO-GENERATED by tools/gen_api_tutorial.py -- do not hand-edit.\n"
    "     Edit the // comments in {entry} (or the tests/examples that\n"
    "     supply each usage example) and re-run the generator instead. -->\n"
)


def render_signature_block(name, sig):
    return "```vani\n{}\n```\n".format(sig)


def render_function_section(fn, math_notes):
    out = ["## `{}`\n".format(fn["name"])]
    out.append(render_signature_block(fn["name"], fn["signature"]))
    if fn["doc"]:
        out.append(fn["doc"] + "\n")
    else:
        out.append(
            "> _No `//` comment found immediately above this function "
            "in the source -- undocumented._\n"
        )
    if fn["name"] in math_notes:
        out.append("**Math**:\n")
        out.append(escape_latex_for_markdown(math_notes[fn["name"]]) + "\n")
    example = find_example(fn["name"])
    if example:
        rel, line_text = example
        out.append(
            "**Example** (from [`{rel}`](https://github.com/{gh}/blob/main/{rel})):\n".format(
                rel=rel, gh="{gh_slug}"
            )
        )
        out.append("```vani\n{}\n```\n".format(line_text))
    else:
        out.append(
            "> _No usage example found in `tests/` or `examples/` yet -- "
            "a real documentation gap, not hidden._\n"
        )
    return "\n".join(out) + "\n"


def render_struct_section(st):
    out = ["## `struct {}`\n".format(st["name"])]
    out.append("```vani\n{}\n```\n".format(st["body"]))
    if st["doc"]:
        out.append(st["doc"] + "\n")
    return "\n".join(out) + "\n"


def main():
    meta = read_package_meta()
    entry_path = os.path.join(ROOT, meta["entry"])
    if not os.path.isfile(entry_path):
        print("error: entry file not found: {}".format(entry_path), file=sys.stderr)
        sys.exit(1)

    # Best-effort GitHub slug from git remote, for example source links.
    gh_slug = "enthusiasticgeek/{}".format(
        "vani-{}".format(meta["name"]) if not meta["name"].startswith("vani-") else meta["name"]
    )

    fns = extract_functions(entry_path)
    structs = extract_structs(entry_path)
    extras = read_extras()

    n_documented = sum(1 for f in fns if f["doc"])
    n_with_example = sum(1 for f in fns if find_example(f["name"]))

    src_dir = os.path.join(ROOT, "tutorials", "src")
    os.makedirs(src_dir, exist_ok=True)

    note = GENERATED_NOTE.format(entry=meta["entry"])

    # --- api_reference.md ---
    parts = [note, "# API Reference\n"]
    parts.append(
        "Auto-generated from `{}`, `tests/`, and `examples/` -- every "
        "function and struct is listed in source declaration order, "
        "each with its signature, its preceding `//` comment (if any), "
        "and a real usage line pulled from this package's own tests or "
        "examples (if any). Coverage this run: **{}/{} functions have "
        "a comment**, **{}/{} have a found usage example**.\n".format(
            meta["entry"], n_documented, len(fns), n_with_example, len(fns)
        )
    )
    if structs:
        parts.append("## Types\n")
        for st in structs:
            parts.append(render_struct_section(st))
    parts.append("## Functions\n")
    for fn in fns:
        section = render_function_section(fn, extras["math_notes"]).replace(
            "{gh_slug}", gh_slug
        )
        parts.append(section)
    with open(os.path.join(src_dir, "api_reference.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))

    # --- index.md ---
    index = [note, "# {} v{}\n".format(meta["name"], meta["version"])]
    if extras["why_use_this"]:
        index.append("## Why use this package\n")
        index.append(extras["why_use_this"] + "\n")
    else:
        index.append(
            "> _No `tools/tutorial_extras.json` `why_use_this` entry yet "
            "for this package -- see the README instead._\n"
        )
    index.append(
        "This is an auto-generated API reference for the `{}` vāṇी "
        "package -- every public function's signature paired with a "
        "real usage example pulled from this package's own tests and "
        "examples, generated by `tools/gen_api_tutorial.py` on every "
        "push to `main`.\n".format(meta["name"])
    )
    index.append("See [API Reference](api_reference.md) for every function.\n")
    index.append("Source: <https://github.com/{}>\n".format(gh_slug))
    with open(os.path.join(src_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(index))

    # --- SUMMARY.md ---
    summary = [
        note,
        "# Summary\n",
        "- [{}](index.md)".format(meta["name"]),
        "- [API Reference](api_reference.md)",
        "",
    ]
    with open(os.path.join(src_dir, "SUMMARY.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary))

    # --- book.toml (only written if missing -- config isn't
    # regenerated content, unlike the three files above). ---
    book_toml_path = os.path.join(ROOT, "tutorials", "book.toml")
    if not os.path.isfile(book_toml_path):
        book_toml = """# mdBook configuration for the {name} API-reference tutorial.
# Auto-scaffolded once by tools/gen_api_tutorial.py; edit freely --
# unlike src/*.md, this file is NOT regenerated on subsequent runs.
[book]
title = "{name} — API Reference"
authors = ["vāṇी contributors"]
description = "Auto-generated function-by-function API reference for the {name} vāṇी package."
language = "en"
src = "src"

[output.html]
default-theme = "rust"
preferred-dark-theme = "navy"
git-repository-url = "https://github.com/{gh_slug}"
edit-url-template = "https://github.com/{gh_slug}/edit/main/tutorials/{{path}}"
# LaTeX math rendering via MathJax, for packages whose comments use
# math notation (e.g. \\\\(A x = b\\\\) or \\\\[ ... \\\\] blocks).
mathjax-support = true

[output.html.search]
enable = true
""".format(name=meta["name"], gh_slug=gh_slug)
        with open(book_toml_path, "w", encoding="utf-8") as f:
            f.write(book_toml)

    print(
        "generated tutorials/src/{{index,api_reference,SUMMARY}}.md -- "
        "{} functions ({} documented, {} with an example, {} with a math "
        "note), {} structs, why_use_this: {}".format(
            len(fns),
            n_documented,
            n_with_example,
            len(extras["math_notes"]),
            len(structs),
            "yes" if extras["why_use_this"] else "MISSING",
        )
    )


if __name__ == "__main__":
    main()
