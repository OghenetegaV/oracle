# How to use Oracle

Oracle turns an architectural drawing into a structural detail drawing —
columns, beams, reinforcement, and a bar bending schedule — in one guided
walkthrough. No commands, no code.

## What you need before you start

**Always required:**
1. **Python 3.11 or newer**, installed on your computer. If you're not sure, open a
   PowerShell window and type `python --version` — if that shows a version
   number, you're set. Otherwise download it from [python.org](https://www.python.org/downloads/)
   (tick "Add python.exe to PATH" during install).
2. **The Python packages Oracle depends on.** Open PowerShell in the Oracle
   folder and run:
   ```
   pip install -r requirements.txt
   ```
   This is a one-time step (per computer).
3. **A Claude API key**, from [console.anthropic.com](https://console.anthropic.com/).
   Oracle asks for this once, the first time you run it, and remembers it —
   you never type it again or share it with anyone by pasting it into a chat.

**Optional, only if you want these specific features:**

| Feature | What you need |
|---|---|
| Real STAAD.Pro structural analysis (Step 5) | STAAD.Pro V8i SS6 installed and running, plus a 32-bit Python 3.11 install (see "STAAD.Pro setup" below). Without this, Oracle uses a fast built-in estimate instead — the wizard explains the trade-off when you get there. |
| Opening a `.dwg` drawing as input, or getting a `.dwg` (not just `.dxf`) as output | The free [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) |
| Viewing/printing the finished drawing | AutoCAD, or any DWG/DXF viewer |

## First-time setup

1. Install Python (if you don't have it) and run `pip install -r requirements.txt` once.
2. Double-click **`Launch Oracle.bat`**.
3. The first time, a small window asks for your Claude API key — paste it in and click
   "Save and continue". This is saved locally to a file called `.env` in the
   Oracle folder and is never sent anywhere except to Claude when Oracle asks
   it a question on your behalf.

That's it — every time after this, just double-click `Launch Oracle.bat`.

### STAAD.Pro setup (optional, for Step 5's real analysis)

STAAD.Pro V8i SS6's automation interface is 32-bit only, so it needs its own
Python install separate from the one you use for everything else:

1. Download the 32-bit Python 3.11 installer from python.org (the one *without*
   "amd64" in the filename) and install it to `C:\Python311-32`.
2. Open PowerShell **as Administrator** and run:
   ```
   C:\Python311-32\python.exe -m pip install pywin32
   C:\Python311-32\python.exe -c "import pythoncom; t=pythoncom.LoadTypeLib(r'<path to your STAAD install>\OpenSTAAD\openstaad.dll'); pythoncom.RegisterTypeLib(t, r'<path to your STAAD install>\OpenSTAAD\openstaad.dll'); print('Registered OK')"
   ```
   (Replace `<path to your STAAD install>` with wherever STAAD.Pro V8i SS6 is
   installed, e.g. `C:\SProV8i SS6`.)
3. Open STAAD.Pro V8i SS6 and leave it running before you reach Step 5 in Oracle.

If any of this isn't set up, just choose "Use the quick estimate instead" in
Step 5 — the rest of the wizard works exactly the same either way.

## Walking through the wizard

1. **Select drawing** — browse to your architectural DXF or DWG file (with
   walls, columns, and gridlines on layers named `Walls`, `Columns`, `Gridlines`).
2. **Check what we found** — confirms Oracle read your drawing correctly.
3. **A few quick questions** — storey height, how the floor will be used
   (sets the design load), slab thickness, and material choice for columns
   and beams (concrete or steel, and their grades). There's also a free-text
   box for anything else worth telling the engineer — write it like you'd
   tell a colleague.
4. **Structural layout** — Claude proposes columns, beams, and slabs. You'll
   see a sketch of the layout alongside the numbers, plus a "Regenerate"
   button if you want another pass.
5. **Structural analysis** — choose real STAAD.Pro analysis or the quick
   estimate.
6. **Element design** — sizing and reinforcement (or steel sections) for
   every column and beam.
7. **Detail drawing** — Oracle builds the finished drawing (plan, bar marks,
   bar bending schedule) and saves it as a DWG. Click "Open the folder" to
   find it.

## Two things available from any step, not just in the flow

Once a layout exists (after Step 4), two buttons appear in the top-right corner:

- **📝 Layout & Notes** — opens a clickable plan of your layout. Click any
  column, beam, or slab to attach a note to it specifically ("thicken this
  slab", "double-check this column"). Elements with a note show a small
  orange dot. Notes are applied the next time you regenerate the layout or
  the design — add them whenever you think of them, you don't need to be on
  a particular step.
- **💬 Ask Claude** — a persistent chat window. Ask questions about the
  project as it stands (Claude can see what's been generated so far) or type
  instructions directly — anything you say here is also carried forward into
  later layout/design generation, the same way the Step 3 notes box and
  per-element notes are.

## Where things get saved

Everything lands inside the Oracle folder:

- `output_json/` — the layout, forces, and design data, as JSON
- `output_dwg/` — the finished detail drawing (`.dwg`, plus the `.dxf` it was built from)
- `output_lisp/` — an AutoCAD LISP script (`oracle_details.lsp`) that places the
  same bar marks onto a drawing you already have open in AutoCAD, as an
  alternative to the standalone DWG
- `.env` — your saved API key (never share this file with anyone, or check it
  into any shared/version-controlled folder)

## Sharing Oracle with someone else

You can hand someone the whole Oracle folder (zipped, on a shared drive,
however you'd normally share files) and they can use it independently, as
long as they:

1. Have Python 3.11+ installed.
2. Run `pip install -r requirements.txt` once.
3. Have their **own** Claude API key (don't share yours — each person should
   get their own from console.anthropic.com; the wizard asks for it on first
   run).
4. Optionally set up STAAD.Pro per the section above, if they want real
   analysis rather than the quick estimate.

**Before sharing, delete the `.env` file** (or make sure it isn't included) —
that's where your personal API key is stored, and it shouldn't travel with
the folder. Everything in `output_json/`, `output_dwg/`, `output_lisp/`,
`output_staad/`, and `logs/` is just generated project data — safe to leave
out of a shared copy too, since it's specific to whatever you last worked on
and gets rebuilt automatically as they use the wizard.

## If something goes wrong

Every error the wizard shows is meant to explain what actually happened, not
just "something broke." If you hit one that doesn't make sense, or the
wizard looks visually broken, that's worth reporting back — screenshot the
error dialog (there's usually a "technical details" section you can expand)
rather than just describing it from memory.
