# ADR-0001: The record of work is separated by the question it answers

- Status: accepted
- Date: 2026-08-30
- Affects: docs/adr/, docs/issues/, docs/proposals/, docs/reviews/, AGENTS.md

## Context

The repository kept review findings under `.agent-review/`, while product specifications and manual
QA debt lived under `docs/`. The hidden review directory started as tool output, but its roadmap is
now a human-maintained backlog with decisions and statuses. A second backlog appeared in
`docs/manual-qa-pending.md`.

The 2026-08-30 review of agent integration also exposed a taxonomy problem: a capability that does
not exist yet (MCP gateway, durable jobs and installer integration) was recorded as five defects.
That makes severity answer both "how harmful is an existing gap?" and "how much do we want a new
feature?", so neither list remains trustworthy.

## Decision

The complete record of work lives under `docs/`, separated by the question it answers:

- `docs/adr/` records why a durable decision was made and what was rejected;
- `docs/issues/` records evidence-backed defects and debt relative to behavior already shipped or
  explicitly accepted;
- `docs/proposals/` records capabilities the product may gain next;
- `docs/reviews/` records dated observations from review and verification runs.

An issue is one self-contained file. Its live status and human decisions exist only in
`docs/issues/roadmap.md`; frontmatter `status: proposed` records creation state only. Issues use the
existing category IDs and add `source: review | work | adr`. An issue found during ordinary work is
created only after the user agrees and only after checking for a duplicate.

A proposal is one numbered file. Its live status exists only in `docs/proposals/README.md`:
`planned -> in-progress -> shipped`, plus `deferred` and `dropped` with a reason. Proposal files
describe intent, constraints and readiness criteria, not status. A missing part of a `planned`
proposal is not debt. Once a proposal is `in-progress` or `shipped`, an unfinished promised part is
filed as an issue.

Manual verification that remains necessary is technical debt and uses `docs/issues/`; completed
manual verification is dated evidence in `docs/reviews/`. There is no separate QA backlog.

`project-review` writes to `docs/`, placing issue files and their index/roadmap under
`docs/issues/` and snapshots under `docs/reviews/`. Closed issues and shipped proposals remain in
place; IDs and numbers are never reused.

## Consequences

- A visible `docs/` tree answers where decisions, debt, proposals and dated evidence live.
- Product priority no longer masquerades as severity.
- The existing review history must move without changing IDs, statuses or human decisions.
- The agent-integration findings are consolidated into a proposal before they become repository
  history as defects.
- Documentation tests can enforce membership and single status carriers, but status correctness
  remains a human judgement.

## Alternatives considered

**Keep `.agent-review/` and link to it from `docs/`.** Rejected because the roadmap is no longer
tool-private output; a pointer preserves two documentation roots.

**Keep proposals in the issue roadmap.** Rejected because severity measures impact of an existing
problem, while proposal priority is a product choice.

**Keep `manual-qa-pending.md` as a specialist backlog.** Rejected because it duplicates open/closed
status and is invisible to the normal debt workflow.
