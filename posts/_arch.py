"""visualtorch, configured once for this site.

Quarto ignores underscore-prefixed files, so this is not a post. Posts reach it
with `sys.path.insert(0, "..")`, same as `_style`.

Two notes on the settings below, both learned the hard way:

* `type_ignore` looks like the right way to hide LayerNorm and activation
  columns, and it silently stops the connectors being drawn past the third
  layer. So every layer type is shown and coloured instead.
* `graph` draws real neurons and suits a short stack; `flow` draws volumetric
  blocks whose size tracks the layer's and stays readable on a deep one.
* `flow` reports a 3-D activation as `(1, 1, width)`, losing the sequence
  length, so its shape labels are switched off; `graph` gets them right and
  keeps them.
* `level_gap=1` keeps a residual connection drawn close to the blocks it skips.
  Without it a transformer's skip arcs are routed far above the diagram and end
  up taller than the model.
* A model taking token ids needs `input_dtype`, because the dummy inputs are
  float by default and `nn.Embedding` refuses them.
"""

import torch.nn as nn
import visualtorch

from _style import COLOURS

# Layer types get a stable colour across every post, so the same kind of thing
# is the same colour whichever diagram you are looking at.
COLOUR_MAP = {
    nn.Linear: {"fill": COLOURS[0]},
    nn.MultiheadAttention: {"fill": COLOURS[1]},
    nn.Embedding: {"fill": COLOURS[3]},
    nn.LayerNorm: {"fill": "#aeb6bf"},
    nn.GELU: {"fill": COLOURS[2]},
    nn.ReLU: {"fill": COLOURS[2]},
    nn.Flatten: {"fill": "#aeb6bf"},
}

_COMMON = dict(
    color_map=COLOUR_MAP,
    connector_fill="#c3c9d0",
    background_fill="white",
    font_color="#5b6570",
    legend=True,
    show_dimension=True,
)


def diagram(model, input_shape, style="graph", **overrides):
    """Render `model` as a PIL image in this site's colours."""
    if style == "graph":
        settings = dict(node_size=24, layer_spacing=110, node_spacing=8,
                        ellipsize_after=5, **_COMMON)
    else:
        settings = dict(spacing=26, scale_xy=2.4, max_xy=280,
                        one_dim_orientation="y", level_gap=1, **_COMMON)
        settings["show_dimension"] = False
    settings.update(overrides)
    return visualtorch.render(model, input_shape=input_shape, style=style, **settings)
