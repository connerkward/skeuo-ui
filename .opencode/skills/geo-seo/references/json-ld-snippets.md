# schema.org JSON-LD — copy-paste snippets

Embed each as `<script type="application/ld+json">…</script>`, typically in `<head>`.
Replace placeholder values. Validate with Google's Rich Results Test or
schema.org's validator before shipping. Multiple entities on one page: wrap in
`{"@context":"https://schema.org","@graph":[ …blocks… ]}`.

These are the **legitimate** machine-readable channel — they are NOT cloaking (see
SKILL.md §4). They describe the page's real, visible content; do not use JSON-LD to
assert content that isn't on the page.

## Person (author / identity entity)
```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Conner Ward",
  "url": "https://connerward.com",
  "sameAs": [
    "https://github.com/connerkward",
    "https://twitter.com/…",
    "https://www.linkedin.com/in/…"
  ],
  "jobTitle": "…",
  "knowsAbout": ["…", "…"]
}
```
`sameAs` is the key GEO field — it links all your identity profiles to one entity so
engines resolve them as the same person.

## BlogPosting / Article
```json
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": "Entity name — one-line definition",
  "description": "X is a Y that does Z.",
  "datePublished": "2026-06-12",
  "dateModified": "2026-06-12",
  "author": { "@type": "Person", "name": "Conner Ward", "url": "https://connerward.com" },
  "mainEntityOfPage": { "@type": "WebPage", "@id": "https://connerward.com/post-slug" },
  "image": "https://connerward.com/post-slug/cover.jpg"
}
```
Use `Article` for general; `BlogPosting` for blog posts. Keep `headline` ≤110 chars.

## CreativeWork (render / design / mixed media with no more specific type)
```json
{
  "@context": "https://schema.org",
  "@type": "CreativeWork",
  "name": "Work title",
  "description": "X is a Y that does Z.",
  "creator": { "@type": "Person", "name": "Conner Ward" },
  "dateCreated": "2026-06-12",
  "url": "https://connerward.com/work-slug",
  "image": "https://connerward.com/work-slug/still.jpg"
}
```
For video specifically prefer `VideoObject` (adds `thumbnailUrl`, `uploadDate`,
`contentUrl`, `transcript`).

## SoftwareApplication / SoftwareSourceCode (a tool/app/library)
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "mcp-apple-notes",
  "description": "mcp-apple-notes is an MCP server that exports Apple Notes to Markdown.",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "macOS",
  "url": "https://github.com/connerkward/mcp-apple-notes",
  "author": { "@type": "Person", "name": "Conner Ward" }
}
```
For a repo/source page, `SoftwareSourceCode` (adds `codeRepository`,
`programmingLanguage`) can be used alongside.

## FAQPage (the TLDR/FAQ — §3)
```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is mcp-apple-notes?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "mcp-apple-notes is an MCP server that exports Apple Notes to Markdown."
      }
    },
    {
      "@type": "Question",
      "name": "Does it send my notes to the cloud?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No — it decodes the local NoteStore protobuf on-device."
      }
    }
  ]
}
```
**The same Q&A must also appear as visible page content** (a `<details>` block is
fine). JSON-LD FAQ without the visible counterpart risks being treated as cloaking.

## BreadcrumbList (site hierarchy)
```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "Home", "item": "https://connerward.com" },
    { "@type": "ListItem", "position": 2, "name": "Projects", "item": "https://connerward.com/projects" },
    { "@type": "ListItem", "position": 3, "name": "mcp-apple-notes", "item": "https://connerward.com/projects/mcp-apple-notes" }
  ]
}
```
Helps engines understand where the page sits in the site structure.
