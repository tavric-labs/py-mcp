import { defineDocsConfig } from '@tavric-labs/docs-theme/config'

// The old MkDocs site served every page at /<page>/. Keep those URLs working
// (README, PyPI metadata and external links point at them) by emitting each
// page as <page>/index.html.
const pages = [
  'getting-started',
  'middleware',
  'tasks',
  'security',
  'runtime-surface',
  'deployment',
  'release',
  'docs-plan'
]
const rewrites = Object.fromEntries(pages.map((page) => [`${page}.md`, `${page}/index.md`]))

export default defineDocsConfig({
  name: 'PyMCP Kit',
  repo: 'tavric-labs/py-mcp',
  siteUrl: 'https://py-mcp.tavric-labs.net',
  branch: 'master',
  description:
    'An opinionated implementation of the Model Context Protocol for FastAPI, with Streamable HTTP and stdio transport.',
  nav: [
    { text: 'Getting started', link: '/getting-started/' },
    {
      text: 'Guides',
      activeMatch: '^/(middleware|tasks|security)/',
      items: [
        { text: 'Middleware', link: '/middleware/' },
        { text: 'Tasks', link: '/tasks/' },
        { text: 'Security', link: '/security/' }
      ]
    },
    { text: 'Reference', link: '/runtime-surface/' },
    {
      text: 'Development',
      activeMatch: '^/(deployment|release|docs-plan)/',
      items: [
        { text: 'Docs deployment', link: '/deployment/' },
        { text: 'Release process', link: '/release/' },
        { text: 'Documentation plan', link: '/docs-plan/' }
      ]
    },
    { text: 'PyPI', link: 'https://pypi.org/project/pymcp-kit/' }
  ],
  sidebar: [
    { text: 'Get started', items: [{ text: 'Getting started', link: '/getting-started/' }] },
    {
      text: 'Guides',
      items: [
        { text: 'Middleware', link: '/middleware/' },
        { text: 'Tasks', link: '/tasks/' },
        { text: 'Security', link: '/security/' }
      ]
    },
    { text: 'Reference', items: [{ text: 'Runtime surface', link: '/runtime-surface/' }] },
    {
      text: 'Development',
      items: [
        { text: 'Docs deployment', link: '/deployment/' },
        { text: 'Release process', link: '/release/' },
        { text: 'Documentation plan', link: '/docs-plan/' }
      ]
    }
  ],
  extra: { rewrites }
})
