---
name: apple-notes-export
description: Export Apple Notes from NoteStore.sqlite via protobuf decoding. Use when user wants to export, back up, or extract Apple Notes data.
author: Conner K Ward
version: 9b18650
last_updated: 2026-06-26 21:56:30 -0700
trigger: always_on
---

# Apple Notes Export

Export notes directly from the Apple Notes SQLite database by decoding protobuf blobs. Zero dependencies (stdlib only), ~2s for ~1800 notes.

## Tool

**Repository:** `~/dev/notesutils` (clone of [dunhamsteve/notesutils](https://github.com/dunhamsteve/notesutils))

If `~/dev/notesutils` is missing: `git clone https://github.com/dunhamsteve/notesutils ~/dev/notesutils`.

**Database location:** `~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite`

## Scripts

| Script | Output | Notes |
|--------|--------|-------|
| `notes2html` | HTML per note + media | Full fidelity: tables, drawings, images, links |
| `notes2bear` | `.bearbk` zip | Bear backup format, no tables |
| `notes2quiver` | Quiver notebook | Quiver app format |

## Usage

```bash
# HTML export (recommended)
python3 ~/dev/notesutils/notes2html --title <dest_dir>

# With inline SVG drawings
python3 ~/dev/notesutils/notes2html --svg --title <dest_dir>
```

Flags:
- `--title` — name files by note title instead of UUID
- `--svg` — render drawings as inline SVG instead of fallback JPG

## How It Works

1. Opens `NoteStore.sqlite` directly (read-only copy made to dest)
2. Queries `ziccloudsyncingobject` for attachments (drawings, tables, images, URLs)
3. Queries `zicnotedata` for note bodies
4. Each note body: `ZDATA` → zlib decompress → protobuf decode → HTML render
5. Encrypted notes (`zcryptotag is not null`) are skipped

## Performance

~1,800 notes in ~2 seconds, 44MB output (HTML + media).

## Integration with exp-notes-indexing (optional)

`~/dev/exp-notes-indexing` is an OPTIONAL downstream local project and may not be present on every machine — don't assume it exists. If it is present, this skill's HTML output can replace the markdown export it previously consumed. To convert HTML to plain text for Graphiti ingestion, strip tags or use the protobuf text directly from the parsed `s_doc` schema.
