JARVIS V4.3 CLASSIC APP — RELIABILITY + LOCAL TOOLS
=========================

WHAT THIS VERSION IS
--------------------
This build deliberately restores the classic JARVIS interface:
- the old INITIALIZE SYSTEM startup screen and initialization sequence
- the old dark teal/black HUD, radar/core and panels
- the old compact rectangular Settings overlay (760 x 650 maximum)
- the existing lower-right controls and classic layout

The code underneath the interface is updated, but the interface was not
redesigned into the V3/V3.1 full-page layout.

V4.3 RELIABILITY UPDATE
-----------------------
- TOOLS is a new top-level workspace with 43 allowlisted utilities across
  Quick, Text, Encode, Generate, Files, System, and Create categories.
- Every local tool works without an account, third-party API key, or sign-up.
  Tools never turn a prompt into an arbitrary PowerShell/shell command.
- Built-in research now starts with documented public APIs/feeds instead of
  scraping search-result pages. Eight independent providers are attempted in
  parallel; one provider failing or rate-limiting does not cancel the others.
- JARVIS never tries to solve or bypass CAPTCHA/verification challenges. It
  switches to readable API sources and reports a clear failure only when all
  sources are unavailable.
- Account bearer tokens are saved in app local storage, and server sessions
  use a rolling long-life expiration. Ctrl+R and normal app restarts no longer
  force a login; LOG OUT still removes the saved token immediately.
- In the installed app, the account database, WebView2 profile, settings,
  research cache, memory, and tool outputs live in `%LOCALAPPDATA%\JARVIS`.
  They are not stored in the temporary one-file EXE extraction directory, so
  an MSI update or executable restart does not erase them.
- Settings uses one bounded native scroll viewport. Wheel/touch stays native;
  a passive WebView2 fallback only activates if two animation frames pass with
  no movement, then it uses the same card focus/reveal behavior as the Tab key.

SEARCH ENGINES + MANUAL UPDATE
------------------------------
- Research now includes DuckDuckGo's Instant Answer API (always on, no key) and
  the official Brave Search API (optional free key from brave.com/search/api).
  Paste the key in Settings > Browsing > Research Search Engines, press SAVE
  KEY, then TEST SEARCH. The key is stored only in this PC's JARVIS config.
- These are search APIs built for programs, so JARVIS is not treated as a bot.
  If a browser-tab results page is empty or shows a verification screen, JARVIS
  skips it and opens a link supplied by the search APIs instead.
- Settings > Manual is a new built-in user guide (modes, research, Ollama setup,
  API keys, GitHub updates, troubleshooting).
- Works the same with Claude/Gemini API keys or a local Ollama model.

LOCAL MODEL QUICK SETUP (8 GB GPU such as an RTX 2080 Super)
------------------------------------------------------------
1. Install Ollama from https://ollama.com/download
2. In Windows Terminal:  ollama pull gemma3:12b     (or gemma3:4b for speed)
3. In JARVIS: Settings > AI > Local, type the same model name, press Save.

GUARDED EVOLUTION
-----------------
- Settings > Evolution lets JARVIS learn external behavior skills immediately.
  Those skills live under the user's JARVIS data folder and survive app updates.
- Repeated local failures can quietly create a JARVIS-origin improvement idea;
  this does not interrupt you with a warning and does not silently edit code.
- A direct "change your code" request shows a warning before the request is
  queued, exactly because that request came from the user.
- Real source edits use an extracted source workspace, an exact find/replace,
  a unified diff, a unique approval phrase, a complete backup, syntax checks,
  the regression suite, and automatic rollback when validation fails.
- The installed one-file JARVIS.exe is never rewritten in place. Applied source
  patches become active after the GitHub workflow builds the next MSI.

INTERFACE SOUND FX + MOTION
---------------------------
- Buttons, tabs, settings cards, mode switches, browser controls, Chat, Brain
  and LAB now share one subtle JARVIS sound system and one motion language.
- Settings > Voice has SOUND FX ON/OFF, TEST FX and a master volume slider.
  The preference is saved locally and is included in account profile sync.
- Chat send/receive, Brain learn/node events, LAB model events, confirmations,
  errors, opening/closing panels and mode changes use distinct short cues.
- Panels/cards ease in, clickable controls respond visually, workspaces fade
  in, and active HUD controls retain the classic restrained glow treatment.
- Windows/browser reduced-motion preference is respected for the added motion.

BRAIN / LEARN MODE
------------------
- BRAIN is a new top-level mode beside J.A.R.V.I.S. and CHAT. It keeps the
  classic interface and adds a rotatable, zoomable 3D knowledge-brain view.
- Click a knowledge node to see what JARVIS knows and its provenance. Built-in
  knowledge is labeled FACTORY and intentionally has no made-up learned date.
- Press LEARN MODE to open its animated timer drawer, then choose 1-120
  minutes. You can also say "Jarvis learn for 5 minutes" while using BRAIN.
  JARVIS uses at most 10 research tabs at once; leaving BRAIN stops the session
  and closes the research tabs it opened.
- Settings > Browsing controls presentation, not whether learning works.
  Documented public APIs/feeds are always the primary research path. Internal
  keeps the activity inside JARVIS; External optionally mirrors the current
  topic in paired Edge/Chrome, but extension pairing is no longer required for
  Brain to research and learn.
- Research nodes store short paraphrased facts and source metadata, not full
  web-page text. Reddit/community sources are clearly marked as community
  context rather than universal fact.
- Newly learned nodes glow, the map grows as new knowledge is added, and the
  bottom-left summary button condenses the latest session into 1-3 sentences.
- Learned Brain knowledge is included in account profile sync when signed in.
- External Learn Mode can still use the /extension/research bridge as an
  optional visible mirror. Closing the extension popup does not stop core
  public-source research.
- The visible countdown does NOT begin merely because the extension says it is
  connected. It begins after the first readable public or browser source is
  processed; if every provider fails, Learn Mode shows FAILED instead of
  consuming the requested learning time.
- Brain now prefers topics whose knowledge labels and searches are not already
  in its knowledge graph/session. It moves to new subjects before revisiting
  anything it already knows and finishes if no unseen topic remains.
- Browser pairing is persisted by the extension and owned by its background
  worker, not the popup. The worker re-registers itself when Chrome/Edge wakes
  it and keeps a 30-second backup heartbeat, so closing the popup does not
  unpair JARVIS. A protected browser page may block "Read this page" without
  changing the pairing state.
- If a normal research page presents a CAPTCHA/human-verification interstitial,
  JARVIS does not try to defeat it. It marks that source blocked and switches
  to a readable public source/API. The countdown starts only after at least one
  source was actually read; if every source fails, the Brain clearly says FAILED.

LAB / 3D MODELS
---------------
- LAB is a top-level mode beside J.A.R.V.I.S., CHAT and BRAIN.
- You can now say things like "Jarvis, design me a 70 mm door stop" or type a
  design request in LAB. JARVIS turns supported benign requests into printable
  combinations of simple solid geometry, and there is an offline shape fallback
  if the AI planner is unavailable.
- Import STL or OBJ, orbit/zoom the preview, then change scale, X/Y/Z rotation
  and X/Y/Z position. Those transforms are baked into the STL handoff.
- The printer plate is part of the same 3D scene as the model, so orbiting the
  camera moves the model and plate together. Half/double scale preserves the
  model's XY center and its position on the bed instead of making it jump.
- Create Cube, Sphere, Cylinder, Cone, Torus, Wedge, and Ring models directly.
- Editing/tools include Undo, Redo, Duplicate, Clear, Mirror X/Y/Z, Center XY,
  Place on Bed, selected-printer auto-fit, X/Y/Z +90-degree rotations,
  half/double scale and transform reset.
- Inspection/tools include isometric/top/front/right views, grid toggle,
  wireframe toggle, STL export, PNG snapshot, copyable model stats, and an
  A1 Mini fit check.
- LAB shows approximate dimensions, triangle count, volume, surface area,
  filament grams, print time, material cost and selected-printer fit. Printer
  profiles cover the current A/P/X/H families in this build; changing printers
  changes the virtual build plate and XYZ fit limits. PLA/PETG/ABS/ASA/TPU use
  built-in density and reference store pricing instead of an editable $/kg box.
- LAB panels start larger for readability and can be resized by dragging their
  inner resize rails. The left creator panel can grow to 720 px wide.
- Slice-style controls now include quality presets, first-layer height, line
  width, nozzle, wall generator/loops, top/bottom layers and patterns, infill,
  support style/threshold, brim width, skirt loops, seam, ironing, elephant-foot
  compensation, plate, sequence, timelapse and five speed controls.
- Factory printer profiles include A, P, X and H-series variants, including
  X2D and H2C/H2D/H2D Pro nozzle-specific envelopes. The selected profile
  updates the plate, XYZ limits, fit check, auto-fit target and profile card.
- Prompt-generated geometry is capped to a practical default envelope when the
  prompt gives no dimensions, and common designs such as boats use dedicated
  semantic geometry instead of falling back to a random single cylinder.
- More than 35 LAB functions are wired to real controls or JARVIS commands;
  prompt design and many common edit/view/print tools can be voice-controlled.
  Example commands: "add a sphere", "mirror X", "fit this to A1 Mini",
  "top view", "export STL", "set infill to 20", and "print review".
- LAB shows approximate pre-slice dimensions, filament grams and print time.
  Bambu Studio is still the exact source of truth after it slices the model.
- PRINT opens a review first. JARVIS shows model validation, STL handoff,
  Bambu Studio launch/staging and final-review states. PREPARE IN BACKGROUND
  asks Windows to minimize Studio while it stages the STL; an already-running
  Studio instance may choose to foreground itself. Exact sliced time/grams and
  the final physical-print confirmation stay in Bambu Studio.
- BRAIN and LAB include subtle UI motion and short interface sound cues.

IMPORTANT SAFETY/STARTUP CHANGE
-------------------------------
The JARVIS app does NOT add itself to Windows Startup and does NOT replace
Windows Explorer or the Windows shell. The startup restored here is the
on-screen JARVIS initialization sequence only.

ADMINISTRATOR MODE + CAMERA
---------------------------
- The GitHub-built JARVIS.exe now requests Windows administrator elevation each
  time it starts. Windows shows a UAC dialog and you can approve or reject it.
- This elevation can make desktop automation more reliable, but it deliberately
  does not disable Windows security/privacy controls or web verification.
- Camera access is a separate Windows privacy permission. Settings > Camera has
  a WINDOWS CAMERA PRIVACY button that opens the exact Windows permission page;
  allow camera access there, then press Restart camera inside JARVIS.

WHAT "APP" MEANS IN THIS VERSION
--------------------------------
JARVIS now runs in its own native Windows window using Edge WebView2. It does
not open the main interface as an Edge browser tab/window. GitHub then wraps
that app in a real Windows Installer (.msi), which installs JARVIS under
Program Files and creates a Start-menu entry plus an Installed Apps/uninstall
  entry. The installer has its normal UAC prompt, and this V4.3 app also asks
for elevation each time J.A.R.V.I.S. itself is launched.

BUILD AND INSTALL IT — NO VISUAL STUDIO OR LOCAL PYTHON
-------------------------------------------------------
1. Make a NEW empty GitHub repository.
2. Upload EVERYTHING inside this folder. Keep the folders exactly as provided,
   including .github/workflows, browser_extension, installer, and tests.
3. Commit all of it to the main branch.
4. Open the Actions tab.
5. Open "Build JARVIS V4.3 Installed Windows App".
6. Click "Run workflow", choose main, then click the green Run workflow button.
7. Wait for the build to turn green.
8. Open the finished run and download JARVIS_V4_3_CLASSIC_APP.msi.
9. Double-click the MSI and install it.
10. Open J.A.R.V.I.S. from the Windows Start menu like a normal installed app.

The PC that RUNS the installed app does not need Visual Studio or Python.
Ollama is only required on the host PC providing the local model. Other people
can use the AI-only sharing link/code without installing Ollama on their PC.

Windows 11 already includes the Evergreen WebView2 Runtime. Most Windows 10
systems also already have it. If an older Windows 10 PC reports that WebView2
is missing, install Microsoft's Evergreen WebView2 Runtime once.

SETTINGS / WORKSPACE LAYOUT FIX
-------------------------------
Settings always keeps the compact 760 x 650 rectangle. Colors and Fonts do NOT
widen it. Only those two pages show a separate up/down arrow rail 12 px outside
the Settings rectangle; leaving those pages hides the rail. Those pages use
the same native overflow viewport as every other Settings page. A passive
window-level observer never cancels wheel input; if WebView2 leaves scrollTop
unchanged for two frames, it directly moves the viewport and then falls back
to the same card focus/reveal behavior that works with Tab. The arrow rail and
PageUp/PageDown/Arrow/Home/End keys remain independent scroll paths.
Whole color/font cards are clickable and hover never applies a selection.

Chat uses the Settings button already built into its sidebar, so the duplicate
floating HUD gear is hidden while Chat is open. The JARVIS sidebar/banner now
starts at the very top of the window. LAB's model/print panels are moved below
the floating Settings gear so the gear is not covered.

ACCOUNT + OPTIONAL AZURE VOICE
------------------------------
- Settings now has an Account page, so login/create-account/sync/logout can be
  done without switching to Chat.
- Login is merge-first: existing local chats, memory and saved appearance/
  browsing choices are merged before the combined copy is synced.
- Personal learned information asks for account login only when signed out.
- The account service is hosted by the owner's JARVIS server on port 5005.
  Passwords are PBKDF2 hashed and sessions use random bearer tokens.
- Settings > Voice has an Azure section at the bottom. Azure is optional.
  Without it JARVIS keeps the built-in system voice.
- Azure keys are never saved in HTML, localStorage, GitHub source, or profile
  JSON. They are encrypted by Windows DPAPI in the JARVIS account database and
  the client can only see whether Azure voice is configured.
- Default Azure voice: en-US-RyanMultilingualNeural with British-English SSML.
  Andrew Multilingual and Brian Multilingual are selectable alternatives.
- If Azure synthesis fails, JARVIS automatically uses its built-in voice.

FILES / SETTINGS
----------------
The installed app contains the UI and support files. User-changing settings are stored in
the user's Windows profile so they survive app updates. The factory config in
this source package contains no personal API keys or passwords.
