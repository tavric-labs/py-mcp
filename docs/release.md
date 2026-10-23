# Release Process

Package publishing is tag-driven. The `Publish on Tag` workflow runs for `v*`
tags, builds the package, creates or updates the GitHub Release, uploads the
distributions as release assets, and publishes to PyPI with `twine`.

## Prepare a Release

1. Update the package version in `pyproject.toml`.
2. Update the default server version in `pymcp/settings.py`.
3. Update docs or tests that mention the default version.
4. Run the test suite and docs build locally.

```bash
pytest
npm ci
npm run docs:build
```

## Publish

Create and push a tag whose version exactly matches `pyproject.toml`:

```bash
git tag v0.3.0
git push origin v0.3.0
```

The workflow verifies that the pushed tag without the leading `v` matches the
package version. For example, tag `v0.3.0` must match `version = "0.3.0"`.

## After Publish

- Check the `Publish on Tag` workflow run.
- Confirm the GitHub Release contains the built distributions.
- Confirm the new version is visible on PyPI.
- Confirm the documentation deploy completes after the release changes merge.
