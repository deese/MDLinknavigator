"""MDLinknavigator - Follow Obsidian-style wikilinks inside Markdown files."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Optional, Tuple

import sublime
import sublime_plugin

SETTINGS_FILE = "MDLinknavigator.sublime-settings"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _load_settings() -> sublime.Settings:
    """Return the plugin settings object."""
    return sublime.load_settings(SETTINGS_FILE)


def _resolve_project_root(
    window: sublime.Window, current_file: Optional[str]
) -> Optional[str]:
    """Return the project folder that contains current_file, or None."""
    if not current_file:
        return None

    for folder in window.folders():
        prefix = folder + os.sep
        if current_file.startswith(prefix):
            return folder

    return None


def _resolve_link_path(
    window: sublime.Window, current_file: Optional[str], rel_path: str
) -> Optional[str]:
    """Resolve a wikilink path based on the configured strategy.

    - Paths starting with ``/`` are always resolved from the project root.
    - Other paths use the ``link_resolution`` setting:
      - ``project_root`` (default): resolved from the project root, like Obsidian.
      - ``relative_to_file``: resolved from the directory of the current file.
    """
    if not current_file:
        return None

    root = _resolve_project_root(window, current_file)

    if rel_path.startswith("/"):
        if not root:
            return None
        base = root
        rel_path = rel_path[1:]
    else:
        resolution = _load_settings().get("link_resolution", "project_root")
        if resolution == "relative_to_file":
            base = os.path.dirname(current_file)
        else:
            base = root if root else os.path.dirname(current_file)

    return os.path.normpath(os.path.join(base, rel_path))


def _parse_link(raw: str) -> Tuple[str, Optional[str]]:
    """Parse a wikilink into (path, anchor). Alias is ignored."""
    target = raw.split("|", 1)[0]

    if "#" in target:
        path, anchor = target.split("#", 1)
    else:
        path, anchor = target, None

    return path.strip(), (anchor.strip() if anchor else None)


def _normalize_path(path: str) -> str:
    """Append .md when no extension is provided, matching Obsidian behavior."""
    if not os.path.splitext(path)[1]:
        path += ".md"
    return path


def _hidden_startupinfo() -> Optional[subprocess.STARTUPINFO]:
    """Return STARTUPINFO that suppresses console window flashing on Windows."""
    if sys.platform != "win32":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return startupinfo


def _open_with_system(path: str) -> None:
    """Open a non-Markdown file with the default system application."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False, startupinfo=_hidden_startupinfo())
    else:
        subprocess.run(
            ["xdg-open", path], check=False, startupinfo=_hidden_startupinfo()
        )


def _find_unique_matches(root: str, basename: str) -> list:
    """Return all file paths under root matching basename, skipping hidden dirs."""
    matches = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if basename in filenames:
            matches.append(os.path.join(dirpath, basename))
    return matches


class MdlinknavigatorFollowCommand(sublime_plugin.TextCommand):
    """Follow the Obsidian wikilink under the cursor."""

    def run(self, edit: Optional[sublime.Edit] = None) -> None:
        view = self.view
        file_name = view.file_name()

        if not file_name or not file_name.lower().endswith(".md"):
            sublime.status_message("MDLinknavigator: not a Markdown file")
            return

        link_region = None
        for sel in view.sel():
            link_region = self._find_link_at(sel.begin())
            if link_region:
                break

        if not link_region:
            sublime.status_message("MDLinknavigator: no wikilink under cursor")
            return

        raw = view.substr(link_region)[2:-2]
        rel_path, anchor = _parse_link(raw)
        if not rel_path:
            sublime.status_message("MDLinknavigator: empty link")
            return

        rel_path = _normalize_path(rel_path)
        full_path = _resolve_link_path(view.window(), file_name, rel_path)
        if not full_path:
            sublime.status_message("MDLinknavigator: cannot resolve link path")
            return

        if full_path.lower().endswith(".md"):
            self._handle_markdown(full_path, rel_path, anchor)
        else:
            self._handle_non_markdown(full_path, rel_path)

    def _find_link_at(self, cursor: int) -> Optional[sublime.Region]:
        """Return the wikilink region at or nearest to the cursor."""
        all_links = self.view.find_all(WIKILINK_RE.pattern)

        for region in all_links:
            if region.contains(cursor):
                return region

        # Fallback: nearest link on the same line helps when the caret is close
        # to a link but not exactly inside it.
        line = self.view.line(cursor)
        candidates = [r for r in all_links if line.intersects(r)]
        if candidates:
            return min(
                candidates,
                key=lambda r: min(abs(r.begin() - cursor), abs(r.end() - cursor)),
            )

        return None

    def _handle_markdown(
        self, full_path: str, rel_path: str, anchor: Optional[str]
    ) -> None:
        """Open an existing Markdown file, resolve a unique name, or create it."""
        settings = _load_settings()

        if os.path.exists(full_path):
            self._open_markdown(full_path, anchor)
            return

        if settings.get("fallback_to_unique_name", True):
            root = _resolve_project_root(self.view.window(), self.view.file_name())
            if root:
                basename = os.path.basename(full_path)
                matches = _find_unique_matches(root, basename)
                if len(matches) == 1:
                    self._open_markdown(matches[0], anchor)
                    return
                if len(matches) > 1:
                    self._show_path_choices(matches, anchor)
                    return

        if not settings.get("create_missing_files", True):
            sublime.status_message(f"MDLinknavigator: file not found {rel_path}")
            return

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            template = settings.get("new_file_template", "")
            with open(full_path, "w", encoding="utf-8") as file:
                if template:
                    file.write(template)
        except OSError as exc:
            sublime.status_message(f"MDLinknavigator: could not create file: {exc}")
            return

        self._open_markdown(full_path, anchor)

    def _open_markdown(self, full_path: str, anchor: Optional[str]) -> None:
        """Open a Markdown file and optionally jump to an anchor."""
        new_view = self.view.window().open_file(full_path)
        if anchor:
            sublime.set_timeout(lambda: self._goto_anchor(new_view, anchor), 300)

    def _show_path_choices(self, matches: list, anchor: Optional[str]) -> None:
        """Show a quick panel when multiple files share the same basename."""
        window = self.view.window()
        root = _resolve_project_root(window, self.view.file_name())

        items = [os.path.relpath(m, root) if root else m for m in matches]

        def on_select(index: int) -> None:
            if index == -1:
                return
            sublime.set_timeout(
                lambda: self._open_markdown(matches[index], anchor), 10
            )

        window.show_quick_panel(items, on_select)

    def _handle_non_markdown(self, full_path: str, rel_path: str) -> None:
        """Open non-Markdown files with the system default application."""
        if not os.path.exists(full_path):
            sublime.status_message(f"MDLinknavigator: file not found {rel_path}")
            return

        try:
            _open_with_system(full_path)
        except OSError as exc:
            sublime.status_message(f"MDLinknavigator: could not open file: {exc}")

    def _goto_anchor(self, view: sublime.View, anchor: str) -> None:
        """Move the cursor to the first heading matching the anchor."""
        if not view:
            return

        content = view.substr(sublime.Region(0, view.size()))
        pattern = re.compile(r"^#{1,6}\s*" + re.escape(anchor) + r"(?:\s|$)", re.I)
        for line_number, line in enumerate(content.splitlines()):
            if pattern.match(line):
                point = view.text_point(line_number, 0)
                view.sel().clear()
                view.sel().add(sublime.Region(point))
                view.show(point)
                return

        sublime.status_message(f"MDLinknavigator: anchor #{anchor} not found")


class MdlinknavigatorClickListener(sublime_plugin.EventListener):
    """Intercept Ctrl/Cmd+Click on wikilinks and follow them."""

    def on_text_command(
        self, view: sublime.View, command_name: str, args: Optional[dict]
    ) -> Optional[tuple]:
        if command_name != "drag_select":
            return None

        settings = _load_settings()
        if not settings.get("follow_on_ctrl_click", True):
            return None

        if not args or not args.get("additive"):
            return None

        event = args.get("event")
        if not event:
            return None

        point = view.window_to_text([event["x"], event["y"]])
        if point < 0:
            return None

        file_name = view.file_name()
        if not file_name or not file_name.lower().endswith(".md"):
            return None

        for region in view.find_all(WIKILINK_RE.pattern):
            if region.contains(point):
                return ("mdlinknavigator_follow", None)

        return None
