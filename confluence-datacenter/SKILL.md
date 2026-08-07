---
name: confluence-datacenter
description: This skill should be used when the user asks to "get Confluence page", "create Confluence page", "search Confluence", "update wiki page", or needs to interact with Confluence Data Center/Server instances.
version: 0.1.0
---

# Confluence Data Center

Interact with Confluence Data Center/Server instances via REST API.

## Features

| Command     | Description                      |
| ----------- | -------------------------------- |
| get         | Get page content by ID or title  |
| search      | Search content using CQL         |
| create      | Create a new page                |
| update      | Update page content              |
| delete      | Delete a page                    |
| children    | List child pages                 |
| spaces      | List available spaces            |
| attachments | List or upload attachments       |
| export      | Export page to different formats |

## Prerequisites

Environment variables (can be in `.env` file):

- `CONFLUENCE_BASE_URL` - Your Confluence instance URL (e.g., `https://confluence.company.com`)
- `CONFLUENCE_PAT` - Personal Access Token (preferred)

OR for basic auth:

- `CONFLUENCE_BASE_URL` - Your Confluence instance URL
- `CONFLUENCE_USERNAME` - Your username
- `CONFLUENCE_PASSWORD` - Your password

### Creating a Personal Access Token

1. Go to your Confluence profile (click avatar → Settings)
2. Navigate to Personal Access Tokens
3. Click "Create token"
4. Give it a name and set expiry
5. Copy the token to `CONFLUENCE_PAT`

## Usage

Run from this skill's directory (or replace `scripts/` with the absolute path to it).

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py COMMAND [OPTIONS]
```

## Commands

### Get Page

```bash
# By page ID
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py get 12345

# By title and space
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py get --space DEV --title "Getting Started"
```

Options:

- `--format html|storage|markdown` - Output format (default: markdown)
- `--json` - Output full JSON response

### Search Content (CQL)

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py search "space = DEV AND title ~ 'API'"
```

Options:

- `--max N` - Maximum results (default: 25)
- `--type page|blogpost|comment` - Content type filter
- `--json` - Output as JSON

### Create Page

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py create \
  --space DEV \
  --title "New Page Title" \
  --body "Page content in **markdown** or HTML"
```

Options:

- `--space KEY` - Space key (required)
- `--title TEXT` - Page title (required)
- `--body TEXT` - Page content (required)
- `--body-file PATH` - Read body from file instead
- `--parent ID` - Parent page ID
- `--format markdown|html|storage` - Body format (default: markdown)

### Update Page

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py update 12345 \
  --body "Updated content"
```

Options:

- `--title TEXT` - New title
- `--body TEXT` - New content
- `--body-file PATH` - Read body from file
- `--format markdown|html|storage` - Body format
- `--minor` - Mark as minor edit

### Delete Page

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py delete 12345
```

Options:

- `--force` - Skip confirmation

### List Child Pages

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py children 12345
```

### List Spaces

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py spaces
```

Options:

- `--type global|personal` - Filter by space type

### Attachments

```bash
# List attachments
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py attachments 12345

# Upload attachment
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py attachments 12345 \
  --upload /path/to/file.pdf
```

### Export Page

```bash
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py export 12345 \
  --format pdf \
  --output ./exported-page.pdf
```

Options:

- `--format pdf|word|markdown` - Export format
- `--output PATH` - Output file path

## Examples

```bash
# Get a page as markdown
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py get 12345

# Search for pages about API in DEV space
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py search \
  "space = DEV AND type = page AND text ~ 'API documentation'"

# Create page from markdown file
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py create \
  --space DEV \
  --title "API Reference" \
  --body-file ./api-docs.md \
  --format markdown

# Create child page
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py create \
  --space DEV \
  --title "Sub Page" \
  --body "Content here" \
  --parent 12345

# Update page with file content
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py update 12345 \
  --body-file ./updated-docs.md \
  --format markdown

# Export page to PDF
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py export 12345 \
  --format pdf \
  --output ./docs.pdf

# Upload diagram to page
uvx --with requests --with python-dotenv --with typer --with rich --with markitdown \
  python scripts/confluence.py attachments 12345 \
  --upload ./architecture.png
```

## Content Formats

### Markdown (recommended)

Write content in standard Markdown. The skill converts to Confluence storage format.

### HTML

Standard HTML that Confluence will render.

### Storage Format

Confluence's native XHTML-based storage format with macros:

```xml
<p>Text with <ac:link><ri:page ri:content-title="Other Page"/></ac:link></p>
```

## Visual design & dark-mode-safe styling

Rich "wow" pages (hero banners, cards, callouts) must look good in **both** light
and dark mode. The single most important rule:

> **Never hardcode a light background (`bgColor`) on a `panel` macro.**

Confluence dark mode only recolors its **own native theme tokens** — it does *not*
touch custom hex colors. So:

- A `panel` with `<ac:parameter ac:name="bgColor">#DEEBFF</ac:parameter>` stays a
  **bright light box** on a dark page in dark mode (jarring "floating islands").
- Worse, dark mode then remaps your text color toward light-gray to "fit" what it
  assumes is a dark surface — so text on your light panel becomes **washed-out and
  low-contrast**.
- Trying to force dark text does **not** reliably fix it:
  - `style="color:..."` on block elements (`<p>`, `<h3>`) is **stripped** by the
    sanitizer.
  - `<span style="color: rgb(23,43,77);">…</span>` *survives* the sanitizer, but
    dark mode still remaps it on a custom light background. Dead end.

### The fix: border-accent panels (theme-adaptive)

Drop `bgColor` entirely and give the panel only a colored **border**. The panel
background then follows the theme (dark in dark mode, white in light mode), and the
text uses the theme's default color — always high-contrast. The color identity comes
from the **border + an emoji + a `status` lozenge**, all of which render correctly in
both themes.

```xml
<ac:structured-macro ac:name="panel">
  <ac:parameter ac:name="borderColor">#0052CC</ac:parameter>
  <ac:parameter ac:name="borderStyle">solid</ac:parameter>
  <ac:parameter ac:name="borderWidth">2</ac:parameter>
  <ac:rich-text-body>
    <h3 style="margin-top:0;">🧠 Card Title &nbsp;
      <ac:structured-macro ac:name="status">
        <ac:parameter ac:name="colour">Blue</ac:parameter>
        <ac:parameter ac:name="title">MODELS</ac:parameter>
      </ac:structured-macro>
    </h3>
    <p>Body text — inherits the theme color, so it stays readable in dark mode.</p>
  </ac:rich-text-body>
</ac:structured-macro>
```

### Other theme-safe building blocks

- **Native semantic panels** are fully theme-aware — use them for callouts instead of
  colored `panel`s: `info`, `note`, `tip`, `warning`, `success`.
- **`status` lozenge** (badges): `colour` must be one of `Grey | Red | Yellow | Green | Blue`
  (no Purple/Orange — they silently fall back to grey).
- **`code` macro** for code blocks (theme-aware, syntax-highlighted) — prefer over
  `<pre>`: `<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">bash</ac:parameter><ac:plain-text-body><![CDATA[...]]></ac:plain-text-body></ac:structured-macro>`
- **`toc` macro** for an "On this page" index; **`children`** macro for an auto index of sub-pages.
- **Multi-column layouts**: wrap the *whole* body in one `<ac:layout>` containing
  `<ac:layout-section ac:type="...">` → `<ac:layout-cell>`. Valid types: `single`,
  `two_equal`, `two_left_sidebar`, `two_right_sidebar`, `three_equal`,
  `three_with_sidebars`. **There is no `four_equal`** — use two `two_equal` rows for a 2×2 grid.

### Gotchas

- **Page titles must be unique per space.** `create` fails if a page with the same
  title exists anywhere in the space (even under a different parent). Pick a distinct title.
- **Re-parenting** (moving a page) isn't exposed by the CLI; do it via REST `PUT
  content/{id}` with `ancestors: [{id: newParent}]` and the incremented `version` —
  omit `body` to preserve content.
- **Always back up before overwriting**: `get <id> --format storage --json > backup.json`.
  The CLI's markdown export flattens macros (you'll see raw params like `#0052CC` or
  `true`), so judge rendered pages in the browser, not the CLI dump.

## Output

- Default output is human-readable formatted text
- Page content defaults to Markdown format
- Use `--json` flag for machine-readable JSON output
- URLs are included for easy navigation

## API Version

This skill uses Confluence REST API (`/rest/api/`), compatible with:

- Confluence Data Center 6.x and later
- Confluence Server 6.x and later
