from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "jarvis_v2.html").read_text(encoding="utf-8")
BRAIN = (ROOT / "brain.js").read_text(encoding="utf-8")
LAB = (ROOT / "lab.js").read_text(encoding="utf-8")
TOOLS_JS = (ROOT / "tools.js").read_text(encoding="utf-8")
LOCAL_TOOLS = (ROOT / "jarvis_local_tools.py").read_text(encoding="utf-8")
RESEARCH = (ROOT / "jarvis_research.py").read_text(encoding="utf-8")
BROWSER = (ROOT / "jarvis_browser.py").read_text(encoding="utf-8")
REMOTE_SERVER = (ROOT / "jarvis_remote_server.py").read_text(encoding="utf-8")
EVOLUTION = (ROOT / "jarvis_evolution.py").read_text(encoding="utf-8")
EXTENSION_BG = (ROOT / "browser_extension" / "background.js").read_text(encoding="utf-8")
EXTENSION_CONTENT = (ROOT / "browser_extension" / "content.js").read_text(encoding="utf-8")
EXTENSION_POPUP = (ROOT / "browser_extension" / "popup.js").read_text(encoding="utf-8")
FINAL_WORKFLOW = (ROOT / ".github" / "workflows" / "JARVIS-FINAL-BUILD.yml").read_text(encoding="utf-8")
APP = (ROOT / "jarvis_app.py").read_text(encoding="utf-8")
REQUIREMENTS = (ROOT / "requirements.txt").read_text(encoding="utf-8")
WIX = (ROOT / "installer" / "Package.wxs").read_text(encoding="utf-8")


class ClassicUiRegressionTests(unittest.TestCase):
    def test_classic_startup_sequence_is_present(self) -> None:
        for marker in ('id="startGate"', 'id="initBtn"', "INITIALIZE SYSTEM", 'id="bootOverlay"'):
            self.assertIn(marker, HTML)

    def test_compact_settings_rectangle_is_restored(self) -> None:
        self.assertRegex(HTML, r"#memPanel\{[^}]*left:92px[^}]*width:min\(760px,calc\(100vw - 120px\)\)")
        self.assertRegex(HTML, r"#memPanel\.settings-manual-scroll\{[^}]*width:min\(760px,calc\(100vw - 120px\)\)")
        self.assertRegex(HTML, r"#memPanel\{[^}]*height:min\(650px,calc\(100vh - 36px\)\)")
        self.assertNotIn("height:min(900px", HTML)

    def test_settings_scroll_viewport_is_explicitly_bounded(self) -> None:
        self.assertRegex(HTML, r"\.settingsMain\{[^}]*position:relative[^}]*height:100%[^}]*overflow:hidden")
        self.assertRegex(HTML, r"\.settingsTopbar\{[^}]*flex:0 0 54px")
        self.assertRegex(HTML, r"\.settingsPages\{[^}]*position:absolute")
        self.assertRegex(HTML, r"\.settingsPages\{[^}]*inset:54px 0 0 0")
        self.assertRegex(HTML, r"\.settingsPages\{[^}]*overflow-y:scroll!important")
        self.assertIn('class="settingsPages" tabindex="0"', HTML)
        self.assertNotIn("installSettingsWheelFallback", HTML)
        self.assertNotIn("panel.addEventListener('wheel'", HTML)

    def test_settings_have_manual_scroll_controls(self) -> None:
        self.assertIn('id="settingsScrollUpBtn"', HTML)
        self.assertIn('id="settingsScrollDownBtn"', HTML)
        self.assertIn("scroller.scrollTop=target", HTML)
        self.assertIn("window.addEventListener('wheel'", HTML)
        self.assertIn("{capture:true,passive:true}", HTML)
        self.assertNotRegex(HTML, r"wheel[^\n]{0,500}preventDefault")
        self.assertIn("setInterval(function(){move(direction,false);},105)", HTML)
        self.assertRegex(HTML, r"\.settingsManualScroll\{[^}]*display:none")
        self.assertRegex(HTML, r"\.settingsManualScroll\{[^}]*position:fixed")
        self.assertIn(".settingsManualScroll.visible{display:flex;}", HTML)
        self.assertIn("var left=rect.right+gap", HTML)
        self.assertIn("gap=12", HTML)
        self.assertIn("name==='appearance'||name==='fonts'", HTML)
        self.assertIn("classList.toggle('settings-manual-scroll'", HTML)
        self.assertIn("#memPanel.settings-manual-scroll .settingsPages{width:100%", HTML)

    def test_external_browser_pairing_survives_popup_and_protected_pages(self) -> None:
        self.assertIn('chrome.alarms.create("jarvis-poll-backup"', EXTENSION_BG)
        self.assertIn('await refreshRegistration(false)', EXTENSION_BG)
        self.assertIn('/extension/register', EXTENSION_BG)
        self.assertIn('JARVIS is still paired, but this page does not allow the reader', EXTENSION_POPUP)
        self.assertIn('time.time() - last_seen < 95', BROWSER)
        self.assertNotIn('External browser is not connected. Open the JARVIS browser extension once, then press Connect.', HTML)

    def test_chat_and_lab_clear_the_global_settings_button(self) -> None:
        self.assertIn("body.chat-mode #settingsBtn{display:none!important}", HTML)
        self.assertRegex(HTML, r"\.chatSidebar\{position:relative;padding-top:0")
        self.assertRegex(HTML, r"\.labPanel\{[^}]*top:146px")
        self.assertIn("document.body.classList.toggle('brain-mode',brainOpen)", HTML)
        self.assertIn("document.body.classList.toggle('lab-mode',labOpen)", HTML)

    def test_settings_gear_stays_above_settings_and_brain(self) -> None:
        self.assertIn("#settingsBtn{z-index:100}", HTML)
        self.assertIn("body.brain-mode #settingsBtn{z-index:100}", HTML)
        self.assertRegex(HTML, r"\.brainNodeCard\{[^}]*top:50%[^}]*transform:translateY\(-50%\)")
        self.assertIn("brainNodeCard.side-right", HTML)

    def test_device_control_header_has_enable_and_real_test(self) -> None:
        self.assertIn('id="enableDeviceControlBtn"', HTML)
        self.assertIn('id="testDeviceControlBtn"', HTML)
        self.assertIn("'/desktop/control'", HTML)
        self.assertIn("'/desktop/control/test'", HTML)
        self.assertIn('if path == "/desktop/control":', BROWSER)
        self.assertIn('if path == "/desktop/control/test":', BROWSER)
        self.assertIn("return isInstalledLocalApp()?location.origin:'http://127.0.0.1:5015'", HTML)

    def test_colors_and_fonts_use_full_card_hitboxes(self) -> None:
        self.assertRegex(HTML, r"\.themeOption\{[^}]*display:block[^}]*width:100%[^}]*pointer-events:auto")
        self.assertRegex(HTML, r"\.fontOption\{[^}]*display:block[^}]*width:100%[^}]*pointer-events:auto")
        self.assertIn(".themeOption>*,.themeOption>* *,.fontOption>*,.fontOption>* *{pointer-events:none}", HTML)
        self.assertIn("b.addEventListener('click',function(){applyTheme(t,true);});", HTML)
        self.assertIn("b.addEventListener('click',function(){applyFont(n,true);});", HTML)

    def test_hover_never_applies_a_font_or_theme(self) -> None:
        self.assertNotRegex(HTML, r"(?:mouseenter|mouseover)[^\n]{0,300}applyFont")
        self.assertNotRegex(HTML, r"(?:mouseenter|mouseover)[^\n]{0,300}applyTheme")

    def test_brain_mode_has_interactive_3d_knowledge_ui(self) -> None:
        for marker in ('id="brainModeBtn"', 'id="brainWorkspace"', 'id="brainCanvas"', 'id="brainLearnBtn"', 'id="brainSummaryBtn"'):
            self.assertIn(marker, HTML)
        self.assertIn('<script src="/brain.js"></script>', HTML)
        self.assertIn("MAX_RESEARCH_TABS=10", BRAIN)
        self.assertIn("requestAnimationFrame(animate)", BRAIN)
        self.assertIn("addEventListener('wheel'", BRAIN)
        self.assertIn("FACTORY", BRAIN)
        self.assertIn("REDDIT COMMUNITY", BRAIN)
        self.assertIn("brain_knowledge", HTML)

    def test_brain_learning_is_tab_scoped_and_read_route_is_local(self) -> None:
        self.assertIn("Learn mode only runs inside Brain", BRAIN)
        self.assertIn("closeResearchTabs(", BRAIN)
        self.assertIn('"/tab/read": "read_text"', BROWSER)
        self.assertIn('"/brain.js": "brain.js"', BROWSER)

    def test_brain_has_timed_learn_mode_and_external_browser_path(self) -> None:
        for marker in ('id="brainLearnSetup"', 'id="brainLearnMinutes"', 'id="brainLearnStartBtn"'):
            self.assertIn(marker, HTML)
        self.assertIn("learnDeadline", BRAIN)
        self.assertIn("learn(?:\\s+mode)?\\s+for", BRAIN)
        self.assertIn("api.getBrowsingMode&&api.getBrowsingMode()==='external'", BRAIN)
        self.assertIn("externalResearch:brainExternalResearch", HTML)
        self.assertIn("localBridgeJson('/extension/research',{brain_learn:true", HTML)
        self.assertNotIn("localBridgeJson('/extension/learn-research'", HTML)
        self.assertIn('if path == "/extension/learn-research":', BROWSER)
        self.assertIn('if path == "/extension/learn-cancel":', BROWSER)
        self.assertIn("learnPhase='starting'", BRAIN)
        self.assertIn("learnPhase='opening';learnDeadline=0", BRAIN)
        self.assertIn("if(learnPhase==='opening')", BRAIN)
        self.assertIn("FIRST SOURCE READ · TIMER STARTED", BRAIN)
        self.assertIn("LEARNED '+sessionNodeIds.length+' · '+remainingLabel()", BRAIN)
        self.assertIn("failLearnMode", BRAIN)
        self.assertIn("researchPreflight:brainResearchPreflight", HTML)

    def test_brain_prefers_unseen_topics_before_researching_again(self) -> None:
        self.assertIn("sessionResearchQueries", BRAIN)
        self.assertIn("knownLabels", BRAIN)
        self.assertIn("!knownLabels[label]&&!sessionResearchQueries[k]", BRAIN)
        self.assertIn("NO UNSEEN RESEARCH TOPICS REMAIN", BRAIN)

    def test_extension_pairing_and_learn_research_survive_popup_close(self) -> None:
        self.assertIn("registerSavedConnection(true)", EXTENSION_POPUP)
        self.assertIn('periodInMinutes: 0.5', EXTENSION_BG)
        self.assertIn("Promise.all(commands.map", EXTENSION_BG)
        self.assertIn("active: !command.brain_learn || command.brain_batch_index === 0", EXTENSION_BG)
        self.assertIn("https://www.bing.com/search?q=", EXTENSION_BG)
        self.assertIn('#b_results li.b_algo h2 a[href]', EXTENSION_CONTENT)
        self.assertEqual(EXTENSION_CONTENT.count('if (command.operation === "read_page")'), 1)

    def test_lab_is_native_mode_with_model_handoff(self) -> None:
        for marker in ('id="labModeBtn"', 'id="labWorkspace"', 'id="labCanvas"', 'id="labImportBtn"', 'id="labPrintBtn"'):
            self.assertIn(marker, HTML)
        self.assertIn('<script src="/lab.js"></script>', HTML)
        self.assertIn('"/lab.js": "lab.js"', BROWSER)
        self.assertIn('if path == "/lab/import":', BROWSER)
        self.assertIn('if path == "/lab/open-in-bambu":', BROWSER)
        self.assertIn("parseBinaryStl", LAB)
        self.assertIn("parseObj", LAB)
        self.assertIn("exportStl", LAB)
        self.assertIn("pre-slice estimate", LAB)
        self.assertIn("openInBambu", LAB)

    def test_lab_creator_and_inspection_tools_are_real(self) -> None:
        for marker in ('id="labDesignBtn"', 'data-lab-primitive="sphere"', 'id="labUndoBtn"', 'id="labAutoFitBtn"', 'id="labExportBtn"', 'id="labA1Fit"'):
            self.assertIn(marker, HTML)
        for marker in ("sphereMesh", "torusMesh", "designFromPrompt", "handleVoiceCommand", "downloadStl", "snapshotPng", "autoFitA1", "mirrorAxis"):
            self.assertIn(marker, LAB)
        self.assertIn("callAIText:callAIText", HTML)
        self.assertIn("openLab:function(){setMainMode('lab');}", HTML)

    def test_lab_printer_profiles_safe_generator_and_scale_in_place(self) -> None:
        for printer in ("a1mini", "a1", "p1s", "x1c", "x2d", "a2l", "h2c", "h2s", "h2d"):
            self.assertIn(printer + ":{label:", LAB)
        self.assertIn('id="labPrinter"', HTML)
        self.assertIn('id="labMaterialPrice"', HTML)
        self.assertNotIn('id="labFilamentCost"', HTML)
        self.assertIn("boatHullMesh", LAB)
        self.assertIn("SAFE_GENERATED_MM=120", LAB)
        self.assertIn("SAFE_GENERATED_CM3=180", LAB)
        self.assertIn("setScalePreservingPlacement", LAB)
        self.assertIn("restorePlacementAnchor", LAB)
        self.assertIn("drawBuildPlate", LAB)
        for control in ("labNozzle", "labWalls", "labTopLayers", "labBottomLayers", "labInfillPattern", "labSupports", "labBrim", "labSeam", "labPlateType", "labSequence"):
            self.assertIn('id="' + control + '"', HTML)

    def test_lab_extended_bambu_profiles_and_studio_controls(self) -> None:
        for printer in ("a2l", "x2daux", "x2dtotal", "h2ctotal", "h2ddual", "h2dtotal", "h2dpro", "h2dprodual", "h2dprototal"):
            self.assertIn(printer + ":{label:", LAB)
        self.assertIn("h2dtotal:{label:'H2D · TOTAL',family:'H',x:350,y:320,z:320", LAB)
        for control in ("labQualityPreset", "labFirstLayer", "labLineWidth", "labWallGenerator", "labTopPattern", "labBottomPattern", "labSupportStyle", "labSupportAngle", "labBrimWidth", "labSkirtLoops", "labIroning", "labElephantFoot", "labTimelapse", "labOuterSpeed", "labInnerSpeed", "labInfillSpeed", "labFirstLayerSpeed", "labTravelSpeed", "labPrepareBambuBtn", "labExportPresetBtn"):
            self.assertIn('id="' + control + '"', HTML)
        self.assertIn('if path == "/lab/bambu-capabilities":', BROWSER)
        self.assertIn('"automatic_print_start": False', BROWSER)
        self.assertIn("background_requested", BROWSER)

    def test_lab_design_does_not_fall_back_to_random_box_or_oversize_models(self) -> None:
        self.assertIn("A boat or ship MUST use boat_hull, never a lone cylinder", LAB)
        self.assertIn("fallbackDesign(prompt){return semanticDesign(prompt);}", LAB)
        self.assertIn("AUTO-SCALED TO PRACTICAL PRINT SIZE", LAB)
        self.assertIn("setScalePreservingPlacement", LAB)

    def test_external_worker_status_persists_and_manual_scroll_has_tab_like_fallback(self) -> None:
        self.assertIn("lastConnectedAt", EXTENSION_BG)
        self.assertIn("jarvis-worker-status", EXTENSION_BG)
        self.assertIn("changes.baseUrl || changes.pairingCode", EXTENSION_BG)
        self.assertIn("focusFallback", HTML)
        self.assertIn("scrollIntoView", HTML)
        self.assertIn("try{best.focus();}", HTML)
        self.assertIn("move(direction,true,true)", HTML)
        self.assertIn("window.addEventListener('wheel'", HTML)
        self.assertIn("window.addEventListener('keydown'", HTML)

    def test_tools_workspace_has_more_than_twenty_key_free_tools(self) -> None:
        for marker in ('id="toolsModeBtn"', 'id="toolsWorkspace"', '<script src="/tools.js"></script>'):
            self.assertIn(marker, HTML)
        for marker in ('"/tools.js": "tools.js"', 'if path == "/tools/catalog":', 'if path == "/tools/run":', 'if path == "/tools/command":'):
            self.assertIn(marker, BROWSER)
        self.assertGreaterEqual(LOCAL_TOOLS.count("ToolSpec("), 20)
        self.assertIn('"no_api_required": True', LOCAL_TOOLS)
        self.assertIn('"no_signup_required": True', LOCAL_TOOLS)
        self.assertIn("Unknown local tool.", LOCAL_TOOLS)
        self.assertIn("JarvisTools", TOOLS_JS)

    def test_research_uses_public_providers_without_captcha_automation(self) -> None:
        for source in ("Wikipedia", "Hacker News", "Stack Exchange", "Crossref", "arXiv", "Open Library", "GitHub", "npm"):
            self.assertIn(source, RESEARCH)
        self.assertIn("failing provider never prevents", RESEARCH)
        self.assertIn("never solve or bypass web challenges", BROWSER)
        self.assertNotIn("captcha solver", RESEARCH.lower())

    def test_profile_session_is_saved_for_reload(self) -> None:
        self.assertIn("localStorage.getItem(PROFILE_TOKEN_KEY)||sessionStorage.getItem(PROFILE_TOKEN_KEY)", HTML)
        self.assertIn("localStorage.setItem(PROFILE_TOKEN_KEY,profileToken)", HTML)
        self.assertIn("sessionStorage.removeItem(PROFILE_TOKEN_KEY)", HTML)

    def test_research_challenges_switch_sources_without_captcha_bypass(self) -> None:
        self.assertIn("verificationPage", BRAIN)
        self.assertIn("publicResearchFallback", BRAIN)
        self.assertIn("VERIFICATION BLOCKED", BRAIN)
        self.assertIn("publicResearch:function(query,label)", HTML)
        self.assertIn('if path == "/research/public-source":', BROWSER)
        self.assertIn("public_research_source", BROWSER)
        self.assertIn("never solve or bypass web challenges", BROWSER)

    def test_camera_privacy_recovery_is_exposed(self) -> None:
        self.assertIn('id="openWindowsCameraPrivacyBtn"', HTML)
        self.assertIn("'/desktop/camera-privacy'", HTML)
        self.assertIn('if path == "/desktop/camera-privacy":', BROWSER)

    def test_quick_controls_remain_available_in_chat_and_brain(self) -> None:
        self.assertNotIn("body.brain-mode #quickControlsDock{display:none", HTML)
        self.assertIn("setNativeOverlayVisibility(true)", BRAIN)
        self.assertIn("if(!brainOpen)setNativeOverlayVisibility(true)", HTML)

    def test_speech_recognition_blocks_jarvis_own_voice(self) -> None:
        self.assertIn("function finishSpeechRecognitionBlock()", HTML)
        self.assertIn("speakingBlockRecognition || Date.now() < ignoreRecognitionUntil", HTML)
        self.assertIn("Date.now()-lastSpokenEndedAt<5000 && isLikelyEcho(transcript)", HTML)
        self.assertIn("lastSpokenEndedAt + 900", HTML)

    def test_global_interface_fx_and_motion_are_wired(self) -> None:
        for marker in ('id="fxSoundToggle"', 'id="fxSoundTest"', 'id="fxSoundVolume"'):
            self.assertIn(marker, HTML)
        self.assertIn("window.JarvisFX={tone:tone", HTML)
        self.assertIn("jarvisFxPulse", HTML)
        self.assertIn("@keyframes jarvisFxPanelIn", HTML)
        self.assertIn("prefers-reduced-motion:reduce", HTML)
        self.assertIn("interface_fx_enabled", HTML)
        self.assertIn("interface_fx_volume", HTML)
        self.assertIn("window.JarvisFX&&window.JarvisFX.tone", BRAIN)
        self.assertIn("window.JarvisFX&&window.JarvisFX.tone", LAB)

    def test_font_preview_text_and_per_card_family_are_present(self) -> None:
        self.assertIn("Aa Bb Cc · JARVIS 0123456789", HTML)
        self.assertIn("b.style.setProperty('font-family',\"'\"+n+\"', sans-serif\",'important')", HTML)


class AppPackagingRegressionTests(unittest.TestCase):
    def test_native_webview_window_is_used(self) -> None:
        self.assertIn("import webview", APP)
        self.assertIn("webview.create_window", APP)
        self.assertIn('gui="edgechromium"', APP)
        self.assertIn("private_mode=False", APP)
        self.assertIn("pywebview>=6.2.1,<7", REQUIREMENTS)
        self.assertNotIn("open_app_window(", APP)

    def test_no_windows_autostart_or_shell_replacement_code(self) -> None:
        joined = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("*.py"))
        forbidden = ("Winlogon", "SetValueEx", "schtasks", "CurrentVersion\\\\Run", "explorer.exe /shell")
        for marker in forbidden:
            self.assertNotIn(marker.lower(), joined.lower())

    def test_factory_config_contains_no_personal_tokens(self) -> None:
        config = json.loads((ROOT / "jarvis_server_config.json").read_text(encoding="utf-8"))
        self.assertEqual(config.get("access_code"), "")
        self.assertEqual(config.get("browser_extension_pairing_code"), "")
        serialized = json.dumps(config).lower()
        for marker in ("api_key", "oauth_token", "refresh_token", "password"):
            self.assertNotIn(marker, serialized)

    def test_workflow_builds_the_files_that_exist(self) -> None:
        for filename in (
            "jarvis_app.py",
            "jarvis_v2.html",
            "brain.js",
            "lab.js",
            "tools.js",
            "jarvis_web.html",
            "jarvis_server_config.json",
            "manifest.webmanifest",
            "service-worker.js",
        ):
            self.assertTrue((ROOT / filename).is_file(), filename)
            self.assertIn(filename, FINAL_WORKFLOW)
        for module in ("jarvis_local_tools", "jarvis_research"):
            self.assertTrue((ROOT / (module + ".py")).is_file(), module)
            self.assertIn("--hidden-import " + module, FINAL_WORKFLOW)
        self.assertTrue((ROOT / "browser_extension").is_dir())
        self.assertIn("browser_extension:browser_extension", FINAL_WORKFLOW)

    def test_frozen_app_uses_persistent_local_appdata(self) -> None:
        for source in (BROWSER, REMOTE_SERVER):
            self.assertIn('Path(local_appdata) / "JARVIS" / "jarvis_server_config.json"', source)
            self.assertIn('Path(user_profile) / "AppData" / "Local" / "JARVIS"', source)
            frozen_block = source.split('if getattr(sys, "frozen", False):', 1)[1].split('directories =', 1)[0]
            self.assertNotIn('directories = (RUN_DIR,)', frozen_block)
        self.assertIn('ACCOUNT_DB_PATH = CONFIG_PATH.parent / "jarvis_accounts.sqlite3"', REMOTE_SERVER)
        self.assertIn('storage = jarvis_browser.CONFIG_PATH.parent / "webview_profile"', APP)

    def test_installer_build_is_the_downloaded_artifact(self) -> None:
        wixproj = (ROOT / "installer" / "JARVIS.Installer.wixproj").read_text(encoding="utf-8")
        self.assertIn("WixToolset.Sdk/6.0.2", wixproj)
        self.assertNotIn("<SuppressIces>", wixproj)
        self.assertIn('Scope="perMachine"', WIX)
        self.assertIn('Version="$(JarvisVersion)"', WIX)
        self.assertIn('AllowSameVersionUpgrades="yes"', WIX)
        self.assertIn('4.3.$env:GITHUB_RUN_NUMBER', FINAL_WORKFLOW)
        self.assertIn('StandardDirectory Id="ProgramFiles64Folder"', WIX)
        self.assertIn('StandardDirectory Id="ProgramMenuFolder"', WIX)
        self.assertIn('Name="J.A.R.V.I.S."', WIX)
        self.assertIn('KeyPath="yes"', WIX)
        self.assertRegex(WIX, r'<File Id="JarvisExe"[^>]*>\s*<Shortcut')
        self.assertIn('Advertise="yes"', WIX)
        self.assertNotIn('Component Id="StartMenuShortcut"', WIX)
        self.assertNotIn('Target="[#JarvisExe]"', WIX)
        self.assertNotIn('LocalAppDataFolder', WIX)
        self.assertIn("dotnet build installer/JARVIS.Installer.wixproj", FINAL_WORKFLOW)
        self.assertIn("JARVIS_V4_3_CLASSIC_APP.msi", FINAL_WORKFLOW)
        self.assertIn("actions/upload-artifact@v7", FINAL_WORKFLOW)
        self.assertIn("archive: false", FINAL_WORKFLOW)

    def test_installed_app_requests_uac_on_every_launch(self) -> None:
        self.assertIn("--uac-admin", FINAL_WORKFLOW)

    def test_final_workflow_guards_the_exact_mcp_cli_failure(self) -> None:
        self.assertIn("Build JARVIS V4.3 Installed Windows App", FINAL_WORKFLOW)
        self.assertIn('mcp[cli]>=2.0.0,<3', FINAL_WORKFLOW)
        self.assertIn("import typer", FINAL_WORKFLOW)
        self.assertNotIn("--collect-all mcp", FINAL_WORKFLOW)
        self.assertNotIn("--collect-all httpx2", FINAL_WORKFLOW)
        self.assertIn("--hidden-import mcp.client.streamable_http", FINAL_WORKFLOW)
        self.assertIn("--hidden-import httpx2", FINAL_WORKFLOW)
        self.assertIn("--hidden-import jarvis_accounts", FINAL_WORKFLOW)
        self.assertIn("--hidden-import jarvis_evolution", FINAL_WORKFLOW)
        self.assertIn("--hidden-import jarvis_local_tools", FINAL_WORKFLOW)
        self.assertIn("--hidden-import jarvis_research", FINAL_WORKFLOW)

    def test_account_and_optional_azure_voice_are_wired(self) -> None:
        self.assertIn('data-settings-page="account"', HTML)
        self.assertIn('data-page="account"', HTML)
        self.assertIn('id="azureSpeechKey"', HTML)
        self.assertIn("/profile/voice/synthesize", HTML)
        self.assertIn("en-US-RyanMultilingualNeural", HTML)
        self.assertIn("mergeProfileData", HTML)
        self.assertIn("isPersonalProfileInfo", HTML)

    def test_guarded_evolution_is_visible_and_functional(self) -> None:
        self.assertIn('data-settings-page="evolution"', HTML)
        self.assertIn('data-page="evolution"', HTML)
        for marker in (
            'id="evolutionWorkspace"', 'id="evolutionSaveSkillBtn"',
            'id="evolutionStagePatchBtn"', 'id="evolutionProposalList"',
        ):
            self.assertIn(marker, HTML)
        for route in (
            "/evolution/status", "/evolution/config", "/evolution/skill",
            "/evolution/intent", "/evolution/propose", "/evolution/apply",
            "/evolution/rollback",
        ):
            self.assertIn(route, HTML)
            self.assertIn(f'if path == "{route}":', BROWSER)
        self.assertIn("selfModificationRequest", HTML)
        self.assertIn("pendingEvolutionIntent", HTML)

    def test_evolution_never_silently_rewrites_executable_code(self) -> None:
        self.assertIn('"automatic_executable_code_changes": False', EVOLUTION)
        self.assertIn('state["code_changes_require_approval"] = True', EVOLUTION)
        self.assertIn('state["automatic_executable_code_changes"] = False', EVOLUTION)
        self.assertIn("approval_phrase", EVOLUTION)
        self.assertIn("base_sha256", EVOLUTION)
        self.assertIn("backups_dir", EVOLUTION)
        self.assertIn("Validation failed. JARVIS restored the previous source automatically.", EVOLUTION)

    def test_autonomous_improvements_are_external_or_review_queued(self) -> None:
        self.assertIn("remember_skill", EVOLUTION)
        self.assertIn('"kind": "external_skill"', EVOLUTION)
        self.assertIn('"status": "needs_patch"', EVOLUTION)
        self.assertIn("noteEvolutionFailure", HTML)
        self.assertIn("origin:'jarvis'", HTML)
        self.assertIn("evolutionSkillsForPrompt", HTML)
        self.assertIn("Active JARVIS behavior skills", HTML)


if __name__ == "__main__":
    unittest.main()
