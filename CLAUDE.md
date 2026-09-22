# roshbeed.com — working notes

Quarto site. Posts are rendered here, on a laptop; Actions publishes what was
committed and never executes a notebook.

```sh
uv sync                                  # create .venv from the lockfile
git config diff.ipynb.textconv \
  "$PWD/.venv/bin/python -m nbstripout -t"   # once per clone, see below
export QUARTO_PYTHON="$PWD/.venv/bin/python"
quarto preview                           # live reload while writing
quarto render                            # build _site/ from stored outputs

python tools/execute_posts.py            # run every post, save its outputs
python tools/execute_posts.py rlhf       # just the posts matching "rlhf"
python tools/check_outputs.py            # what CI checks before publishing
```

Quarto never runs a post. `execute_posts.py` does, and writes the outputs into
the notebook; `quarto render` then publishes whatever it finds there.

## Posts are executed while they are written, not at build time

Quarto does not execute `.ipynb` posts. It reuses the outputs stored in the
notebook, and those outputs are committed. Running a post is part of writing it.

So `quarto render` builds the site in seconds and needs no torch. Producing the
outputs is a separate step: `tools/execute_posts.py` runs each notebook in place
with nbclient, from the post's own directory, which is what a notebook opened in
Jupyter would see. Running a post in Jupyter and saving does the same thing.

Re-run a post when it changes, and every post after a dependency bump.

This replaced a build that executed all eleven posts on a GitHub runner. That
took about twenty minutes, trained models on CI hardware to draw figures, and
answered differently from the laptop often enough to make the prose unreliable.

The cost is real and worth stating: a figure is no longer a product of the
locked environment by construction. It is a product of whichever machine last
ran the notebook. `uv.lock` and `.python-version` still pin that machine, and
every dataset a post pulls is still pinned to a Hugging Face commit revision,
but nothing enforces that the person rendering used them.

`tools/check_outputs.py` covers the one failure mode this introduces. A notebook
committed with its outputs cleared renders as prose wrapped around empty code
blocks, and nothing about the build looks wrong. It runs in CI and fails on a
post whose cells were never run, or that ends in a traceback.

There is no freeze cache and no use for one. Nothing executes at render time, so
there is no execution to cache.

## The prose may quote what the notebook computed

A number in the prose and the output beside it now come from the same run, so
they cannot disagree. That was the main thing wrong with building on a runner:
it is x86-64 and this laptop is arm64, the same code gave 0.842 here and 0.926
there, and 13 of 47 outputs differed when I checked. Prose had to hedge around
its own figures, saying "naming most of them" rather than "naming five in six".

Two habits survive, because a re-run still has to agree with the run before it.

Every post that imports torch calls `torch.set_num_threads(1)`. Multithreaded
CPU reductions add floats in whatever order the threads finish in, so the same
seed gives different answers run to run, and over a training loop that compounds
until a PPO sweep settles on a different policy each time.

Where a comparison is the point, make it stable rather than quoting one run of
it. The emotion post reports three seeds with the spread beside the mean, which
is what showed the two designs it compares do not actually separate.

Re-running a post rewrites every number it produced. Read the prose against the
new outputs before committing them.

## The repo holds no data

Corpora, measurements and dataset slices live in the
`roshbeed/ai-residency-blog-data` dataset on the Hub and are pulled at render
time, pinned to a commit. A clone is ephemeral: it works on a laptop or a runner
with nothing cached. That includes the figures a post displays:
`posts/*/figures/` is gitignored, and `tools/fetch_figures.py` fills it from the
same dataset before every render.

## Notebook outputs are the published artifact

Outputs are committed. nbstripout used to run as a git clean filter, and that is
what forced CI to execute: the committed notebook carried no outputs, so a fresh
run was the only thing left to publish. The filter is gone.

nbstripout stays installed for one job. `.gitattributes` keeps `*.ipynb
diff=ipynb`, pointed at `nbstripout -t` as a diff textconv, so `git diff` shows
the code that changed without the base64 PNGs underneath it. The committed file
keeps its outputs; only the diff view drops them.

That textconv is local config, so a fresh clone needs the `git config` line
above. Do not run `nbstripout --install` — it restores the clean filter.

## Layout

```
posts/<date>-<slug>/index.ipynb    the post, and nothing else

posts/_metadata.yml   options every post shares
tools/fetch_figures.py  pulls figures from the Hub before rendering
tools/check_isolation.py  fails the build if a post imports a sibling
tools/check_outputs.py  fails CI on a post committed without its outputs
tools/execute_posts.py  runs the posts and saves their outputs in place
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
