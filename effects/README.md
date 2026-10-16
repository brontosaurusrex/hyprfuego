# Window-close effects

Each effect has its own folder and GLSL source. Select one with
`./hyprfuego effect burn` or `./hyprfuego effect teleport`.

- `burn/`: the existing burn shader, constant-size preview, and historical variants.
- `teleport/`: experimental random matter breakup, blue-white shafts and a shimmering particle cloud.
  The window content is gone at 38% of the duration. `// @reflow natural` leaves
  neighboring windows on the compositor's normal layout timing while the wake
  continues. Fadeout snapshots receive no input; normal focus handling continues.

`// @duration` supplies an effect's default duration. A saved duration preference
(0.1–20 seconds) applies to either effect. `duration default` restores the selected
shader's default. The old `shaders/` paths remain compatibility symlinks.
