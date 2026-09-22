"""Run posts and save their outputs into the notebooks themselves.

This is the step that used to happen on a GitHub runner. Quarto no longer
executes anything: it publishes the outputs stored in each `.ipynb`, so this is
what puts them there.

Execution is in-place and the working directory is the post's own folder, which
is what a notebook opened in Jupyter would see -- posts read `figures/` by
relative path.

    python tools/execute_posts.py                  # every post
    python tools/execute_posts.py superposition    # posts matching a substring
    python tools/execute_posts.py --timeout 7200   # a post that trains for a while

Several of these train a model, so the full run is long by design. That is the
trade: it happens once, here, rather than on every build.
"""

import argparse
import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

POSTS = Path(__file__).resolve().parent.parent / "posts"


def execute(notebook: Path, timeout: int) -> None:
    document = nbformat.read(notebook, as_version=4)
    client = NotebookClient(document, timeout=timeout, kernel_name="python3",
                            resources={"metadata": {"path": str(notebook.parent)}})
    client.execute()
    nbformat.write(document, notebook)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", nargs="?", default="",
                        help="only run posts whose folder contains this")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="per-cell timeout in seconds (default: 3600)")
    arguments = parser.parse_args()

    notebooks = [n for n in sorted(POSTS.glob("*/index.ipynb"))
                 if arguments.match in n.parent.name]
    if not notebooks:
        raise SystemExit(f"no post matches {arguments.match!r}")

    failed = []
    for notebook in notebooks:
        post = notebook.parent.name
        # One line per event, never a trailing `end=""`: the kernel writes its
        # own warnings to the same terminal and would land in the middle of it.
        print(f"running {post}", flush=True)
        start = time.monotonic()
        try:
            execute(notebook, arguments.timeout)
        except CellExecutionError as error:
            failed.append(post)
            print(f"FAILED {post} after {time.monotonic() - start:.0f}s", flush=True)
            print(f"  {str(error).strip().splitlines()[-1]}", file=sys.stderr)
        else:
            print(f"    done {post} in {time.monotonic() - start:.0f}s", flush=True)

    if failed:
        raise SystemExit(f"\n{len(failed)} post(s) failed: {', '.join(failed)}")
    print(f"\n{len(notebooks)} post(s) executed; "
          f"run tools/check_outputs.py before committing")


if __name__ == "__main__":
    main()
