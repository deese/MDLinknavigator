# MDLinknavigator

A Sublime Text 4 plugin that lets you follow Obsidian-style wikilinks inside
Markdown files.

## Features

- Follow `[[note.md]]` links with a single keystroke.
- Supports paths relative to the current Markdown file: `[[folder/note.md]]`.
- Supports project-root paths: `[[/folder/note.md]]`.
- Supports aliases: `[[folder/note.md|My Note]]`.
- Supports heading anchors: `[[folder/note.md#Section]]`.
- Automatically creates missing Markdown files and folders (configurable).
- Opens images, PDFs, and other non-Markdown files with the default system
  application.

## Usage

Place the cursor inside a wikilink and invoke the command via:

- **Command Palette** (`Ctrl+Shift+P` / `Cmd+Shift+P`): run **MDLinknavigator: Follow Link**
- **Context menu**: right-click inside a wikilink and select **Follow Markdown Link**
- **Ctrl+Click** (Windows/Linux) or **Cmd+Click** (macOS) — enabled by default, see Settings

### Key bindings

The keymap files ship with suggested bindings commented out to avoid conflicts
with other packages. To enable them, open
`Preferences > Package Settings > MDLinknavigator > Key Bindings` and uncomment
the binding for your platform (`Ctrl+Enter` on Windows/Linux, `Cmd+Enter` on macOS).

## Settings

Open `Preferences > Package Settings > MDLinknavigator > Settings`.

```json
{
    "create_missing_files": true,
    "new_file_template": "",
    "follow_on_ctrl_click": true
}
```

- `create_missing_files` – Create a missing Markdown file when following a link.
- `new_file_template` – Text written to newly created Markdown files. Leave empty
  to create blank files.
- `follow_on_ctrl_click` – Follow a wikilink with Ctrl/Cmd+Click.
- `link_resolution` – Strategy for resolving relative wikilinks.
- `fallback_to_unique_name` – Search the whole project for a unique basename match
  when the strict path does not exist.

## Path resolution

Links are resolved from two bases:

- **Root links** (`[[/note.md]]`, `[[/folder/note.md]]`) are always resolved from
  the project root (the opened folder that contains the current file).
- **Relative links** (`[[note.md]]`, `[[folder/note.md]]`) use the
  `link_resolution` setting:
  - `"project_root"` (default): resolved from the project root, like Obsidian.
  - `"relative_to_file"`: resolved from the directory of the Markdown file that
    contains the link.
- **Unique-name fallback**: if a relative link does not exist at the resolved
  path and `fallback_to_unique_name` is `true`, the plugin searches the whole
  project for files with the same basename. If exactly one is found, it opens
  directly; if several are found, a quick panel lets you choose.

## License

MIT
