# policyengine-taxsim

See [PolicyEngine/CLAUDE.md](../CLAUDE.md) for org-wide conventions.

## Changelog

**Never manually edit `CHANGELOG.md`.** It is auto-generated on merge by towncrier.

Instead, add a fragment file in `changelog.d/`:

```bash
echo "Description of change." > changelog.d/<branch-name>.<type>.md
```

Fragment types and their semver bumps:
- `breaking` → **major** (reserved for breaking API changes)
- `added` → **minor**
- `removed` → **minor**
- `changed` → **patch**
- `fixed` → **patch**

Fragment names can be anything (branch name, issue number, short description). Examples:
- `changelog.d/add-new-endpoint.added.md`
- `changelog.d/fix-age-default.fixed.md`
- `changelog.d/123.fixed.md`

## Running tests

```bash
pytest tests/
```
