<a name="readme-top"></a>

<p align="center">
  <img src="readme/assets/banner.svg" alt="SV Cleaner — Explore, compare and clean your WoW SavedVariables" width="1000">
</p>

<h1 align="center">Your data. A clearer interface.</h1>

<p align="center">
  A <strong>SavedVariables</strong> and temporary data manager for <strong>World of Warcraft</strong>.<br>
  Find your addons' data, compare your characters, and prepare your cleanup.<br>
  An <strong>in-game addon</strong> to edit and reload. A <strong>local companion</strong> to clean orphaned data and manage files without launching WoW.
</p>

<p align="center">
  <a href="#installation"><img src="readme/assets/install-button.svg" alt="Install the WoW addon" width="260"></a>
  <a href="#local-companion"><img src="readme/assets/companion-button.svg" alt="Start the local companion" width="260"></a>
</p>

<p align="center">
  <a href="#getting-started"><strong>Get started</strong></a> &nbsp;·&nbsp;
  <a href="#features"><strong>Features</strong></a> &nbsp;·&nbsp;
  <a href="#characters-and-comparison"><strong>Comparison</strong></a> &nbsp;·&nbsp;
  <a href="#compatibility-and-languages"><strong>Compatibility</strong></a> &nbsp;·&nbsp;
  <a href="#commands"><strong>Commands</strong></a>
</p>

---

## Getting started

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>01 &nbsp; Choose your WoW version</h3>
      <p>Download the Windows portable companion, extract the ZIP and run <code>SVCleaner.exe</code>. Choose your WoW client folder when prompted. The companion opens your browser.</p>
      <p>Choose your client in the <strong>WoW version</strong> selector. The inventory and backups belong to that client folder.</p>
    </td>
    <td width="50%" valign="top">
      <h3>02 &nbsp; Find your data</h3>
      <p>Browse files by addon, account, and character. Search for a variable, inspect its contents, and identify files with no matching installed addon.</p>
      <p>In WoW, type <code>/svc</code> to explore the variables of loaded addons.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>03 &nbsp; Prepare your changes</h3>
      <p>Edit a value, compare two characters, or select several files for deletion. Review the <strong>before and after</strong> values.</p>
      <p>The grid aligns <strong>keys, types, values, and status</strong>. Identity fields remain protected.</p>
    </td>
    <td width="50%" valign="top">
      <h3>04 &nbsp; Back up and apply</h3>
      <p>In game, choose <strong>Apply and reload</strong>; results are checked after the reload. Or close all WoW clients and apply in the companion, which backs up original files before writing.</p>
      <p>Use the history to inspect a transaction, measure its changes, or prepare a restore.</p>
    </td>
  </tr>
</table>

> [!NOTE]
> Both interfaces keep the preparation step. In game, review your requests and click **Apply and reload** to change loaded data and verify the results after reloading. Closing the window with pending changes displays a warning. To continue in the companion instead, log out, close WoW, scan, and import the in-game requests.

## Installation

### WoW addon

Install SV Cleaner directly from [CurseForge](https://www.curseforge.com/wow/addons/svcleaner/preview) or [Wago](https://addons.wago.io/addons/svcleaner).

### Local companion

**Windows 10/11 (64-bit): no installation required.** Download
`SVCleaner-Companion-<version>-windows-x64.zip` from
[GitHub Releases](https://github.com/Neogeekmo/SVCleaner/releases), extract the **entire ZIP**
into a writable folder, then double-click **`SVCleaner.exe`**. Python and the browser
interface are included. Keep the `_internal` folder beside the executable.

On first launch, choose the WoW client folder containing `Interface/AddOns`
(for example `_retail_` or `_classic_`). The path is saved in `wow-path.txt`;
delete that file to choose again. You can also specify a folder explicitly:

```powershell
.\SVCleaner.exe --wow "D:\Jeux\World of Warcraft\_retail_"
```

The companion listens on **`127.0.0.1`** and opens your browser. Your data stays on
your PC. Keep its console open; press **Ctrl+C** to stop the server and discard
pending changes that have not been applied. `Lancer-SVCleaner.cmd` also launches
the executable and keeps errors visible if startup fails.

Backups and history are stored in **`data/` beside the executable**. Preserve this
folder when updating; extract the new version into the same folder or copy your
existing `data/` and `wow-path.txt` into the new one.

To try the portable application with isolated sample data:

```powershell
.\SVCleaner.exe --demo
```

**From source (Python 3.10+):** use `Lancer-SVCleaner.cmd` in the source archive or:

```powershell
python companion/app.py --wow "D:\Jeux\World of Warcraft\_retail_"
```

The source version uses Python's standard library and needs no third-party runtime packages.

The companion interface is currently in **French**. The steps below describe its actions in English.

To try the interface with isolated sample data:

```powershell
python companion/app.py --demo
```

---

<p align="center">
  <img src="readme/assets/features.svg" alt="Your data, under control — inventory, editing, comparison and cleanup" width="1000">
</p>

## Features

<table>
  <tr>
    <td width="50%" valign="top">
      <h3>🔎 &nbsp; Inventory and exploration</h3>
      <ul>
        <li><strong>Addon / SavedVariables mapping</strong> from TOC declarations and the manifest.</li>
        <li><strong>Combined filters</strong> for addon, loaded state, and scope in game; accounts, characters, and files in the companion.</li>
        <li><strong>Readable data grid</strong> with key, type, value, and status columns, plus navigation into nested tables.</li>
        <li><strong>Selection details</strong> and searching through keys and values in the open block.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>✏️ &nbsp; Editing and cleanup</h3>
      <ul>
        <li><strong>Editing, deletion and creation</strong> in both interfaces: text, numbers, booleans and empty tables, with typed keys. Existing scalar edits preserve their type.</li>
        <li><strong>Apply and reload in game</strong>, with conflict checks before writing and verification after reloading.</li>
        <li><strong>Bulk deletion</strong> in the companion: select individual files or all filtered results.</li>
        <li><strong>Orphaned files and backup copies</strong> listed separately so you can review what to remove.</li>
        <li><strong>Pending changes and before/after review</strong>, original-file backups, and restore history.</li>
      </ul>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3>👥 &nbsp; Characters and profiles</h3>
      <ul>
        <li><strong>APR character blocks</strong>, including GUID-associated entries in <code>APRData</code>.</li>
        <li><strong>Browsable AceDB structures</strong>: <code>char</code>, <code>profileKeys</code>, and <code>profiles</code>.</li>
        <li><strong>Named comparisons</strong>: check two entries in the addon, then inspect differences in aligned columns.</li>
        <li><strong>Copies to an explicit recipient</strong>, for one value or the compatible values in a block.</li>
      </ul>
    </td>
    <td width="50%" valign="top">
      <h3>📊 &nbsp; Storage and maintenance</h3>
      <ul>
        <li><strong>Actual disk usage</strong> and per-addon charts in the companion.</li>
        <li><strong>Loaded-data estimates</strong> in game, separate from file sizes.</li>
        <li><strong>Change history</strong> and measurements of data removed from active files.</li>
        <li><strong>Cache guidance</strong> in game and backed-up resets of the client's <code>Cache</code> or <code>GPUCache</code> folder while WoW is closed.</li>
      </ul>
    </td>
  </tr>
</table>

Both interfaces offer **light and dark themes**. The addon window can be moved and resized; menus close on outside clicks or **Escape**. The window closes when you enter combat.

### In game and on disk

| Function | In-game addon | Local companion |
|---|---|---|
| Explore variables | Accessible data from loaded addons | Files in the selected WoW client folder |
| Inspect other characters | Character blocks in loaded account-wide variables | Character folders and account-wide variables |
| Create, edit, delete, or copy | Prepare, apply to loaded data and reload; verify results | Prepare, back up and apply file changes without launching WoW |
| Search and edit CVars | Search names, descriptions and values; prepare changes or defaults, apply and reload | CVar requests remain in game |
| Identify orphaned files | — | Match files against installed addons |
| Measure storage | Bounded estimates of loaded data | Actual bytes, charts, and history |
| Maintain caches | Command and settings guidance | Rename a cache folder with restore support |

A **disabled but installed** addon is still installed. A file declared by another addon is marked as **linked / needs review**. Blizzard data and SV Cleaner's own data are protected.

### In-game CVars

Open the **CVars** tab to search the current client's console variables by name, description or current value. Select a row to inspect its current and default values. Enter a new value and choose **Prepare**, or choose **Prepare default value**. Review the request, then use **Apply and reload**, together with any prepared SavedVariables changes. The addon checks for conflicts, reads each CVar back after setting it, and checks it again after reload.

Variables reported as locked, secure or read-only remain visible but cannot be edited. When console enumeration is unavailable, enter an exact CVar name to look it up. Some CVars require a full game restart or are stored on Blizzard's servers; they are applied only in game. The implementation uses the client's [CVar API declarations](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/CVarDocumentation.lua) and [console variable enumeration](https://github.com/Gethe/wow-ui-source/blob/live/Interface/AddOns/Blizzard_APIDocumentationGenerated/ConsoleDocumentation.lua), with legacy API fallbacks.

## Characters and comparison

In the addon, open a variable such as `APRData`, **check two entries**, then click **Compare**. Column headers show character or profile names; each row aligns a key and its two values. Select a difference to inspect it and use **Copy to [character]**.

In the companion, select the addon, account, and two characters or profiles in the comparison view. You can also compare compatible per-character files belonging to the same account.

Copies preserve destination keys and the parent identifier. They operate on existing values of the same type. **GUIDs, IDs, and identity fields**, missing keys, and incompatible types remain visible but cannot be copied through these actions.

**“Not observed” does not mean “deleted character.”** The registry only knows characters encountered since installation, and an old WTF folder may remain. Review these clues before cleaning up.

<details>
  <summary><strong>Data grid and comparison previews</strong></summary>
  <p>These previews use the Lua layout with sample data and a substitute font. They are rendered outside the game.</p>
  <p><img src="readme/assets/grid-preview.png" alt="Key, type and value grid with an editor below the selection" width="1000"></p>
  <p><img src="readme/assets/compare-preview.png" alt="Elowen and Thalion comparison with protected sample identifiers and named copy actions" width="1000"></p>
</details>

---

<p align="center">
  <img src="readme/assets/workflow.svg" alt="Prepare in game, apply on disk — review changes and back up files" width="1000">
</p>

## Backups and applying changes

1. **Prepare** changes in the addon or companion.
2. In game, review the requests and choose **Apply and reload**. The addon checks that the original values still match before applying the entire batch. It keeps requests until their result has been checked after reload; differences remain visible for review. Unloaded addons and requests belonging to another character wait until their data is available.
3. To use the companion instead, **log out and close WoW**, scan, then import in-game requests when needed. Scalar changes, creations and table deletions with a matching snapshot can be imported. Requests already reflected in the data are skipped.
4. **Review the companion basket**, then choose **Back up and apply**. **Open the history** to restore a transaction compatible with the current file contents.

In-game changes do not create the companion's file backups. An addon may recreate a deleted value or change it during shutdown or initialization; verification reports these differences. A normal `/reload` does not apply prepared requests: use **Apply and reload**. Pending requests are saved on logout or reload and can be resumed in the companion. Closing the companion browser tab with a nonempty basket also triggers a warning; stopping its server discards that in-memory basket.

Original files and the journal are stored in `data/<installation>/<transaction>`. The companion checks file contents before writing; a restore refuses to overwrite data that has changed in the meantime.

Data **removed from active files** is different from physical disk space freed: retained backups still occupy storage. Resetting a cache does not guarantee better FPS or latency.

## Compatibility and languages

The shipped TOCs declare the following client families:

| Family | Dedicated TOC |
|---|---|
| Retail | `SVCleaner_Mainline.toc` |
| Classic Era / Hardcore | `SVCleaner_Vanilla.toc` |
| TBC / Anniversary | `SVCleaner_TBC.toc` |
| Wrath / Titan | `SVCleaner_Wrath.toc` |
| Cataclysm | `SVCleaner_Cata.toc` |
| Mists of Pandaria | `SVCleaner_Mists.toc` |
| Forever / Camelot | `SVCleaner_Camelot.toc` |

PTR and beta clients use their corresponding declared interfaces. The companion identifies the client family from the installation metadata; ambiguous clients remain marked as uncertain. Automated checks do not replace testing in each exact game client.

The addon follows WoW's language: **English, French, German, European and Latin American Spanish, Italian, Brazilian Portuguese, Russian, Korean, Simplified Chinese, and Traditional Chinese**. The `enGB` and `ptPT` aliases use the `enUS` and `ptBR` catalogs respectively. The local companion is in **French**.

---

<p align="center">
  <img src="readme/assets/commands.svg" alt="Commands — /svc in WoW and the companion launcher on your PC" width="1000">
</p>

## Commands

| Command | Action |
|---|---|
| `/svc` or `/svcleaner` | Open or close the in-game interface |
| `python companion/app.py --wow "…"` | Open the companion for the specified game client folder |
| `python companion/app.py --demo` | Try the companion with sample data |
| `.\SVCleaner.exe --wow "…"` | Open the Windows portable companion without installing Python |
| `.\SVCleaner.exe --demo` | Try the portable companion with sample data |

## Development, CI and releases

The companion runs with Python 3.10+ and no third-party runtime dependencies.
Install the development dependencies to run the full test suite, including Lua 5.1:

```sh
python -m pip install -r requirements-dev.txt
python tests/check.py
python tools/build.py --check
```

`python tools/build.py --version v0.1.0` regenerates locales, client TOCs and textures,
then creates addon and companion ZIPs in `output/`. Commit generated files together
with their source changes. The addon archive contains only runtime Lua, all eight
TOCs, TGA textures, `LICENSE` and `NOTICE`. The separate companion archive includes
its Python scripts, browser UI, Windows launcher and addon installer; it requires
Python 3.10+ and ships no user data or backups.

To build the **Windows portable ZIP**, use Windows and a 64-bit x86 Python with
Tcl/Tk (CI uses Python 3.12), preferably in a dedicated virtual environment:

```powershell
py -3.12 -m venv .venv-packaging
.\.venv-packaging\Scripts\python.exe -m pip install -r requirements-packaging.txt
.\.venv-packaging\Scripts\python.exe tools/package_companion.py --version v1.0.0
python tools/verify_companion.py output/SVCleaner-Companion-v1.0.0-windows-x64.zip
```

The packager uses [PyInstaller](https://pyinstaller.org/en/stable/) in one-folder mode,
includes the UI, addon runtime and license notices, and writes a ZIP plus a SHA-256
checksum in `output/`. It packages a fresh build only, excluding user settings and
backups. The verifier runs the extracted executable without Python on `PATH`,
checks CLI, demo and HTTP assets, installs the addon into a synthetic WoW folder,
and verifies backup/restore across a restart. Close WoW before running this full
test; `--read-only` checks startup and HTTP assets while a game client is running.

CI builds and tests this portable package on Windows. The tag release workflow
attaches that tested ZIP to GitHub Releases alongside the Python source archive.
Before a release, the ZIP is also available as the `companion-windows-x64` Actions artifact.

## License

Copyright (c) 2026 **Neogeekmo**. SV Cleaner's original code, documentation, and artwork, including the addon and local companion, are distributed under the [MIT License](LICENSE). You may use, modify, and redistribute them, including commercially, provided you retain the copyright and license notice. The software is provided without warranty, subject to applicable law. See the [MIT license text](https://opensource.org/license/mit).

The [project notices](NOTICE) explain third-party rights, Blizzard trademarks, and precautions for SavedVariables cleanup. Blizzard's [UI Add-On Development Policy](https://us.forums.blizzard.com/en/wow/t/ui-add-on-development-policy/24534) applies separately and requires free addon distribution and publicly accessible addon code. SV Cleaner is an independent project and is not endorsed by Blizzard Entertainment.

## Credits

**Neogeekmo** — project author.

---

<p align="center">
  <strong>SV Cleaner</strong><br>
  Readable data. Reviewable changes.<br><br>
  <a href="#readme-top">Back to top ↑</a>
</p>
