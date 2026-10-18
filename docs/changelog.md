# Unreleased

- Maintain addon translations directly in one Lua file per language under `addon/locales/`; remove the JSON translation sources and locale generator. Use WoW's `GetLocale()` directly, with English fallback and no additional locale aliases.
- Replace the light/dark text button with a compact theme icon and a localized tooltip.
- Use a single multi-client `SVCleaner.toc`. Local archives, installation and synchronization share the same runtime content, which is also checked in BigWigs archives. Synchronization backs up and removes obsolete client TOCs.
- Filter comparison results without recalculating on each keystroke; recompute when the selection changes or data is refreshed.
- Estimate large SavedVariables in batches of 512 traversal steps, cancel previous scans and handle data changes during traversal.
- Add versioned saved-data migrations that preserve pending requests and history; leave unsupported formats untouched.
- Split the Lua core into data, discovery, migration, CVar, request and minimap modules.
- Separate sources: the WoW addon lives in `addon/`, the companion in `companion/`, documentation artwork in `docs/assets/` and the logo source in `artwork/`. Remove the CMD launcher and the old separate Python source archive.
- Translate the companion into all eleven WoW languages, with browser language detection, a persistent language selector, localized server errors and dialogs, and preservation of user settings and data.
- Restore the companion's Characters screen, including search and access to local files.
- Provide a portable Windows 64-bit companion with an embedded Python runtime, a WoW folder picker on first launch, persistent backups and ZIP distribution through GitHub Releases.
- Apply prepared changes in game, reload the interface and verify the results after reloading.
- Warn when closing with pending requests and preserve them for continuation in the companion.
- Support creating typed keys, values and empty tables in both interfaces.
- Import table deletions with snapshots and detect requests that have already been applied.
- Translate the new workflow across all eleven language catalogs.
- Add a CVars tab with search by name, description and value; prepare edits or restore defaults, then apply and verify after reloading. Support both modern and legacy APIs.

# SVCleaner 0.1.0

SavedVariables management, character data comparison and preparation of offline changes.
Light and dark themes with a transparent SV logo.
Separate distribution of the addon and local companion, with a TOC for each client family.

Grid-based data navigation showing keys, types, values and status, with an editor below the selection.
Comparison of two selected entries, named columns and copying to an explicit destination.
Compact controls, font-independent TGA icons and menus that close when clicking outside or pressing Escape.
