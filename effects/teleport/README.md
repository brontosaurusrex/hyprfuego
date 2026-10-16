# Transporter

The current visual reference is the user-provided trimmed clip
`Green screen star trek transporter effects [is9ztQqQ2N0]_trimmed.mp4`
(1280×720, 30 fps, approximately 1.57 seconds). The reference is not bundled.

The effect follows the clip's progression:

1. Narrow, bluish-white vertical shafts sweep into view.
2. The shafts resolve into a dense cloud of soft points, with a brighter center.
3. Individual points shimmer, drift irregularly and fade at different times.

Particles have white-blue cores and broad blue halos, with independent size,
brightness, lifetime and flicker. A local neighbor-cell field renders hundreds
of points without iterating over every particle at each pixel. Three nearby
columns similarly cover each beam's core and halo.

A fixed multiscale density field breaks the window into random patches throughout
its area; vanished content never returns. Content is gone at 38% of the total
duration, leaving only the energy wake. `// @reflow natural` preserves early
focus/input handoff and ordinary layout timing. The shader stays inside the
snapshot's original alpha. Duration remains configurable from 0.1 to 20 seconds.
