# Distribution branch — do not develop here

This branch is **not source**. It is the published `agent-device@0.17.2` npm package,
extracted verbatim, with two patches applied to the prebuilt bundle so it can be installed
straight from git with no build step.

1. `dist/src/2415.js` — `resolveRunnerSigningBuildSettings` emits `CODE_SIGN_STYLE=Manual`
   when `AGENT_DEVICE_IOS_PROVISIONING_PROFILE` is set, and keeps `Automatic` otherwise.
   Xcode ignores `PROVISIONING_PROFILE_SPECIFIER` under automatic signing, which made that
   variable a no-op.
2. `dist/src/9542.js` — the default daemon request envelope honours
   `AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS`, falling back to 90s. A cold UI-test runner on a
   slow physical device can take ~60s to launch, so the stock envelope expires before it
   connects and the runner is killed mid-startup.
3. `package.json` — `prepack` and `devDependencies` removed. npm runs `prepack` when packing
   a git dependency, and this branch ships prebuilt output, so the build must not run.

Source-level equivalents, which are what get upstreamed to `callstack/agent-device`:

| Branch | Fix |
|---|---|
| `fix/manual-signing-with-explicit-profile` | (1), with tests |
| `fix/configurable-daemon-request-timeout` | (2), with tests |

To refresh for a new upstream version: `npm pack agent-device@<version>`, extract, re-apply
all three edits, commit.
