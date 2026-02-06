# policyengine-taxsim

See [PolicyEngine/CLAUDE.md](../CLAUDE.md) for org-wide conventions.

## Changelog

**Never manually edit `CHANGELOG.md` or `changelog.yaml`.** These are auto-generated on merge.

Instead, create or update `changelog_entry.yaml` at the repo root:

```yaml
- bump: patch|minor|major
  changes:
    added|changed|removed|fixed:
    - Description of change
```

## Running tests

```bash
pytest tests/
```
