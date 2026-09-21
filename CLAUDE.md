# roshbeed.com — working notes

Quarto site, published to GitHub Pages by Actions on every push to `main`.

```sh
uv sync                                  # create .venv from the lockfile
uv run nbstripout --install              # once per clone, see below
export QUARTO_PYTHON="$PWD/.venv/bin/python"
quarto preview                           # live reload while writing
quarto render                            # one-shot build into _site/
```

## Posts are notebooks, executed at build time

`posts/_metadata.yml` sets `execute: enabled: true`, which is not Quarto's default
for `.ipynb` — left alone it reuses whatever outputs are stored in the notebook.
Executing is the point: a figure is then the output of the code beside it, never a
committed artifact that drifted.

That guarantee needs a fixed environment, so Quarto is pinned in the workflow,
Python in `.python-version`, packages in `uv.lock` via `uv sync --locked`, and
every dataset a post pulls is pinned to a Hugging Face commit revision.

There is no freeze cache. Every build runs every post, which takes about twenty
minutes and costs nothing on a public repo. Do not add one: Quarto keys it on the
md5 of the notebook *including its outputs*, which nbstripout strips on the way
into git, so the committed notebook never matches and CI re-executes anyway.

## The prose may not restate a number the build computes

A post is re-executed on every build, and the build that readers see runs on a
GitHub runner, not on my laptop. Two things follow.

Torch's multithreaded CPU reductions add floats in whatever order the threads
finish in, so the same seed gives different answers run to run. Over a training
loop that compounds: a PPO sweep came out with a different policy each render, and
the prose asserting what it settled on was wrong about half the time. Every post
that imports torch calls `torch.set_num_threads(1)` for this reason.

That fixes a run on one machine and cannot fix it across two. The runner is
x86-64 and this laptop is arm64, and the same code gives 0.842 here and 0.926
there — 13 of 47 outputs differed when I checked. So prose states what is stable
and the output carries the digits: "naming most of them", not "naming five in
six". Counts that come from data rather than training — tokens, parameters, a
chance baseline — are exact and safe to quote.

Where a comparison is the point, make it stable rather than quoting one run of it.
The emotion post reports three seeds with the spread beside the mean, which is
what showed the two designs it compares do not actually separate.

After a push, diff the live outputs against the local ones before trusting any
number in the prose.

## The repo holds no data

Corpora, measurements and dataset slices live in the
`roshbeed/ai-residency-blog-data` dataset on the Hub and are pulled at render
time, pinned to a commit. A clone is ephemeral: it works on a laptop or a runner
with nothing cached. That includes the figures a post displays:
`posts/*/figures/` is gitignored, and `tools/fetch_figures.py` fills it from the
same dataset before every render.

## Notebook outputs never reach git

Rendering writes outputs back into the `.ipynb`, which would turn a one-line prose
edit into a diff of base64 PNGs. nbstripout runs as a git clean filter, so the
notebook on disk keeps its outputs for Jupyter while the committed copy has none.
It fires on `git add`. It is local config, so a fresh clone must run
`uv run nbstripout --install`.

## Layout

```
posts/<date>-<slug>/index.ipynb    the post, and nothing else

posts/_metadata.yml   options every post shares
tools/fetch_figures.py  pulls figures from the Hub before rendering
tools/check_isolation.py  fails the build if a post imports a sibling
_site/                the built site, gitignored
```

## Every notebook stands on its own

A post imports nothing from the repo. There is no `posts/_style.py`, no
`_arch.py`: the chart palette, the visualtorch settings, the log-mel front end
and the block-diagram code are pasted into a folded setup cell at the top of
each notebook that needs them. Lift one `.ipynb` out of the repo and it runs.

That is a deliberate trade and the cost is real. The chart styling exists eleven
times and the mel filterbank twice, so a fix has to be applied to each copy.
Those two copies drifted apart once already, and the stale one rounded its
triangle corners to whole FFT bins, which leaves four mel bands empty and paints
black stripes across the spectrogram. If you change one, change the others.

`tools/check_isolation.py` runs from `pre-render` and fails the build if a
notebook grows a `sys.path` insert or a `from _something import`.

## Figures

`tools/fetch_figures.py` runs from `pre-render` and pulls every figure the posts
display into `posts/<post>/figures/`, which is gitignored. Adding figures means
uploading them to `figures/<post>/` in the dataset and bumping `REVISION`.

Extracting them from a slide deck in the first place is a one-off job that does
not live here — the decks are not in this repo either.

## Writing

Short sentences. Plain headings. Bullets over long clauses. Every post ends with a
Conclusion.

The course slide decks are the source of truth for what a week covered — follow
the arc they take rather than inventing a hook. Do not use an image of text; quote
it. Cut AI tells: "turns out", "the catch", "is the point", "essentially", heavy
em-dash use.
