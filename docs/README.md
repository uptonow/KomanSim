# Documentation Index

This directory contains developer-facing documentation for KomanSim.

## User Guide

- **[User Guide](USER_GUIDE.md)** - Comprehensive guide with all features, examples, and workflows

## Engineering Documentation

### Core Concepts

- **[Architecture](20-engineering/architecture.md)** - System design and backend contract
- **[JobSpec Reference](20-engineering/jobspec.md)** - Configuration schema and validation
- **[Runtime API](20-engineering/runtime.md)** - Programmatic job execution API

### Implementation Details

- **[Config Validation](20-engineering/config-validation.md)** - Resource limits and validation rules
- **[Reproducibility](20-engineering/reproducibility.md)** - Config hashing, manifest generation, and reproducibility guarantees
- **[Canonical Annotations](20-engineering/canonical-annotations-spine.md)** - Canonical annotations and bbox labeler
- **[Exporters & Packaging](20-engineering/exporters-packaging.md)** - COCO/YOLO exporters and dataset packaging
- **[Local Registry & Caching](20-engineering/local-registry-caching.md)** - Dataset registry and caching system
- **[QA & Previews](20-engineering/qa-previews.md)** - Quality assurance and preview generation

### Backends

- **[Backends](20-engineering/backends/)** - Backend implementations

### Operations

- **[Troubleshooting](20-engineering/troubleshooting.md)** - Common issues and solutions
- **[Security](20-engineering/security.md)** - Security considerations
- **[Quality Gates](20-engineering/quality-gates.md)** - Quality assurance gates

### Decision Records

- **[ADRs](20-engineering/adrs/)** - Architecture Decision Records
- **[ADR Template](20-engineering/adr-template.md)** - Template for new ADRs

---

**Note:** Business/MVP documents (pricing, strategy, GTM, roadmap) are maintained privately and not included in this open-source release.
