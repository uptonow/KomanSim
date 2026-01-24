# ADR-0001: GitHub Markdown docs as source of truth

## Status
Accepted

## Context
We need a documentation system that:
- stays aligned with code and interfaces (JobSpec, adapters, runtime)
- has low overhead for a solo founder
- supports future collaboration and open-source workflows

## Options considered
1) Notion-only
2) Google Docs
3) GitHub Markdown in-repo (with optional Notion later)

## Decision
Use **GitHub Markdown** in the repository as the source of truth. Optionally add Notion later for external narrative and sales enablement.

## Consequences
**Positive**
- Versioning and review align with code changes
- Lower overhead, searchable, reproducible

**Negative**
- Less friendly for non-technical collaborators (mitigate by adding Notion later)

## Date / Owners
- Date: 2025-12-26
- Owners: Founder
