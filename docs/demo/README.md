# Historical demo materials

These walkthroughs, screenshots, and browser scripts document the early
platform demo. They contain retired URLs and must not be treated as current
production instructions.

To regenerate a walkthrough HTML file:

```bash
npm ci
node md_to_html.js CSIS_Demo_Walkthrough.md
```

The Playwright demo has its own lock file under `playwright_demo/`. Install its
dependencies locally with `npm ci`; generated `node_modules`, command state,
and logs are intentionally not tracked.
