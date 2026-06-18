# AGENTS.md

## Repository purpose

SeigaBlog is a GitHub Pages / Jekyll static blog.

The LoL patch automation generates Korean/Japanese League of Legends patch posts using Riot official patch notes and Riot Data Dragon locale data.

## Critical rules

- Do not rebuild the blog from scratch.
- Preserve the existing Jekyll structure.
- Preserve the existing custom frontmatter structure.
- Preserve Korean/Japanese multilingual fields.
- Do not replace the current card/detail panel rendering model with plain Markdown unless explicitly requested.
- Do not leave sample, dummy, placeholder, or test text in production posts.
- Do not directly push generated posts to main from automation. Use a Pull Request.

## LoL content rules

- Never invent League of Legends patch data.
- Never invent champion changes.
- Never invent win rate, pick rate, ban rate, sample size, tier, or region.
- If data is not present in the structured input, do not mention it.
- Separate official patch-note facts from solo queue interpretation.
- Use cautious language for early patch analysis.
- Avoid exaggerated claims.

## Champion naming rules

- Use Riot Data Dragon official locale data.
- Korean visible champion names must use `ko_KR`.
- Japanese visible champion names must use `ja_JP`.
- English champion keys are only for file paths and data identifiers.
- Do not machine-translate champion names.

## Required checks before PR

Run:

```bash
npm run sync:lol
npm run fix:champions
npm run generate:blog-images
npm run validate:blog
npm run build
```
