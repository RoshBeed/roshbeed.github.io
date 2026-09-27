"""Run some of a post's cells against a kernel that stays alive between calls.

`execute_posts.py` runs a whole notebook start to finish, which is what an
unattended run wants. Iterating on one figure does not: word2vec spends twenty
minutes training before the cell that draws anything, and re-running that to
change an axis label is the wrong shape of loop.

This keeps a kernel per post, so the expensive cells run once and the cheap ones
can be re-run as often as they need to be.

    python tools/run_cells.py word2vec --cells 0-7    # setup and training, once
    python tools/run_cells.py word2vec --cells 11     # then iterate on one cell
    python tools/run_cells.py word2vec --stop         # let the kernel go

Outputs are merged into the notebook as it stands on disk, so prose edited while
a cell was running survives. A cell that is not run keeps the outputs it had.
"""

import argparse
import os
import queue
import re
import subprocess
import time
from pathlib import Path

import nbformat
from jupyter_client import BlockingKernelClient
from jupyter_client.manager import KernelManager

ROOT = Path(__file__).resolve().parent.parent
POSTS = ROOT / "posts"
SESSIONS = Path("/tmp/roshbeed-kernels")


def find(match: str) -> Path:
    hits = [n for n in sorted(POSTS.glob("*/index.ipynb")) if match in n.parent.name]
    if len(hits) != 1:
        raise SystemExit(f"{match!r} matches {[h.parent.name for h in hits]}")
    return hits[0]


def parse_cells(spec: str, total: int) -> list[int]:
    wanted: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            wanted += list(range(lo, hi + 1))
        else:
            wanted.append(int(part))
    bad = [i for i in wanted if not 0 <= i < total]
    if bad:
        raise SystemExit(f"no such cell: {bad} (notebook has {total})")
    return wanted


def connection_file(notebook: Path) -> Path:
    SESSIONS.mkdir(exist_ok=True)
    return SESSIONS / f"{notebook.parent.name}.json"


def start(notebook: Path) -> BlockingKernelClient:
    """Reuse this post's kernel if one is alive, otherwise start a detached one.

    The kernel is spawned through `jupyter kernel` rather than KernelManager, so
    it outlives this process. A KernelManager-owned kernel is a child and dies on
    exit, which would defeat the point of keeping state between calls.
    """
    path = connection_file(notebook)
    if path.exists():
        client = BlockingKernelClient(connection_file=str(path))
        client.load_connection_file()
        try:
            client.start_channels()
            client.wait_for_ready(timeout=10)
            return client
        except Exception:
            client.stop_channels()
            path.unlink()

    log = path.with_suffix(".log")
    with open(log, "w") as handle:
        subprocess.Popen(["jupyter", "kernel", "--kernel=python3"],
                         cwd=str(notebook.parent), stdout=handle, stderr=handle,
                         start_new_session=True)
    spawned = None
    for _ in range(120):
        time.sleep(0.5)
        found = re.search(r"Connection file: (\S+\.json)", log.read_text())
        if found:
            spawned = Path(found.group(1).strip())
            break
    if spawned is None:
        raise SystemExit(f"kernel did not start; see {log}")
    path.write_text(spawned.read_text())
    client = BlockingKernelClient(connection_file=str(path))
    client.load_connection_file()
    client.start_channels()
    client.wait_for_ready(timeout=60)
    return client


def run(client, source: str, timeout: int) -> tuple[list, str | None]:
    """Send one cell and collect what comes back."""
    msg_id = client.execute(source)
    outputs, failure = [], None
    while True:
        try:
            message = client.get_iopub_msg(timeout=timeout)
        except queue.Empty:
            return outputs, "timed out"
        if message["parent_header"].get("msg_id") != msg_id:
            continue
        kind, content = message["msg_type"], message["content"]
        if kind == "status" and content["execution_state"] == "idle":
            return outputs, failure
        if kind == "stream":
            outputs.append(nbformat.v4.new_output("stream", name=content["name"],
                                                  text=content["text"]))
        elif kind in ("execute_result", "display_data"):
            outputs.append(nbformat.v4.new_output(kind, data=content["data"],
                                                  metadata=content.get("metadata", {})))
        elif kind == "error":
            failure = f"{content['ename']}: {content['evalue']}"
            outputs.append(nbformat.v4.new_output("error", ename=content["ename"],
                                                  evalue=content["evalue"],
                                                  traceback=content["traceback"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("match", help="post whose folder contains this")
    parser.add_argument("--cells", help="indices or ranges, e.g. 3,7,10-13")
    parser.add_argument("--list", action="store_true", help="number the cells and exit")
    parser.add_argument("--stop", action="store_true", help="shut this post's kernel down")
    parser.add_argument("--timeout", type=int, default=6 * 3600)
    arguments = parser.parse_args()

    notebook = find(arguments.match)
    document = nbformat.read(notebook, as_version=4)

    if arguments.list:
        for i, cell in enumerate(document.cells):
            head = next((l for l in cell.source.split("\n")
                         if l.strip() and not l.startswith("#|")), "")
            ran = "" if cell.cell_type != "code" else (
                " [out]" if cell.get("outputs") else " [   ]")
            print(f"{i:3} {cell.cell_type[:4]}{ran} {head[:66]}")
        return

    if arguments.stop:
        path = connection_file(notebook)
        if path.exists():
            client = BlockingKernelClient(connection_file=str(path))
            client.load_connection_file()
            try:
                client.start_channels()
                client.shutdown()
            except Exception:
                pass
            path.unlink()
            path.with_suffix(".log").unlink(missing_ok=True)
            print(f"kernel for {notebook.parent.name} stopped")
        else:
            print("no kernel running for that post")
        return

    if not arguments.cells:
        raise SystemExit("--cells is required (or --list, or --stop)")

    wanted = parse_cells(arguments.cells, len(document.cells))
    client = start(notebook)

    produced, failed = {}, []
    for index in wanted:
        cell = document.cells[index]
        if cell.cell_type != "code":
            continue
        print(f"  cell {index} ...", flush=True)
        outputs, failure = run(client, cell.source, arguments.timeout)
        produced[cell.source] = outputs
        if failure:
            failed.append((index, failure))
            print(f"  cell {index} FAILED {failure}", flush=True)

    client.stop_channels()

    # Merge into the file as it stands now, not the copy read at the start.
    current = nbformat.read(notebook, as_version=4)
    merged = 0
    for cell in current.cells:
        if cell.cell_type == "code" and cell.source in produced:
            cell.outputs = produced[cell.source]
            merged += 1
    nbformat.write(current, notebook)
    print(f"merged {merged} cell(s) into {notebook.parent.name}; kernel still up")
    if failed:
        raise SystemExit(f"{len(failed)} cell(s) failed: {[i for i, _ in failed]}")


if __name__ == "__main__":
    main()
