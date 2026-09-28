"""Fail on a post whose stored outputs were produced by different code.

`check_outputs.py` asks whether a cell ran. It cannot ask whether it ran *this*
cell: an edit to a print statement leaves the old output sitting underneath the
new code, the notebook still renders, and every check passes. That is how the
encoder-decoder post shipped `targets of length 3` under code that had already
been rewritten to draw one to three.

The test is cheap and needs no kernel. Every `print("...")` in a cell contributes
the literal text around its placeholders; if a literal long enough to be
distinctive is absent from that cell's output, the output predates the code.
"""

import ast
import json
import re
import sys
from pathlib import Path

# json rather than nbformat: CI installs the render dependencies only
# (`uv sync --locked --no-default-groups`), so the notebook libraries are not
# there. A notebook is JSON, and both sibling checks read it the same way.

ROOT = Path(__file__).resolve().parent.parent
MIN_LITERAL = 12          # shorter fragments match by coincidence


def literals(source: str) -> list[str]:
    """The fixed text a cell's print calls must emit, f-string holes removed."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
            continue
        for argument in node.args:
            parts = argument.values if isinstance(argument, ast.JoinedStr) else [argument]
            for part in parts:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    # A literal can span a placeholder on either side, so split on
                    # whitespace runs and keep the pieces worth matching.
                    found += [p for p in re.split(r"\s{2,}|\n", part.value)
                              if len(p.strip()) >= MIN_LITERAL]
    return found


def text_of(value) -> str:
    """A notebook stores source and stream text as a string or a list of lines."""
    return value if isinstance(value, str) else "".join(value)


def main() -> None:
    stale: list[str] = []
    checked = 0
    for notebook in sorted(ROOT.glob("posts/*/index.ipynb")):
        document = json.loads(notebook.read_text(encoding="utf-8"))
        for number, cell in enumerate(document["cells"]):
            if cell["cell_type"] != "code" or not cell.get("outputs"):
                continue
            printed = "".join(text_of(o.get("text", "")) for o in cell["outputs"]
                              if o.get("output_type") == "stream")
            if not printed:
                continue
            for literal in literals(text_of(cell["source"])):
                checked += 1
                if literal.strip() not in printed:
                    stale.append(f"{notebook.parent.name} cell {number}: "
                                 f"code prints {literal.strip()!r}, output does not")
    if stale:
        print("outputs were produced by earlier versions of this code:")
        for line in stale:
            print(f"  {line}")
        sys.exit(1)
    print(f"freshness: {checked} print literals, all present in their cell's output")


if __name__ == "__main__":
    main()
