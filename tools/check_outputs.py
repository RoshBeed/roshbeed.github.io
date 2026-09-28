"""Fail the build if a post would publish without the outputs it was written around.

Posts are not executed at render time any more: Quarto reuses the outputs stored
in the .ipynb, so what ships is whatever was in the notebook when it was
committed. That removes a twenty-minute build and makes the numbers stable, and
it moves one failure mode into git -- a notebook committed with its outputs
cleared renders as prose wrapped around empty code blocks, and nothing about the
build looks wrong.

So the guarantee that used to come from re-executing everything comes from here
instead. Three things are checked, and none of them assume a cell that produces
no value is a mistake:

  * the notebook ran at all -- at least one code cell carries an output
  * every code cell ran -- no null execution_count, which is what a half-run
    notebook or a fresh kernel leaves behind
  * nothing raised -- an `error` output means a traceback is about to be
    published as if it were a result

Execution *order* is deliberately not checked. Re-running a single cell while
writing bumps its count out of sequence, which is normal and not a defect.
"""

import json
import sys
from pathlib import Path

POSTS = Path(__file__).resolve().parent.parent / "posts"


def code_cells(notebook: Path) -> list[dict]:
    cells = json.loads(notebook.read_text())["cells"]
    return [c for c in cells
            if c["cell_type"] == "code" and "".join(c["source"]).strip()]


def main() -> None:
    notebooks = sorted(POSTS.glob("*/index.ipynb"))
    if not notebooks:
        raise SystemExit("no posts found")

    problems = []
    for notebook in notebooks:
        post = notebook.parent.name
        cells = code_cells(notebook)

        if not any(c.get("outputs") for c in cells):
            problems.append(f"{post}: no cell has any output -- "
                            f"run the notebook before committing it")
            continue

        unrun = sum(1 for c in cells if c.get("execution_count") is None)
        if unrun:
            problems.append(f"{post}: {unrun} of {len(cells)} code cells were "
                            f"never run (null execution_count)")

        errors = [o for c in cells for o in c.get("outputs", [])
                  if o.get("output_type") == "error"]
        if errors:
            names = ", ".join(sorted({o.get("ename", "?") for o in errors}))
            problems.append(f"{post}: {len(errors)} cell(s) ended in an "
                            f"exception ({names})")

    if problems:
        print("posts must ship the outputs they were written around:",
              file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        raise SystemExit(1)

    total = sum(len(code_cells(n)) for n in notebooks)
    print(f"outputs: {len(notebooks)} posts, {total} code cells, all executed")


if __name__ == "__main__":
    main()
