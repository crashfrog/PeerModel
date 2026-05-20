# Domain Docs — Single-Context Layout

This repo uses a single-context architecture:

```
.
├── CONTEXT.md           ← domain language, vocabulary, key concepts
├── docs/adr/            ← architecture decision records
│   ├── 0001-xyz.md
│   └── ...
└── [source code]
```

## What CONTEXT.md should contain

- Domain vocabulary (the language stakeholders use)
- Key entities and their relationships
- System boundaries and integrations
- Important invariants or constraints

Skills like `improve-codebase-architecture` and `diagnose` read CONTEXT.md to learn the domain before suggesting changes.

## What docs/adr/ should contain

Architecture Decision Records (ADRs) documenting:
- Why a design choice was made
- Tradeoffs considered
- What alternatives were rejected

Use the [Nygard ADR format](https://github.com/joelparkerhenderson/architecture_decision_record):

```
# ADR-NNN: Title

## Status

Accepted / Proposed / Deprecated

## Context

Why this decision was necessary.

## Decision

What we decided to do.

## Consequences

What changed as a result.

## Alternatives

What we rejected and why.
```

## Creating your first CONTEXT.md

If you don't have a CONTEXT.md yet, start with:

```markdown
# PeerModel Domain Context

[Brief overview of what the system is]

## Key Entities

- Entity 1: definition
- Entity 2: definition

## Invariants

- Invariant 1
- Invariant 2

## Integrations

- External service 1: what it does
- External service 2: what it does
```

Then expand over time as patterns emerge.
