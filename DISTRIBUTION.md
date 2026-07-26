# Distribution branch — do not develop here

This branch is **not source**. It is the published `agent-device@0.17.2` npm package,
extracted verbatim, with one patch applied to the prebuilt bundle so it can be installed
straight from git with no build step:

- `dist/src/2415.js` — `resolveRunnerSigningBuildSettings` now emits
  `CODE_SIGN_STYLE=Manual` when `AGENT_DEVICE_IOS_PROVISIONING_PROFILE` is set, and keeps
  `Automatic` otherwise. Xcode ignores `PROVISIONING_PROFILE_SPECIFIER` under automatic
  signing, which made that environment variable a no-op.
- `package.json` — `prepack` and `devDependencies` removed. npm runs `prepack` when packing
  a git dependency, and this branch ships prebuilt output, so the build must not run.

The equivalent change **in source** is on `fix/manual-signing-with-explicit-profile`, which
is the branch to upstream to `callstack/agent-device`. Fix things there, not here.

To refresh this branch for a new upstream version: `npm pack agent-device@<version>`,
extract, re-apply both edits above, commit.
