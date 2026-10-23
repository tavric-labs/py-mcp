# Docs Deployment

The documentation is built with MkDocs Material and published to Tavric Labs' docs host.

## Published URL

- `https://py-mcp.tavric-labs.net/`

## Local Preview

Install the docs dependencies and run MkDocs locally:

```bash
pip install -e '.[docs]'
mkdocs serve
```

The local preview runs at `http://127.0.0.1:8000/` by default.

## CI Workflow

The deployment flow lives in `.github/workflows/docs.yml`.

It does three things:

- builds the site with `mkdocs build --strict` on pushes and pull requests that touch `docs/**`, `mkdocs.yml`, or the docs workflow itself
- comments on pull requests when the docs build passes
- on pushes to `main` or `master`, uploads the built site over SSH as an immutable release and checks that the public `_deployment.json` reports the commit

The host keeps the five newest releases and serves the latest one, so a failed deploy never takes the site down.

## Repository Setup

Deploys are gated on the repository variable `DOCS_DEPLOY_ENABLED == 'true'`. The workflow also needs:

- secrets `DOCS_DEPLOY_SSH_KEY` and `DOCS_DEPLOY_KNOWN_HOSTS`
- variables `DOCS_DEPLOY_HOST`, `DOCS_DEPLOY_USER`, and `DOCS_DEPLOY_PORT`

The deploy key can only publish to this site. The docs host and the checklist for adding a new site are documented in the [tavric-labs-website repository](https://github.com/tavric-labs/tavric-labs-website/tree/main/deploy/docs-host).

## What To Edit

- add or update pages under `docs/`
- update navigation in `mkdocs.yml`
- keep the hosted links in `README.md` aligned with the pages you expose
