"""Fail the build if a post depends on anything outside its own file.

Every notebook is self-contained: the shared helpers that used to live in
posts/_style.py, _arch.py, _audio.py and _blocks.py are inlined into a folded
setup cell in each post. That is what lets a single .ipynb be lifted out of the
repo and run.

It is also easy to undo by accident — one `from _style import COLOURS` during an
edit and the invariant is gone, with nothing failing until someone tries to run
the notebook on its own. Quarto runs this from `pre-render`.
"""

import json
import re
import sys
from pathlib import Path

POSTS = Path(__file__).resolve().parent.parent / "posts"
BANNED = ((re.compile(r"^\s*from\s+_\w+\s+import\s", re.M), "imports a sibling module"),
          (re.compile(r"sys\.path\.insert", re.M), "inserts into sys.path"))


def main() -> None:
    problems = []
    for notebook in sorted(POSTS.glob("*/index.ipynb")):
        cells = json.loads(notebook.read_text())["cells"]
        source = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
        for pattern, why in BANNED:
            for hit in pattern.findall(source):
                problems.append(f"{notebook.parent.name}: {why} -- {hit.strip()}")

    stray = sorted(p.name for p in POSTS.glob("_*.py"))
    if stray:
        problems.append(f"helper modules are back in posts/: {', '.join(stray)}")

    if problems:
        print("posts must stand on their own:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        raise SystemExit(1)
    print(f"isolation: {len(list(POSTS.glob('*/index.ipynb')))} posts, no sibling imports")


if __name__ == "__main__":
    main()
