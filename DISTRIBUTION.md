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
3. `dist/src/2415.js` — the Apple runner's 45s startup and command budgets honour
   `AGENT_DEVICE_RUNNER_TIMEOUT_MS`, falling back to 45s. A cold UI-test runner on a slow
   device can need longer just to launch; startup then expires and the runner is killed
   mid-boot, surfacing as `BUILD INTERRUPTED`. The minifier inlined both constants as default
   parameters, so there is no named symbol to target: every `45e3` in that module is routed
   through one env-derived value. That also scales a few unrelated 45s budgets in the same
   module (e.g. simulator `bootstatus`), but only when the variable is set, which we do for
   physical-device runs only.
4. `package.json` — `prepack` and `devDependencies` removed. npm runs `prepack` when packing
   a git dependency, and this branch ships prebuilt output, so the build must not run.

Source-level equivalents, which are what get upstreamed to `callstack/agent-device`:

| Branch | Fix |
|---|---|
| `fix/manual-signing-with-explicit-profile` | (1), with tests |
| `fix/configurable-daemon-request-timeout` | (2), with tests |
| `fix/configurable-runner-startup-timeout` | (3), with tests |

To refresh for a new upstream version: `npm pack agent-device@<version>`, extract, re-apply
all four edits, commit.
