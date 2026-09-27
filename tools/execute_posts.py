"""Run posts and save their outputs into the notebooks themselves.

This is the step that used to happen on a GitHub runner. Quarto no longer
executes anything: it publishes the outputs stored in each `.ipynb`, so this is
what puts them there.

Execution is in-place and the working directory is the post's own folder, which
is what a notebook opened in Jupyter would see -- posts read `figures/` by
relative path.

    python tools/execute_posts.py                  # every post
    python tools/execute_posts.py superposition    # posts matching a substring
    python tools/execute_posts.py --timeout 7200   # tighten the cap for one run
    python tools/execute_posts.py --retries 0      # fail on the first attempt

A post that trains for hours can lose its kernel to something that has nothing to
do with the notebook: the machine runs out of memory, the socket to the kernel
dies. Those are retried. A cell that raises is not -- the code is wrong and running
it again will raise the same way.

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


def merge_outputs(executed: nbformat.NotebookNode, notebook: Path) -> int:
    """Copy outputs onto the file as it stands now, rather than overwriting it.

    A run takes minutes to hours, and prose gets edited while it is going. Writing
    the in-memory copy back would silently discard those edits, so the file is
    re-read and only the outputs are transplanted. Code cells are matched in order
    and by source: a cell whose source changed during the run keeps whatever it had,
    because the outputs just produced belong to a version that no longer exists.
    """
    current = nbformat.read(notebook, as_version=4)
    ran = [c for c in executed.cells if c.cell_type == "code"]
    disk = [c for c in current.cells if c.cell_type == "code"]
    moved = 0
    for before, after in zip(ran, disk):
        if before.source == after.source:
            after.outputs = before.outputs
            after.execution_count = before.execution_count
            moved += 1
    stale = len(disk) - moved
    if stale or len(ran) != len(disk):
        print(f"  {stale} code cell(s) changed during the run and kept their outputs",
              flush=True)
    nbformat.write(current, notebook)
    return moved


def execute(notebook: Path, timeout: int) -> None:
    document = nbformat.read(notebook, as_version=4)
    client = NotebookClient(document, timeout=timeout, kernel_name="python3",
                            resources={"metadata": {"path": str(notebook.parent)}})
    client.execute()
    merge_outputs(document, notebook)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", nargs="?", default="",
                        help="only run posts whose folder contains this")
    # A post trains the model it describes, so one cell legitimately runs for
    # hours. The cap is here to catch a hang, not to bound normal work.
    parser.add_argument("--timeout", type=int, default=6 * 3600,
                        help="per-cell timeout in seconds (default: 6 hours)")
    parser.add_argument("--retries", type=int, default=2,
                        help="retries after a lost kernel or a timeout (default: 2)")
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
        for attempt in range(arguments.retries + 1):
            start = time.monotonic()
            try:
                execute(notebook, arguments.timeout)
            except CellExecutionError as error:
                # The notebook's own code raised. Retrying reruns the same bug.
                failed.append(post)
                print(f"FAILED {post} after {time.monotonic() - start:.0f}s, "
                      f"a cell raised", flush=True)
                print(f"  {str(error).strip().splitlines()[-1]}", file=sys.stderr)
                break
            except Exception as error:                       # noqa: BLE001
                # A lost kernel, a timeout, a dead socket. None of them say
                # anything about the notebook, so try again.
                left = arguments.retries - attempt
                print(f"LOST {post} after {time.monotonic() - start:.0f}s: "
                      f"{type(error).__name__}, {left} retries left", flush=True)
                if not left:
                    failed.append(post)
                    print(f"FAILED {post}, out of retries", flush=True)
            else:
                print(f"    done {post} in {time.monotonic() - start:.0f}s", flush=True)
                break

    if failed:
        raise SystemExit(f"\n{len(failed)} post(s) failed: {', '.join(failed)}")
    print(f"\n{len(notebooks)} post(s) executed; "
          f"run tools/check_outputs.py before committing")


if __name__ == "__main__":
    main()
