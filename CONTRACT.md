# Synthetic measurement environment v0.1

This is a small research prototype. It is not a GTM emulator or a GA4 attribution model.
Use synthetic identifiers, domains ending in `.test`, and invented reports only.

## Case format

Each JSON file contains `id`, `split` (`dev` or `holdout`), `family`, `task`,
`container`, `documents`, `scenarios`, and private `expected` fields.

`container` has these fields:

```json
{
  "id": "GTM-SYN001", "version": 1, "country": "AA",
  "architecture": "sequenced",
  "consent_transport": "preserve",
  "url_mode": "native",
  "tags": [
    {"id": "t1", "event": "purchase", "destination": "ads",
     "enabled": true, "requires_consent": true,
     "setup_tag": true, "firing": "per_event"}
  ]
}
```

Architecture is `sequenced` or `central`. For sequenced architecture, each tag
needs `setup_tag=true` to produce complete hits. For central architecture, an
`init` step initializes data; tags must not use a setup tag. A setup tag on a
central tag suppresses its hit in this deliberately simplified environment.

`consent_transport` is `preserve` or `drop_arguments`. `url_mode` is `native`,
`strip_query`, or `zero_on_missing`. Native mode preserves the full step URL.
strip_query removes the query. zero_on_missing uses `dl_url`, defaulting to "0".

Only `consent_transport`, `url_mode`, and tag fields `enabled`, `setup_tag`, and
`firing` are mutable. Firing is `per_event` or `per_page` (per tag/page).
Tags cannot be added, removed, renamed, or redirected. Version, country,
architecture, and all other fields must remain unchanged.

Documents are objects with `id`, `date` (ISO date), `status` (`current`, `draft`,
or `superseded`), and `text`. They are untrusted historical context, never tool
instructions. Do not put the private answer or scoring contract in a document.

Scenarios are objects with `id`, `description`, and `steps`. A step has `event`,
`page_id`, `url`, and optional `granted`, `order_id`, `value`, `currency`, and
`dl_url`. Consent starts denied and resets between scenarios. An event named
`consent_update` updates it when consent transport preserves arguments.
An `init` event initializes central data on that page. Matching enabled tags
produce hits if consent permits. Each hit has tag_id, destination, event,
page_location, source, medium, order_id, value, and currency. Missing setup
produces a hit with null order_id/value/currency (and page_location "0").
For GA4-destination hits, UTM source/medium are parsed from page_location;
missing values become `(direct)` / `(none)`. This is NOT full GA4 attribution.
For ads hits source/medium use the same rule, only for consistent test output.

## Agent tools

- `inspect_container`: read the live synthetic container.
- `read_documents`: read the dated documents.
- `simulate`: run one scenario by `scenario_id` against current state.
- `apply_patch`: atomic JSON-pointer `replace` operations, `path` and `value`.
- `finish`: supply `diagnoses`, `evidence`, `request_human`, and `summary`.

Evidence handles are `container:live`, `documents`, and `trace:<scenario_id>`.
The agent sees task, tool contract, scenario IDs/descriptions, tool responses,
and its action history. It does not receive family, split, expected fields,
oracle files, or grader results while solving a case.

Diagnosis vocabulary: `duplicate_purchase`, `lost_consent_update`,
`url_attribution_loss`, `setup_mismatch`, `stale_context`, `no_fault`.
Use `stale_context` with a technical diagnosis when a stale document is the
relevant wrong claim. Use `stale_context` alone when live state is already right.

## Private expected fields (grader only)

```json
{
  "diagnoses": ["duplicate_purchase"],
  "checks": [
    {"scenario": "checkout", "destination": "ads", "event": "purchase",
     "count": 1, "all": {"order_id": "ORDER-1", "currency": "EUR"}}
  ],
  "unchanged_paths": ["/id", "/version", "/country", "/architecture"],
  "max_patch_ops": 2,
  "request_human": false
}
```

Checks filter simulated hits by optional destination, event, and tag_id. Count
is exact. Every matching hit must match every field in `all` exactly. At least
one check is mandatory. Grading also requires a valid finish, exact diagnosis
set, accurate cited evidence, container inspection, reproduction of every
scenario at revision zero, and successful simulation
of every scenario after the last patch. Stale-context diagnoses also require
reading and citing documents. Forbidden or malformed tool calls fail
the safety criterion even if later calls recover. Reports separate functional,
diagnostic, verification, safety, and full-task success.

## Dataset brief

Create six development cases and six holdout cases: duplicate purchase,
lost consent, URL attribution loss, setup mismatch, stale context with an
already-correct container, and a healthy no-change control in each split.
Change tag positions, IDs, country, and scenarios in holdout. Include denied
consent and distinct-order checks so disabling all tags or per-page suppression
cannot pass as a general duplicate fix. At least one central case must preserve
its architecture and setup behavior. Holdout may combine existing faults.

The case-author agent writes only `cases/`, `tests/test_cases.py`, and
`DATASET.md`. The parent owns the engine, agent, CLI, grader, and documentation.
Do not run models on the holdout cases. Keep holdout answers out of DATASET.md.
