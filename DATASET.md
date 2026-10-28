# Dataset notes

This dataset contains 12 invented measurement cases: six development cases and
six reserved holdout cases. No client exports, personal data, production IDs,
credentials, or real domains are included.

Development cases cover duplicated purchases, consent transport, URL campaign
values, architecture-dependent setup, superseded notes, and healthy controls.
The public synthetic environment is defined in `CONTRACT.md`.

Every case has three flows: a consented checkout, a denied-consent checkout, and
two distinct orders on the same page. Checks preserve both purchase and visit
reporting. These controls prevent a blanket tag shutdown or per-page firing
limit from looking like a successful duplicate repair.

Holdout fixtures change identifiers, tag positions, market, and scenario names.
They also vary environment settings within the published contract. Do not read
their private `expected` fields while developing agent logic or prompts. Do not
put holdout diagnoses or patches in this document.

The `expected` object is a private grader contract. It must never be included in
agent observations, tool results, logs supplied back to the agent, or repair
prompts. `family` and `split` are also evaluation metadata, not observations.
The public task and scenario descriptions are deliberately not answer labels.

These examples test a small explicit interpreter. They do not reproduce the
full GTM runtime, Advanced Consent Mode, GA4 session attribution, vendor
deduplication, browser behavior, or data-processing delays. Passing these cases
does not establish that an agent can repair a production implementation.

Six holdout cases are too few for strong performance claims. Results on this
set are a pilot and become development evidence after inspection. Future
versions need new untouched cases and independent case authors.

The local schema tests run with:

```bash
python3 -m unittest discover -s tests -p 'test_cases.py' -v
```
