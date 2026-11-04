# Native iOS coordinate-fill evidence

This run names head `abf90adaea15e7104cff4c1bff4979f500e4e810` and pristine upstream base `7d42395ff7e1c03b643c2cf56683808bf5427cf3`. Device type: `com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro-Max`. Runtime: `com.apple.CoreSimulator.SimRuntime.iOS-26-2`. Both versions rebuilt JavaScript and their own stock iOS XCTest runner with unit fixtures disabled. Each version starts with a previously absent, separate daemon state directory. The source-owned SDK drives native coordinate `fill` through that daemon and runner into a separate UIKit witness app.

## Evidence

- [cases.json](cases.json): all 16 successful cases, preparation commands/responses, coordinate fill commands/responses, exact app-owned underlying values, unchanged neighbour, and focus/tap witnesses.
- [runner-excerpts.log](runner-excerpts.log): matching native `type` accepted/completed events, structured focus/clear/phase events, and XCTest coordinate taps. Command IDs map consistently to case names. Timestamps, process identifiers, durations, and free-form exception text are omitted; the synthetic bundle name is normalized. Raw excerpt SHA256 values identify retained local originals.
- [provenance.json](provenance.json): source SHAs, runner source fingerprints, built JavaScript and CLI hashes, and fresh daemon-state assertions.
- [validation-receipt.json](validation-receipt.json): passed exact-head affected gate, individual check statuses, CI/manual skips, and nine passed native regression tests with zero skips. The iOS Simulator arm64 native build passed. This local receipt does not establish required CI success. [ci-status.json](ci-status.json) records the fork-workflow and Vercel authorization obligations.
- [cleanup.json](cleanup.json): successful owned-session, daemon, synthetic app and lease cleanup. Raw states, runner logs, device IDs, samples and xcresult bundles remain local.
- [aggregates.json](aggregates.json): five successful pairs per operation, alternating version order and rotating operation order. Timing covers the coordinate fill step; setup and independent assertions run outside that step. All 60 measured commands succeeded and satisfied exact app-owned text and untouched-neighbour assertions. These measurements make no full-suite gain claim.

| Operation | Base median (ms) | Head median (ms) | Reduction | Head faster pairs |
| --- | ---: | ---: | ---: | ---: |
| empty_focused | 2447 | 1654 | 32.4% | 5/5 |
| existing_focused | 4070 | 2686 | 34.0% | 5/5 |
| clear_focused | 2725 | 1388 | 49.1% | 5/5 |
| empty_unfocused | 2209 | 2289 | -3.6% | 1/5 |
| existing_unfocused | 3940 | 4033 | -2.4% | 0/5 |
| clear_unfocused | 2681 | 2882 | -7.5% | 2/5 |

The [initial-run-status.json](initial-run-status.json) records an earlier run: all 16 detailed correctness cases passed, then round two stopped on upstream base because the post-fill observation capture stalled. The fill itself succeeded. Cleanup succeeded. No partial samples were reused. The final five paired rounds were collected as one fresh run under the exclusive host build/benchmark lock, with the same timeout, assertions, and production code. All final samples are retained without filtering. Unfocused head medians were 3.6%, 2.4%, and 7.5% slower in this run. Five pairs cannot distinguish variability from a small regression; no unfocused improvement is claimed.

## Behavior witnesses

The focused normal replacements and clear perform zero field taps. Initially unfocused normal inputs and a target whose neighbour took focus retain both the focus and caret taps. The rejected-select-all fixture puts its caret at the beginning after refusing deletion; its exact replacement/clear and one fallback caret tap prove recovery. Genuine `SecureTextField` and AX-masked ordinary `TextField` inputs are seeded with `seedvalue` and tested focused/unfocused for both replacement and clear. Preparation asserts the genuine secure role/password attribute and nonempty bullet-only AX values. An independent app-owned label reads the underlying `UITextField.text` for every result.

- `focused-empty-fill`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `focused-prefilled-replace`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=0 selections=1 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `focused-clear`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=0 selections=1 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `unfocused-prefilled-replace`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=1 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `unfocused-clear`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=1 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `target-after-neighbour-focus`: taps=0 selections=1 rejected=0 targetFocus=0 neighbourFocus=1 -> taps=2 selections=2 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `rejected-select-all-replace`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=4 rejected=4 targetFocus=1 neighbourFocus=0; focus reused=true.
- `rejected-select-all-clear`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=4 rejected=4 targetFocus=1 neighbourFocus=0; focus reused=true.
- `secure-replace`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `secure-clear`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `focusedSecure-replace`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `focusedSecure-clear`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `masked-replace`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `masked-clear`: taps=0 selections=0 rejected=0 targetFocus=0 neighbourFocus=0 -> taps=2 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=false.
- `focusedMasked-replace`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.
- `focusedMasked-clear`: taps=0 selections=0 rejected=0 targetFocus=1 neighbourFocus=0 -> taps=1 selections=0 rejected=0 targetFocus=1 neighbourFocus=0; focus reused=true.

## Reproduce

Place [Fixture.swift](Fixture.swift), [batch.mjs](batch.mjs), and [live-proof.py](live-proof.py) together. Prepare separate clean source checkouts at the named base/head. Use repository-pinned pnpm and run `pnpm install --frozen-lockfile && pnpm build` in each checkout. Use Xcode and the compatible iOS Simulator runtime. Reserve a simulator using the repository/host lease mechanism, and hold the exclusive host build/benchmark lock around the entire subprocess. Keep the lease through cleanup.

```sh
python3 live-proof.py --workspace /path/to/private-results --base /path/to/base --head /path/to/head --udid <leased-udid> --rounds 5
```

The reproducer creates unique app/session/state values, builds separate runners in each checkout, closes its sessions and daemons, removes its synthetic app, and shuts down a simulator that it booted. Release the external lease afterward. No account, private app, or network backend is required. Keep generated raw outputs private.

## Historical evidence

[historical-5b26c9c-validation.json](historical-5b26c9c-validation.json) and [historical-5b26c9c-mutation.json](historical-5b26c9c-mutation.json) make the earlier inaccessible validation and rejected broader-deferral mutation results readable. They apply only to `5b26c9c6aae3ac7b2eb257e1d16f011e5284c1ec`, not the rebased head. The mutation replaced the focus-based deferral condition with `true`; the newly focused caret-preparation test failed with one tap instead of two.

[SHA256SUMS.json](SHA256SUMS.json) covers every published file except the manifest itself. Only reviewed synthetic evidence and aggregate timings are published on this separate evidence branch; it adds no files to the upstream PR.
