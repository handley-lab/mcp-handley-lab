---
name: figure_standard
description: The house style for data figures, as render-order discipline. The same voice projected into the figure medium - a correct plot that does not carry the mark still fails. Compute placement from the data, render vital information on top, never let furniture collide with meaning.
---

# Figure Standard [EXPERIMENTAL]

A figure is the voice in a non-prose medium. The physics can be right and the figure still fail - if a gridline crosses a label, if an inset lands on the curve, if a number floats free of the thing it measures. This skill is that failure mode stated as a discipline, settled live with the author against his standing peeve: a non-important element drawn over vital information, above all text colliding with a graphic.

State it positively. "Do not overlap" gives no guidance. "Vital information renders on top, and every element's place is computed from the data" does.

## The settled forks

- **Frame and ticks.** Despined - drop the top and right spines. Ticks inward.
- **Grid off by default.** A grid earns its place only when the reader's job is to read values off the plot. On a structural figure - a slope, a trend, anything carrying labels or insets over it - the grid is background texture competing with the meaning-bearing elements, so it stays off. When a value does need reading, turn it on, always below the data (`set_axisbelow`). Prefer a single reference line at a meaningful value (an axis-zero crossing) over a full grid.
- **Legend is conditional on geometry.** Direct labels on curves when they are spatially distinct, degrading to a colourbar for a family or ensemble. A discrete legend box when curves overlay or cross - a label at the end is ambiguous then. When exact markers sit *on* a fitted line because their coincidence is the result, a legend is correct, not direct labels.
- **Panel labels.** Bold lowercase `(a)`, exterior top-left.
- **Hero intent is per figure.** A mechanism schematic and a result plot want different framing. Decide which a figure is before building it.
- **Adopted silently (best practice, not peeves).** viridis/cividis continuous, Okabe-Ito categorical. Vector line art (PDF/EPS), raster at 600dpi or more. Match the body face (CM serif via usetex for REVTeX). 6pt floor, 7-8pt target. Exact column-width sizing (APS 8.6cm single, 17.8cm double). Every figure from a version-controlled script.

## Render-order discipline (the core)

Vital information renders on top. Data above structure, labels above data. Gridlines always `set_axisbelow(True)`, annotation text always on the upper layer.

Reserve space before placing text. Identify each label's collision zone - plot boundary, corner, dense data region, neighbouring labels - at design time and give it room. Extend the axis limit for headroom, pad, or relocate, rather than letting it land on or under another element.

Think in render layers up front. Post-hoc visual inspection is the costly path. Boundaries, corners, and dense regions are the standing risk zones.

## Placement is derived from the data, not guessed

You know what you are plotting before you render it, so you know where the whitespace is. Compute the data's footprint and place every secondary element - inset, legend, annotation - where the data is not. Never hand-place and then discover it landed on the curve.

**Draw the canvas first** (`fig.canvas.draw()`) so the data transform reflects the final limits. Computing placement before the draw uses provisional transforms and lands in the wrong corner.

Two consequences of the inward-tick default:
- **Reserve an edge band along every spine.** Inward ticks live *inside* the data area, so the plot region is not clean to its edges. A secondary element flush against an axis occludes that axis's ticks. Pay this once in the placer, not by eye each time.
- **An inset's labelled axes face the figure interior.** An inset whose y-axis abuts the parent's y-axis sandwiches two near-identical sets of tick furniture and the reader cannot tell whose is whose, even with no literal overlap. Turn the inset's decorations into empty space - a left-half inset puts its y-ticks on the right, a bottom-half inset puts its x-ticks on top.

## An annotation attaches to its referent, and its label is enclosed

A floating "psi = 0.505" in a corner is meaningless without the caption. Attach the annotation to the thing it describes - a slope triangle *on* the power-law line, a label beside its curve, an arrow to its feature. Put the label *inside* the element where possible (a slope-triangle label at the triangle's log-centroid, enclosed by its own legs) - an enclosed label is guaranteed clear and cannot drift into a neighbour. If it cannot be attached, it belongs in the caption, not floating.

Fixing one collision can open another. Placing elements one at a time, each fix can push a label into a neighbour. The durable answer is to make each element's footprint *and its label* self-contained and placed against the data footprint - which is why labels are enclosed and placement is computed, not nudged.

## Usage

This is a protocol, not a backing script. Build every data figure on a house-style module that encodes the forks above. The reference implementation is `scripts/figs/anf_style.py` in the adaptive-normal-form project: `find_clear_box` (occupancy-grid placement with an `edge_pad` band), `orient_inset` (interior-facing inset furniture), `slope_triangle` (enclosed-label annotation), and `finish_axes` (despine, inward ticks, opt-in grid below data).

After rendering, inspect the PNG yourself before presenting - catch collisions before the author does - and open the result natively for review.

## Probationary status

This is an `[EXPERIMENTAL]` discipline forged from the ANF figure rail, where the whole house style was settled live with the author. It generalises beyond that paper but has been exercised on one. Solicit feedback on each new figure surface until the placement primitives prove out on a second project, and lift the project-coupled `anf_style.py` into a canon backing script once they do.
