# Ground zero

The user selected this Hyprfuego source revision as the return point on
2026-10-15:

- Repository: `/home/b/source/hyprfuego`
- Commit: `e88763400d6cc733ba14e5872b9bf73c6a2e639f`
- Branch at selection: `main`
- Commit subject: `fuego`
- Working tree at selection: clean

When the user asks to "return to ground zero", they mean this exact source
revision. This records a future restore target; it is not a request to restore
anything now. Preserve subsequent work before restoring unless the user
explicitly asks to discard it. This checkpoint covers Git source, not system
snapshots or desktop configuration outside this repository.

An annotated `ground-zero` tag could not be created because the session exposes
Git metadata as read-only. This note preserves the target independently of the
current branch tip.
