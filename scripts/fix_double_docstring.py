#!/usr/bin/env python3
"""Merge duplicate leading docstrings; restore shebang + from __future__ order."""
from __future__ import annotations

import sys
from pathlib import Path


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    try:
        compile(text, str(path), "exec")
        return False
    except SyntaxError:
        pass

    lines = text.splitlines(keepends=True)
    shebang = ""
    i = 0
    doc_parts: list[str] = []
    comment_parts: list[str] = []

    while i < len(lines):
        s = lines[i].strip()
        if s.startswith("#!"):
            shebang = lines[i] if not shebang else shebang
            i += 1
            continue
        if s.startswith('"""') or s.startswith("'''"):
            quote = '"""' if '"""' in lines[i] else "'''"
            if s.count(quote) >= 2:
                doc_parts.append(s[3:-3].strip())
                i += 1
                continue
            buf = []
            while i < len(lines):
                buf.append(lines[i])
                if quote in lines[i] and lines[i].strip().endswith(quote) and len(buf) > 1 or (
                    quote in lines[i] and s.startswith(quote) and lines[i].count(quote) >= 2
                ):
                    break
                if quote in lines[i] and not s.startswith(quote):
                    break
                i += 1
            block = "".join(buf).strip()
            if block.startswith(quote):
                doc_parts.append(block[3:-3].strip())
            i += 1
            continue
        if s.startswith("#"):
            comment_parts.append(lines[i].rstrip())
            i += 1
            continue
        if s == "":
            i += 1
            continue
        break

    rest = "".join(lines[i:])
    if not rest.lstrip().startswith("from __future__"):
        return False

    merged = "\n\n".join(doc_parts)
    if comment_parts:
        merged += "\n\n" + "\n".join(comment_parts)
    body = f'"""\n{merged}\n"""\n' + rest
    if shebang and not body.startswith("#!"):
        body = shebang + body
    path.write_text(body, encoding="utf-8", newline="\n")
    return True


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv[1:] or ["tests", "scripts"])]
    n = 0
    for root in roots:
        files = [root] if root.is_file() else sorted(root.glob("*.py"))
        for fp in files:
            if fix_file(fp):
                print(f"fixed: {fp}")
                n += 1
    print(f"done: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
