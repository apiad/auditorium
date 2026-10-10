---
when: cutting a release of auditorium to PyPI, bumping its version, or a published version does not sort above an old one
---

# Releasing auditorium

PyPI publishing is automatic once a GitHub release is published:
`.github/workflows/deploy.yaml` builds with `uv build` and uploads through PyPI's
trusted publisher, so no token is involved.

1. On a branch, bump the version in both places it lives: `version` in
   `pyproject.toml` and the string printed by `_version_callback` in
   `auditorium/cli.py`. They are separate literals, and nothing checks that they
   match.
2. Give `CHANGELOG.md` a heading for the version, open the PR, and merge it on
   green CI.
3. Publish the release from `main`:

   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
   ```

4. Confirm the published artifact, not the tag:

   ```bash
   gh run list --workflow deploy.yaml --limit 1
   uvx --from 'auditorium==1!X.Y.Z' auditorium --version
   ```

## Traps

- **Keep the `1!` epoch in `pyproject.toml`.** Releases before 2.0 used calendar
  versions such as `20.2.1`, which sort above any plain `4.0.0`. The PEP 440 epoch
  makes every semver release sort higher. Git tags stay plain (`v4.0.0`).
- **A tag on `main` is not a release.** The workflow fires on `release:
  published`, so `git tag` plus `git push --tags` publishes nothing.
