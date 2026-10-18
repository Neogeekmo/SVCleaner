local ADDON, SVC = ...
local L = SVC.L
SVC.name = ADDON
SVC.rows, SVC.pending = {}, {}

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_REGEN_DISABLED")
events:RegisterEvent("PLAYER_LOGOUT")
events:RegisterEvent("CVAR_UPDATE")
events:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" and name == ADDON then
        SVC.databaseReady = SVC:InitializeDatabase()
        if not SVC.databaseReady then print("SVCleaner: " .. L.DATABASE_UNSUPPORTED) end
    elseif not SVC.databaseReady then
        return
    elseif event == "PLAYER_LOGIN" then
        local guid = UnitGUID("player")
        local playerName, realm = SVC.Compat:PlayerIdentity()
        if guid then SVCleanerDB.characters[guid] = {name = playerName, realm = realm, lastSeen = time()} end
        SVC:CreateMinimapButton()
        SVC.loggedIn = true
        SVC.Compat:NextFrame(function() SVC:VerifyPending() end)
        -- Discovery is deferred until the manager is opened.
    elseif event == "ADDON_LOADED" and SVC.loggedIn then
        SVC.Compat:NextFrame(function() SVC:VerifyPending() end)
    elseif event == "PLAYER_LOGOUT" and #SVC.pending > 0 and not SVC.reloading then
        print("SVCleaner: " .. SVC:PendingWarning())
    elseif event == "CVAR_UPDATE" and SVC.activePage == "cvars" and not SVC.cvarRefreshQueued then
        SVC.cvarRefreshQueued = true
        SVC.Compat:NextFrame(function() SVC.cvarRefreshQueued = nil; if SVC.RefreshCVars then SVC:RefreshCVars() end end)
    elseif event == "PLAYER_REGEN_DISABLED" and SVC.frame then
        SVC.frame:Hide()
    end
end)

SLASH_SVCLEANER1, SLASH_SVCLEANER2 = "/svc", "/svcleaner"
SlashCmdList.SVCLEANER = function() SVC:Toggle() end
function SVCleaner_OnAddonCompartmentClick() SVC:Toggle() end
