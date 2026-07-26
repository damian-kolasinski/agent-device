# Dependency graph viewer

```sh
pnpm depgraph                       # -> .tmp/depgraph/index.html (+ index.json)
pnpm depgraph --out /tmp/graph.html
pnpm depgraph:test
```

Renders every production file under `src/` (tests excluded) as an interactive graph in a
single self-contained HTML file — no external requests, no build step, no runtime
dependency. Open it from `file://`, publish it as a static page, or embed it.

## Why it reuses the layering gate

The graph is extracted with `scripts/layering/model.ts`, the same module
`scripts/layering/check.ts` uses in CI. File set, zone partition, edge kinds
(value / type-only / dynamic), and cycle definition are therefore identical to the rules
the gate enforces — a separate extractor with its own resolution behaviour would draw a
graph nobody is enforcing. Cross-checked once against `dependency-cruiser` 3.1.1: same 891
modules, same 4516 edges, plus 88 dynamic/type-only edges it fails to resolve.

## What the view encodes

- **Colour** is the ranked spine (`kernel` sink → `cli`); zones sharing a rank differ in
  lightness. Unranked zones (`UNRANKED_ZONES`) get a muted palette of their own, because
  the gate deliberately asserts no ordering over them.
- **Size** is coupling, dependents, or lines — dependents is the blast-radius metric.
- **Clusters** layout: folder groups placed by how much they import from each other, then
  files relaxed inside their group. Tight blobs are cohesive; long bridges are coupling.
- **Layers** layout: x is the longest path to a leaf over static value imports. R4
  guarantees that subgraph is a DAG, so every edge should read leftwards.
- **Overlays** for spine back-edges (R5), import cycles, and transitively redundant edges.

A "redundant" edge means the target is still reachable from the source at distance >= 2
over value edges, so removing the direct import would not change what the module can see.
That makes it a _candidate_, not a defect: plenty of direct imports are clearer than
relying on a re-export chain.

Layouts are computed at build time and shipped as coordinates, so the viewer never runs a
physics simulation on the reader's phone, and the same commit always renders identically.
