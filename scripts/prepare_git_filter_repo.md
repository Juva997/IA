Prepare git-filter-repo

This document explains how to safely remove sensitive strings from repository history using `git-filter-repo`.

Important safety notes:
- DO NOT run history rewrite on a repository that other collaborators are actively using without coordination.
- Always work on a fresh mirror clone and push the rewritten history to the remote only after confirming rotated secrets are in place.

Steps (recommended):

1. Create a local template with exact secrets to replace (do not commit secrets into the repository):

   - Edit `scripts/secret-replacements-template.txt` replacing the example lines with exact sensitive values and replacement placeholders.

2. Create a bare mirror of the repository:

```bash
git clone --mirror <repo-url> repo.git
cd repo.git
```

3. Run `git-filter-repo` with the replace-text file:

```bash
# install git-filter-repo if not available (system dependent)
# Then:
git filter-repo --replace-text ../scripts/secret-replacements.txt
```

4. Push rewritten history to remote (force):

```bash
git push --force --all
git push --force --tags
```

5. In collaborators' clones: re-clone or follow git-filter-repo recommended recovery steps.

If you prefer `bfg`, consult its docs; `git-filter-repo` is recommended for finer control.

Template placeholder file: `scripts/secret-replacements-template.txt` (copy to `scripts/secret-replacements.txt` locally and fill with exact values).
