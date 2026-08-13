# Source checkpoint manifest

Use this manifest when creating a reviewable source checkpoint. It deliberately excludes local runtime data, credentials, caches, temporary renders, and large delivery binaries. Never use `git add .` for this repository.

## Include

| Group | Paths |
| --- | --- |
| CI and configuration | `.github/workflows/ci.yml`, `.gitignore`, `.env.example`, `Dockerfile`, `docker-compose.yml` |
| Frontend source | `app.js`, `index.html`, `style.css`, `presentation.html`, `endcard.html` |
| Backend source | `backend/*.py`, `backend/requirements*.txt`, `backend/migrations/*.sql`, `backend/policies/*.json` |
| Application contracts | `contracts/*.md` |
| Verification | `tests/**/*.py`, `tests/frontend/*.mjs` |
| Documentation | `README.md`, `docs/*.md` |

The files under `presentation-final/*.png` are optional submission deliverables. Add them only after visual approval and keep them in a separate asset commit.

## Exclude

- Real `.env` variants, credentials, tokens, private keys, certificates, and secret-manager exports.
- `*.db`, `*.sqlite*`, database journals, dumps, volumes, and other runtime state.
- `tmp/`, PDF page renders, `__pycache__/`, `*.pyc`, `.pytest_cache/`, coverage output, logs, PID files, and `.DS_Store`.
- `presentation-final/*.mp4`; publish large videos through an approved artefact store or release attachment. Do not add them as ordinary Git blobs.
- Dependency environments and generated build directories.

## Repeatable checkpoint

First remove the legacy tracked bytecode entry from the index while retaining the ignored local file:

```bash
git rm --cached -- backend/__pycache__/guardrails.cpython-312.pyc
```

Then stage only the approved source groups:

```bash
git add -- \
  .github/workflows/ci.yml .gitignore .env.example \
  Dockerfile docker-compose.yml \
  README.md contracts docs \
  backend tests \
  app.js index.html style.css presentation.html endcard.html
```

Before committing, inspect the complete staged inventory and run the same checks as CI:

```bash
git diff --cached --name-status
git diff --cached --check
PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' \
  python -m pytest -q
node --check app.js
node --test tests/frontend/*.test.mjs
```

Stop if the staged inventory contains any excluded path or unexpected binary. Commit and push only after the source inventory, secret-safe CI result, and test results have been reviewed.
