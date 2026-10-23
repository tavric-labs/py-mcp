# Docs Deployment

The documentation is built with [VitePress](https://vitepress.dev) and the shared
Tavric Labs docs theme, and published to Tavric Labs' docs host.

## Published URL

- `https://py-mcp.tavric-labs.net/`

Pages are served at `/<page>/`, for example `/getting-started/` and `/tasks/`.

## Local Preview

The docs are a small Node project (Node 22 or newer):

```bash
npm ci
npm run docs:dev
```

The local preview runs at `http://localhost:5173/` by default. `npm run docs:build`
builds the site into `docs/.vitepress/dist` and fails on dead links.

## Theme

Layout, colours, diagrams and search come from the shared
[`@tavric-labs/docs-theme`](https://github.com/tavric-labs/docs-theme) package, which
every Tavric Labs docs site installs so they look and behave the same.
`docs/.vitepress/config.mjs` only describes this site: its name, repository,
navigation and sidebar. To change the design, change the theme package, tag a
release, and update the tarball URL in `package.json`.

## CI Workflow

The deployment flow lives in `.github/workflows/docs.yml`.

It does three things:

- builds the site (and fails on dead links) on pushes and pull requests that touch `docs/**`, `package.json`, or the docs workflow itself
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
- update navigation, the sidebar and the `rewrites` list in `docs/.vitepress/config.mjs`
- keep the hosted links in `README.md` aligned with the pages you expose
