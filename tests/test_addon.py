"""Lua 5.1 behavior and UI smoke test using WoW API doubles (optional lupa)."""
import unittest
from pathlib import Path

try:
    from lupa.lua51 import LuaRuntime
except ImportError:
    LuaRuntime = None

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(LuaRuntime is None, "Optional Lua 5.1 runtime (lupa) is unavailable")
class AddonTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('''
            unpack = unpack or table.unpack
            SVC = {}
            UISpecialFrames, SlashCmdList = {}, {}
            function fake()
                local frame = {_shown = true, _text = ""}
                return setmetatable(frame, {__index = function(self, method)
                    if method == "CreateFontString" or method == "CreateTexture" or method == "GetHighlightTexture" then return function() return fake() end end
                    if method == "GetWidth" then return function(self) return self._width or 1600 end end
                    if method == "GetHeight" then return function(self) return self._height or 1000 end end
                    if method == "SetSize" then return function(self,w,h) self._width,self._height=w,h end end
                    if method == "SetWidth" then return function(self,w) self._width=w end end
                    if method == "SetHeight" then return function(self,h) self._height=h end end
                    if method == "GetStringHeight" then return function() return 36 end end
                    if method == "SetEnabled" then return function(self,v) self._enabled=v end end
                    if method == "IsEnabled" then return function(self) return self._enabled~=false end end
                    if method == "SetPoint" then return function(self,...) self._point={...} end end
                    if method == "GetFrameLevel" then return function() return 1 end end
                    if method == "IsShown" then return function(self) return self._shown end end
                    if method == "Hide" then return function(self) local shown=self._shown; self._shown = false; if shown and self.OnHide then self.OnHide(self) end end end
                    if method == "Show" then return function(self) self._shown = true end end
                    if method == "SetShown" then return function(self,shown) self._shown=not not shown end end
                    if method == "SetText" then return function(self, text) assert(type(text)=="string" or type(text)=="number"); self._text = text end end
                    if method == "GetText" then return function(self) return self._text end end
                    if method == "SetScript" then return function(self, name, callback) self[name] = callback end end
                    if method:match("^[A-Z]") then return function() end end
                    return nil
                end})
            end
            UIParent, GameTooltip = fake(), fake()
            function GetLocale() return "frFR" end
            function CreateFrame(_, _, _, template) local frame = fake(); frame._template = template; lastFrame = frame; return frame end
            function UnitGUID() return "Player-1-AAA" end
            function UnitFullName() return "A", "Realm" end
            function GetRealmName() return "Realm" end
            function InCombatLockdown() return false end
            function time() return 1 end
            C_Timer = {After = function(_, f) f() end}
            C_AddOns = {
                GetNumAddOns = function() return 1 end,
                GetAddOnInfo = function() return "APR", "Azeroth Pilot Reloaded" end,
                GetAddOnMetadata = function() return nil end,
                IsAddOnLoaded = function() return true end
            }
            APRData = {
                ["A-Player-1-AAA"] = {GUID = "Player-1-AAA", route = {step = 42, enabled = false}},
                ["B-Player-1-BBB"] = {GUID = "Player-1-BBB", route = {step = 16, enabled = true}}
            }
        ''')
        for filename in ("Compat.lua", "Locale.lua", "Manifest.lua", "Core.lua", "Widgets.lua", "Compare.lua"):
            self.lua.execute((ROOT / filename).read_text(encoding="utf-8"), "SVCleaner", self.lua.globals().SVC)
        self.lua.execute('eventsFrame = lastFrame; eventsFrame.OnEvent(eventsFrame, "ADDON_LOADED", "SVCleaner"); eventsFrame.OnEvent(eventsFrame, "PLAYER_LOGIN")')

    def test_discovery_manifest_and_false_requests(self):
        self.lua.execute('''
            SVC:Discover()
            local row
            for _, candidate in ipairs(SVC.rows) do if candidate.root == "APRData" then row = candidate end end
            assert(row and row.available)
            assert(SVC:Queue(row, {"A-Player-1-AAA", "route", "enabled"}, "edit", true))
            assert(SVCleanerDB.requests[1].expectedValue == false)
            assert(APRData["A-Player-1-AAA"].route.enabled == false)
            assert(not SVC:Queue(row, {"A-Player-1-AAA", "GUID"}, "edit", "changed"))
        ''')

    def test_diff_keeps_guids_locked(self):
        self.lua.execute('''
            local diffs = SVC:Diff(APRData["A-Player-1-AAA"], APRData["B-Player-1-BBB"])
            local locked, editable = 0, 0
            for _, item in ipairs(diffs) do if item.protected then locked = locked + 1 elseif item.copyable then editable = editable + 1 end end
            assert(locked == 1 and editable == 2)
        ''')

    def test_native_ui_can_open_browse_compare_and_switch_themes(self):
        self.lua.execute((ROOT / "UI.lua").read_text(encoding="utf-8"), "SVCleaner", self.lua.globals().SVC)
        self.lua.execute('''
            SVC:Toggle()
            assert(SVC.frame:IsShown())
            local row
            for _, candidate in ipairs(SVC.rows) do if candidate.root == "APRData" then row = candidate end end
            SVC:OpenRow(row)
            assert(#SVC.tree.items == 2)
            SVC.left = {row = row, path = {"A-Player-1-AAA"}}
            SVC.right = {row = row, path = {"B-Player-1-BBB"}}
            SVC:ShowDiff()
            assert(SVC.diff:IsShown() and #SVC.diffList.items == 3)
            SVCleanerDB.theme = "light"; SVC.UI:Theme()
            SVC:ShowGuide(); assert(SVC.overlay:IsShown())
            SVC:ShowCompanion()
            SVC:Toggle(); assert(not SVC.frame:IsShown())
        ''')

    def test_legacy_and_partial_addon_namespaces(self):
        self.lua.execute('''
            GetNumAddOns, GetAddOnInfo = C_AddOns.GetNumAddOns, C_AddOns.GetAddOnInfo
            GetAddOnMetadata, IsAddOnLoaded = C_AddOns.GetAddOnMetadata, C_AddOns.IsAddOnLoaded
            C_AddOns = nil
            SVC:Discover()
            assert(#SVC.rows > 0)
            C_AddOns = {GetNumAddOns = function() return 1 end}
            SVC:Discover()
            local api = SVC.Compat:GetAddOnAPI()
            assert(api.GetNumAddOns == C_AddOns.GetNumAddOns)
            assert(api.GetAddOnInfo == GetAddOnInfo and #SVC.rows > 0)
        ''')

    def test_identity_and_backdrop_fallbacks(self):
        self.lua.execute('''
            UnitFullName = nil
            UnitName = function() return "LegacyPlayer", "" end
            local name, realm = SVC.Compat:PlayerIdentity()
            assert(name == "LegacyPlayer" and realm == "Realm")
            assert(SVC.Compat:BackdropTemplate() == nil)
            BackdropTemplateMixin = {}
            assert(SVC.Compat:BackdropTemplate() == "BackdropTemplate")
        ''')

    def test_no_timer_fallback_runs_only_on_next_frame(self):
        self.lua.execute('''
            C_Timer = nil
            local called = 0
            SVC.Compat:NextFrame(function() called = called + 1 end)
            assert(called == 0)
            local frame = lastFrame
            frame.OnUpdate(frame)
            assert(called == 1 and rawget(frame, "OnUpdate") == nil and not frame:IsShown())
        ''')

    def test_ui_loads_with_modern_and_historical_client_profiles(self):
        for flavor in ("Mainline", "Vanilla", "TBC", "Wrath", "Titan", "Cata", "Mists", "Camelot"):
            with self.subTest(flavor=flavor):
                self.setUp()
                self.lua.execute("BackdropTemplateMixin = {}")
                if flavor in ("Wrath", "Cata"):
                    self.lua.execute('''
                        GetNumAddOns, GetAddOnInfo = C_AddOns.GetNumAddOns, C_AddOns.GetAddOnInfo
                        GetAddOnMetadata, IsAddOnLoaded = C_AddOns.GetAddOnMetadata, C_AddOns.IsAddOnLoaded
                        C_AddOns, UnitFullName = nil, nil
                        UnitName = function() return "A", "Realm" end
                        eventsFrame.OnEvent(eventsFrame, "PLAYER_LOGIN")
                    ''')
                self.lua.execute((ROOT / "UI.lua").read_text(encoding="utf-8"), "SVCleaner", self.lua.globals().SVC)
                self.lua.execute('''
                    SVC:Toggle()
                    assert(SVC.frame:IsShown() and SVC.frame._template == "BackdropTemplate")
                    local row
                    for _, candidate in ipairs(SVC.rows) do if candidate.root == "APRData" then row = candidate end end
                    assert(row and row.available)
                    SVC:OpenRow(row)
                    SVC.left, SVC.right = {row=row,path={"A-Player-1-AAA"}}, {row=row,path={"B-Player-1-BBB"}}
                    SVC:ShowDiff()
                    assert(SVC.diff:IsShown() and #SVC.diffList.items == 3)
                    SVCleanerDB.theme = "light"; SVC.UI:Theme()
                ''')

    def open_ui(self):
        self.lua.execute((ROOT / "UI.lua").read_text(encoding="utf-8"), "SVCleaner", self.lua.globals().SVC)
        self.lua.execute('SVC:Toggle()')

    def test_minimap_launcher_click_drag_and_persisted_position(self):
        self.open_ui()
        self.lua.execute('''
            Minimap=fake(); Minimap:SetSize(160,160)
            Minimap.GetCenter=function() return 200,200 end
            Minimap.GetEffectiveScale=function() return 2 end
            GetCursorPosition=function() return 600,400 end
            GetMinimapShape=function() return "ROUND" end
            SVCleanerDB.minimap={angle=90}
            eventsFrame.OnEvent(eventsFrame,"PLAYER_LOGIN")
            local button=SVC.minimapButton; assert(button and button:GetWidth()==32)
            assert(math.abs(button._point[4])<.001 and math.abs(button._point[5]-88)<.001)
            button.OnClick(button); assert(not SVC.frame:IsShown())
            button.OnMouseDown(button); button.OnDragStart(button); button.OnUpdate(button)
            assert(SVCleanerDB.minimap.angle==0 and button._point[4]==88)
            button.OnDragStop(button); assert(rawget(button,"OnUpdate")==nil)
            button.OnClick(button); assert(not SVC.frame:IsShown())
            button.OnMouseDown(button); button.OnClick(button); assert(SVC.frame:IsShown())
            SVC:CreateMinimapButton(); assert(SVC.minimapButton==button)
            GetMinimapShape=function() return "SQUARE" end
            SVCleanerDB.minimap.angle=45; SVC:PositionMinimapButton()
            assert(math.abs(button._point[4]-88)<.001 and math.abs(button._point[5]-88)<.001)
            GetMinimapShape=function() return "CORNER-TOPRIGHT" end
            SVC:PositionMinimapButton(); assert(button._point[4]<88)
            SVCleanerDB.minimap.angle="invalid"; SVC:CreateMinimapButton(); assert(SVCleanerDB.minimap.angle==225)
        ''')

    def test_combined_filters_keep_unloaded_and_loaded_distinct(self):
        self.open_ui()
        self.lua.execute('''
            SVC.rows = {
                {addon="APR",title="APR",root="APRData",scope="account",loaded=true,available=true,bytes=0},
                {addon="APR",title="APR",root="APRChar",scope="character",loaded=true,available=true,bytes=0},
                {addon="Other",title="Other",root="OtherDB",scope="account",loaded=false,available=false,bytes=0}}
            SVC:Refresh(); assert(#SVC.catalog.items==2)
            SVC.filters.scope="character"; SVC:Refresh(); assert(#SVC.catalog.items==1)
            SVC.filters.scope="all"; SVC.filters.state="unloaded"; SVC:Refresh(); assert(#SVC.catalog.items==1 and SVC.catalog.items[1].addon=="Other")
            SVC.filters.addon="APR"; SVC:Refresh(); assert(#SVC.catalog.items==0)
            SVC:ResetFilters(); assert(#SVC.catalog.items==2)
            SVC.query="aprdata"; SVC:Refresh(); assert(#SVC.catalog.items==1)
            assert(SVC:CharacterLabel("10-fillers - Custom-RawTotalSteps")==nil)
        ''')

    def test_resize_keeps_grid_and_inspector_inside_window_and_dismisses_menu(self):
        self.open_ui()
        self.lua.execute('''
            for _,size in ipairs({{1040,680},{1500,980}}) do
                SVC.frame:SetSize(size[1],size[2]); SVC:Layout()
                assert(SVC.catalog:GetWidth()+SVC.tree:GetWidth()+12==size[1]-32)
                SVC.detail:Show(); SVC:Layout()
                assert(-SVC.deleteButton._point[5]+SVC.deleteButton:GetHeight()<=SVC.detail:GetHeight())
                assert(SVC.detail:GetWidth()==SVC.tree:GetWidth())
                assert(SVC.diffList:GetWidth()==size[1]-64)
            end
            SVC.stateFilter.OnClick(); local first=SVC.UI.menu
            SVC.scopeFilter.OnClick(); assert(SVC.UI.menu==first)
            SVC.UI.menu.search:SetText("person"); SVC.UI.menu:Filter("person")
            assert(#SVC.UI.menu.list.items==1)
            assert(SVC.UI.menuOutside:IsShown())
            SVC.UI.menuOutside.OnClick(); assert(not first:IsShown() and not SVC.UI.menuOutside:IsShown())
            SVC.stateFilter.OnClick(); assert(first:IsShown())
            first.search.OnEscapePressed(); assert(not first:IsShown())
            SVC.stateFilter.OnClick(); SVC.stateFilter.OnClick(); assert(not first:IsShown())
        ''')

    def test_grid_exposes_values_and_compares_two_named_records_without_pin_buttons(self):
        self.open_ui()
        self.lua.execute('''
            local row; for _,r in ipairs(SVC.rows) do if r.root=="APRData" then row=r end end
            SVC:OpenRow(row)
            assert(SVC.tree.rowHeight==30 and SVC.tree.columns[4].label==SVC.L.VALUE)
            SVC:MarkComparison(SVC.tree.items[1]); SVC:MarkComparison(SVC.tree.items[2]); SVC:CompareSelection()
            assert(SVC.left.path[1]=="A-Player-1-AAA" and SVC.right.path[1]=="B-Player-1-BBB")
            assert(SVC.diffList.headings[2]:GetText()=="A" and SVC.diffList.headings[3]:GetText()=="B")
            assert(SVC.copyRight.label:GetText()==string.format(SVC.L.COPY_TO,"B"))
            SVC:ShowPage("data"); SVC.path={"A-Player-1-AAA","route"}; SVC:RefreshTree()
            local visible=false
            for _,button in ipairs(SVC.tree.rows) do if button.item and button.item.key=="step" then
                assert(button.cells[3]:GetText()==SVC.L.NUMBER and button.cells[4]:GetText()=="42"); visible=true
            end end
            assert(visible and #SVC.pending==0)
        ''')

    def test_copy_preview_false_value_and_identity_protection(self):
        self.open_ui()
        self.lua.execute('''
            local row; for _,r in ipairs(SVC.rows) do if r.root=="APRData" then row=r end end
            SVC.left={row=row,path={"A-Player-1-AAA"}}; SVC.right={row=row,path={"B-Player-1-BBB"}}
            SVC:ShowDiff()
            assert(SVC.leftPicker.label:GetText():find("A",1,true))
            assert(SVC.rightPicker.label:GetText():find("B",1,true))
            local flag,locked; for _,r in ipairs(SVC.diffRows) do if r.path[#r.path]=="enabled" then flag=r end; if r.protected then locked=r end end
            SVC:QueueDiff(flag,"right"); assert(SVC.review:IsShown() and #SVC.pending==0)
            SVC.reviewCallback(); assert(#SVC.pending==1 and SVC.pending[1].value==false)
            assert(APRData["B-Player-1-BBB"].route.enabled==true)
            SVC:QueueDiff(locked,"right"); assert(#SVC.pending==1)
            SVC:QueueDiff(flag,"right"); SVC.reviewCallback(); assert(#SVC.pending==1)
            SVC:RefreshDiff(); local staged
            for _,r in ipairs(SVC.diffRows) do if r.path[#r.path]=="enabled" then staged=r end end
            assert(staged.rightPrepared and staged.rightPlanned==false)
        ''')

    def test_detail_draft_survives_refresh_and_stale_copy_is_rejected(self):
        self.open_ui()
        self.lua.execute('''
            local row; for _,r in ipairs(SVC.rows) do if r.root=="APRData" then row=r end end
            SVC:OpenRow(row); SVC.path={"A-Player-1-AAA","route"}; SVC:RefreshTree()
            local item; for _,r in ipairs(SVC.tree.items) do if r.key=="step" then item=r end end
            SVC:SelectValue(item); SVC.editor:SetText("45"); SVC:Refresh(); assert(SVC.editor:GetText()=="45")
            SVC:QueueSelection("edit"); APRData["A-Player-1-AAA"].route.step=99; SVC.reviewCallback()
            assert(#SVC.pending==0)
        ''')

    def test_search_folds_accented_and_cyrillic_names_without_changing_keys(self):
        self.lua.execute('assert(SVC:Fold("ÉLOWEN АЛЬДРИК") == "élowen альдрик")')
        self.lua.execute('assert(SVC.UI:Display("ééé",3)=="é..."); assert(SVC.UI:Display("a|b")=="a||b")')

    def test_large_strings_are_read_only_and_display_is_bounded(self):
        self.open_ui()
        self.lua.execute('''
            local large=string.rep("a",40000)
            SVC.original:SetText(large)
            assert(#SVC.original.fullText==40000 and #SVC.original.text:GetText()<34000)
            local diff=SVC:Diff({text=large},{text="short"})
            assert(diff[1].large and not diff[1].copyable)
        ''')

    def test_guide_names_are_editable_but_guid_and_id_fields_stay_protected(self):
        self.lua.execute('''
            assert(not SVC:IsIdentity("RXPGuidesDB",{}))
            assert(not SVC:IsIdentity("Guido-Player-1-AAA",{}))
            assert(not SVC:IsIdentity("valid",true))
            assert(SVC:IsIdentity("questId",12) and SVC:IsIdentity("cachedGuidValue",12))
            assert(SVC:IsIdentity("GUIDs",{}) and SVC:IsIdentity("playerGUID",12))
        ''')
