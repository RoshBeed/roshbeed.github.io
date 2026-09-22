"""Download the figures the posts display, before Quarto renders them.

The repository holds no data: corpora, measurements and figures all live in the
`roshbeed/ai-residency-blog-data` dataset and are pulled at render time, pinned to
a commit so a rebuild cannot quietly pick up something different. A clone is
therefore ephemeral — it works on a laptop or a CI runner with nothing cached, and
a post is one notebook and nothing else.

Quarto runs this from `pre-render` in _quarto.yml. Figures land in
posts/<post>/figures/, which is gitignored.
"""

from pathlib import Path

from huggingface_hub import snapshot_download

DATASET = "roshbeed/ai-residency-blog-data"
REVISION = "99e231d8cc966b4c279df94c376f50e1910087e0"
ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    cache = Path(snapshot_download(DATASET, repo_type="dataset", revision=REVISION,
                                   allow_patterns="figures/**")) / "figures"

    placed = skipped = 0
    for post in sorted(cache.iterdir()):
        target = ROOT / "posts" / post.name
        if not target.is_dir():
            skipped += 1          # a post that has since been renamed or removed
            continue

        figures = target / "figures"
        figures.mkdir(exist_ok=True)
        for figure in post.iterdir():
            destination = figures / figure.name
            if not destination.exists():
                destination.write_bytes(figure.read_bytes())
            placed += 1

    note = f", {skipped} unused" if skipped else ""
    print(f"figures: {placed} in place from {DATASET}@{REVISION[:7]}{note}")


if __name__ == "__main__":
    main()
