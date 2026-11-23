# Article bundle

Everything needed to publish the write-up for this repo.

| File | Use |
|---|---|
| [ARTICLE.md](ARTICLE.md) | Medium-ready article (front matter has title, subtitle, tags) |
| [LINKEDIN.md](LINKEDIN.md) | One-line post + a longer variant |
| [images/architecture.png](images/architecture.png) | Hero image / architecture |
| [images/results.png](images/results.png) | Results card |
| [images/flow.png](images/flow.png) | End-to-end request flow |
| [../docs/](../docs) | DEPLOYMENT, PROMOTION, EVALS, TEST-CASES, ARCHITECTURE, THREAT-MODEL, RUNBOOK |

## Before publishing
1. Run the EKS deployment (docs/DEPLOYMENT.md) and replace the _[update after the EKS run …]_ paragraph with the numbers.
2. Read it once aloud; change anything that does not sound like you.
3. Decide the canonical home first (see below). If you want the Kubernetes blog, submit there **before** publishing anywhere else: it only accepts original, unpublished content.

## Publishing order (keeps SEO credit with you)
1. Canonical: your own blog (Hashnode with a custom domain, or GitHub Pages), or Medium if you want Medium to be the home.
2. Medium: **Import a story** with the canonical URL (pasting the text does not keep the canonical).
3. dev.to: set `canonical_url` in the post settings.
4. LinkedIn: the one-liner with the link, the architecture image attached.
5. Submit the link to the KubeWeekly newsletter form (accepts articles published within the last month).

Images: upload the PNGs directly; Medium does not render Mermaid.
