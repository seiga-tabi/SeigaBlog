# AGENTS.md

## Repository purpose

SeigaBlog is a GitHub Pages / Jekyll static blog.

The LoL patch automation generates Korean/Japanese League of Legends patch posts using Riot official patch notes and Riot Data Dragon locale data.

The Minecraft Java automation generates Korean/Japanese Minecraft Java Edition update posts using Mojang/Minecraft official sources only.

The Minecraft Bedrock automation generates Korean/Japanese Minecraft Bedrock Edition update posts using Mojang/Minecraft official sources only.

## Critical rules

- Do not rebuild the blog from scratch.
- Preserve the existing Jekyll structure.
- Preserve the existing custom frontmatter structure.
- Preserve Korean/Japanese multilingual fields.
- Do not replace the current card/detail panel rendering model with plain Markdown unless explicitly requested.
- Do not leave sample, dummy, placeholder, or test text in production posts.
- Do not directly push generated posts to main from automation. Use a Pull Request.

## Minecraft Bedrock content rules

- Never merge Bedrock Edition and Java Edition into one generated post.
- Bedrock posts must use `category: minecraft`, `content_type: minecraft_bedrock_update`, and `edition: bedrock`.
- Use only official Minecraft/Mojang source pages for Bedrock update facts.
- Exclude Java Edition, Snapshot, Pre-Release, Release Candidate, Education, Dungeons, Legends, Marketplace, unofficial add-on updates, and unsourced rumors.
- Do not describe Beta or Preview content as a stable release.
- Do not invent version numbers, release dates, features, bug fixes, supported platforms, Realms compatibility, Add-On compatibility, or world compatibility.
- Platform-specific availability must be recorded only when the official source states it.
- If the official source page cannot be opened, do not generate a Bedrock post.
- Create or update a pull request only after Bedrock validation, full blog validation, and Jekyll build pass.

## Minecraft Java content rules

- Never merge Java Edition and Bedrock Edition into one generated post.
- Java posts must use `category: minecraft`, `content_type: minecraft_java_update`, and `edition: java`.
- Use only official Minecraft/Mojang source pages for Java update facts.
- Exclude Bedrock Edition, Beta & Preview, Marketplace, Education, Dungeons, Legends, unofficial mod updates, unofficial server updates, and unsourced rumors.
- Do not describe Snapshot, Pre-Release, or Release Candidate content as a stable release.
- Do not invent version numbers, release dates, features, bug fixes, data pack versions, server compatibility, mod compatibility, or world compatibility.
- If the official source page cannot be opened, do not generate a Java post.
- Create or update a pull request only after Java validation, full blog validation, and Jekyll build pass.

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

## Daily LoL intelligence rules

- Daily automation runs at 12:00 Asia/Tokyo.
- Daily execution does not require daily publication.
- Do not create filler or duplicate posts when no meaningful new information exists.
- Never invent patch data, dates, patch numbers, statistics, champions, builds, or schedules.
- Clearly separate confirmed, scheduled, planned, considered, PBE, reported, and rumor information.
- PBE content must never be described as confirmed live content.
- Community rumors must never be automatically published.
- Preserve the existing SeigaBlog frontmatter and Korean/Japanese structure.
- Use Riot Data Dragon official ko_KR and ja_JP champion names.
- Do not push generated content directly to main.
- Create or update a pull request only after validation and Jekyll build pass.

## Review guidelines

- Treat unsupported factual claims as blocking issues.
- Treat missing source URLs as blocking issues.
- Treat incorrect information status as blocking issues.
- Treat missing Korean or Japanese content as blocking issues.
- Treat rumor auto-publication as a blocking issue.
- Treat duplicate posts and broken slugs as blocking issues.
- Verify that scheduled workflows do not overlap.

## Revenue goal

- The monthly ad revenue target is USD 200, but no revenue result is guaranteed.
- Never manipulate ad clicks, ad impressions, search rankings, or traffic.
- Never create low-value pages merely to increase page count.
- Revenue optimization must preserve content quality and user experience.
- Never report assumed revenue, Page RPM, or traffic as actual performance.

## Content

- Never invent League of Legends facts, statistics, dates, patches, sources, builds, or schedules.
- Prefer updating an existing page over creating a duplicate page.
- Do not publish community rumors automatically.
- Do not copy or lightly rewrite official Riot content.
- Each public article must add original analysis, comparison, visualization, or actionable guidance.
- Disclose substantial AI or automation use.
- Preserve Korean and Japanese quality.
- Keep official facts, PBE information, reported information, rumors, and interpretation clearly separated.

## Ads

- Do not enable AdSense without explicit configuration and approval.
- Never use placeholder publisher IDs in production.
- Do not place ads near navigation, buttons, or interactive champion cards.
- Never add language that encourages ad clicks.
- Do not show ads on thin, draft, policy, error, or rumor-only pages.
- Do not render ad scripts or empty ad containers while `ADSENSE_ENABLED=false`.

## SEO

- Preserve canonical URLs and existing slugs.
- Homepage must not render full bodies of every post.
- Each article needs a unique indexable URL.
- Do not keyword-stuff titles, headings, tags, or alt text.
- Do not change dates without a substantive content update.
- Treat hash URLs as legacy compatibility paths, not canonical URLs.

## Git

- Do not push generated content directly to main.
- Run all validation commands before creating a PR.
- Treat unsupported facts, broken canonical URLs, missing sources, and exposed secrets as blocking issues.

## Codex review blocking issues

- Treat ad policy violations as P0 or P1.
- Treat unsupported facts as P0 or P1.
- Treat false revenue numbers as P0 or P1.
- Treat exposed secrets as P0 or P1.
- Treat duplicate content as P0 or P1.
- Treat canonical errors as P0 or P1.
- Treat rumor auto-publication as P0 or P1.
- Treat PBE content described as confirmed live content as P0 or P1.
- Treat homepage full-body rendering regressions as P0 or P1.
- Treat AdSense activation before approval as P0 or P1.
- Treat missing Riot legal notices as P0 or P1.
