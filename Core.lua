local ADDON, SVC = ...
local L = SVC.L
SVC.name = ADDON
SVC.rows, SVC.pending = {}, {}

local identityNames = {id = true, guid = true, playerid = true, characterid = true, userid = true,
    playerguid = true, characterguid = true, realm = true, realmname = true, servername = true,
    playername = true, charactername = true, name = true, key = true, profilekey = true}

function SVC:IsIdentity(key, value)
    if type(key) == "string" then
        local lower = key:lower()
        local characterKey=key:match("%-Player%-%d+%-%x+$")
        local guidField=not characterKey and (lower:match("guids?$") or lower:match("^guids?[_%p]") or lower:match("[_%p]guids?[_%p]") or key:match("[Gg][Uu][Ii][Dd][A-Z_]"))
        if identityNames[lower] or key:match("ID$") or key:match("Id$") or lower:match("_id$") or guidField then return true end
    end
    return type(value) == "string" and value:find("Player%-%d+%-%x+") ~= nil
end

function SVC:Keys(value)
    local keys = {}
    if type(value) ~= "table" then return keys end
    for key in pairs(value) do
        if (type(key) == "string" or type(key) == "number" or type(key) == "boolean") and (not issecretvalue or not issecretvalue(key)) then keys[#keys + 1] = key end
    end
    table.sort(keys, function(a, b)
        if type(a) == type(b) and type(a) == "number" then return a < b end
        return type(a) .. tostring(a) < type(b) .. tostring(b)
    end)
    return keys
end

function SVC:Preview(value)
    if issecretvalue and issecretvalue(value) then return L.RESTRICTED end
    if type(value) == "table" then
        local count=0; for _ in pairs(value) do count=count+1; if count>=10000 then break end end
        return (count>=10000 and ">= " or "") .. string.format(L.TABLE_KEYS,count)
    end
    return tostring(value)
end

function SVC:Estimate(value)
    local seen, nodes, truncated = {}, 0, false
    local function measure(item, depth)
        nodes = nodes + 1
        if nodes > 40000 or depth > 50 then truncated = true; return 0 end
        if issecretvalue and issecretvalue(item) then truncated = true; return 0 end
        if type(item) == "string" then return #string.format("%q", item) end
        if type(item) ~= "table" then return #tostring(item) end
        if seen[item] then truncated = true; return 0 end
        seen[item] = true
        local bytes = 2
        for key, child in pairs(item) do
            if nodes > 40000 then truncated = true; break end
            bytes = bytes + measure(key, depth + 1) + measure(child, depth + 1) + 7
        end
        seen[item] = nil
        return bytes
    end
    return measure(value, 0), truncated
end

function SVC:FormatBytes(bytes)
    if bytes >= 1048576 then return string.format("%.2f MiB", bytes / 1048576) end
    if bytes >= 1024 then return string.format("%.1f KiB", bytes / 1024) end
    return tostring(bytes) .. " B"
end

function SVC:Discover()
    self.rows = {}
    local api = self.Compat:GetAddOnAPI()
    if not api.GetNumAddOns or not api.GetAddOnInfo or not api.IsAddOnLoaded then
        print("SVCleaner: " .. L.API_MISSING)
        return
    end
    local count = api.GetNumAddOns()
    for index = 1, count do
        local name, title = api.GetAddOnInfo(index)
        if name and name ~= ADDON and not name:match("^Blizzard_") then
            local manifest = self.Manifest[name] or {}
            local seen = {}
            for _, scope in ipairs({"account", "character"}) do
                local declarations = {}
                for _, root in ipairs(manifest[scope] or {}) do declarations[#declarations + 1] = root end
                -- Some clients/addons expose the directive; a generated manifest is the reliable fallback.
                local field = scope == "account" and "SavedVariables" or "SavedVariablesPerCharacter"
                local ok, metadata = pcall(api.GetAddOnMetadata, name, field)
                if ok and type(metadata) == "string" then
                    for root in metadata:gmatch("[%a_][%w_]*") do declarations[#declarations + 1] = root end
                end
                for _, root in ipairs(declarations) do
                    if not seen[root] then
                        seen[root] = true
                        local value = rawget(_G, root)
                        local loaded = api.IsAddOnLoaded(name)
                        self.rows[#self.rows + 1] = {addon = name, title = title or name, root = root, scope = scope,
                            value = value, loaded = loaded, available = loaded and value ~= nil, bytes = 0}
                    end
                end
                if not manifest[scope] and #declarations == 0 and scope == "account" then
                    self.rows[#self.rows + 1] = {addon = name, title = title or name, root = L.MANIFEST, loaded = api.IsAddOnLoaded(name), unavailable = true, bytes = 0}
                end
            end
        end
    end
    table.sort(self.rows, function(a, b) return a.addon .. a.root < b.addon .. b.root end)
    -- Spread estimates across frames so opening the window does not scan every large DB at once.
    local generation = (self.generation or 0) + 1
    self.generation = generation
    local index = 1
    local function nextEstimate()
        if self.generation ~= generation then return end
        local row = self.rows[index]
        if not row then if self.Refresh then self:Refresh() end; return end
        if row.available then row.bytes, row.truncated = self:Estimate(row.value) end
        index = index + 1
        self.Compat:NextFrame(nextEstimate)
    end
    nextEstimate()
end

function SVC:Resolve(root, path)
    local value = rawget(_G, root)
    for _, key in ipairs(path or {}) do
        if type(value) ~= "table" then return nil end
        value = rawget(value, key)
    end
    return value
end

function SVC:Protected(root, path)
    local value = rawget(_G, root)
    if self:IsIdentity(root,value) then return true end
    for _, key in ipairs(path or {}) do
        if type(value) ~= "table" then return true end
        value = rawget(value, key)
        if issecretvalue and issecretvalue(value) then return true end
        if self:IsIdentity(key, value) then return true end
    end
    return false
end

function SVC:CharacterLabel(key)
    if type(key) ~= "string" then return nil end
    local guid = key:match("(Player%-%d+%-%x+)$")
    if guid then
        local known = SVCleanerDB.characters[guid]
        return key .. " · " .. (known and L.OBSERVED or L.UNOBSERVED)
    end
    local container=self.path and self.path[#self.path]
    if (container=="char" or container=="profileKeys") and key:find(" - ",1,true) then return key.." · "..L.UNOBSERVED end
end

function SVC:Queue(row, path, operation, value)
    if not row.available or self:Protected(row.root, path) then return false, L.UNAVAILABLE end
    local old = self:Resolve(row.root, path)
    if old == nil then return false, L.NOT_FOUND end
    if operation == "edit" and ((type(old) ~= "string" and type(old) ~= "number" and type(old) ~= "boolean") or type(old) ~= type(value) or self:IsIdentity(path[#path], value)) then
        return false, L.TYPE_ID
    end
    if type(value) == "number" and (value ~= value or value == math.huge or value == -math.huge) then return false, L.NON_FINITE end
    if operation=="edit" and type(value)=="string" and (#value>32768 or #old>32768) then return false,L.READ_ONLY end
    local copied = {}
    for index, key in ipairs(path) do copied[index] = {type = type(key), value = key} end
    local name, realm = self.Compat:PlayerIdentity()
    local slot = #self.pending + 1
    for index, request in ipairs(self.pending) do
        local same = request.addon == row.addon and request.root == row.root and request.scope == row.scope and #request.path == #copied
        for i, key in ipairs(copied) do if not request.path[i] or request.path[i].type ~= key.type or request.path[i].value ~= key.value then same = false end end
        if same then slot = index; break end
    end
    self.pending[slot] = {addon = row.addon, root = row.root, scope = row.scope, path = copied,
        operation = operation, value = value, expectedType = type(old), expectedValue = type(old) ~= "table" and old or nil,
        character = name .. " - " .. realm, created = time()}
    if type(old) ~= "table" then self.pending[slot].expectedValue = old end
    SVCleanerDB.requests = self.pending
    return true
end

function SVC:Diff(left, right)
    local rows, visited, limited, nodes = {}, {}, false, 0
    local function walk(a, b, path, protected, depth)
        nodes = nodes + 1
        if #rows >= 1000 or depth > 30 or nodes > 50000 then limited = true; return end
        if issecretvalue and (issecretvalue(a) or issecretvalue(b)) then return end
        if type(a) == "table" and type(b) == "table" then
            if visited[a] or visited[b] then limited = true; return end
            visited[a], visited[b] = true, true
            local keys = self:Keys(a)
            for _, key in ipairs(self:Keys(b)) do if rawget(a, key) == nil then keys[#keys + 1] = key end end
            for _, key in ipairs(keys) do
                local child = {}
                for i, item in ipairs(path) do child[i] = item end
                child[#child + 1] = key
                walk(rawget(a, key), rawget(b, key), child, protected or self:IsIdentity(key, rawget(a, key)) or self:IsIdentity(key, rawget(b, key)), depth + 1)
                if limited then break end
            end
            visited[a], visited[b] = nil, nil
        elseif (not issecretvalue or not issecretvalue(a) and not issecretvalue(b)) and a ~= b then
            local large=type(a)=="string" and #a>32768 or type(b)=="string" and #b>32768
            rows[#rows + 1] = {path = path, left = a, right = b, protected = protected, large=large,
                copyable = not large and not protected and a ~= nil and b ~= nil and type(a) == type(b) and (type(a) == "string" or type(a) == "number" or type(a) == "boolean")}
        end
    end
    walk(left, right, {}, false, 0)
    return rows, limited
end

function SVC:PositionMinimapButton()
    if not self.minimapButton or not Minimap then return end
    local angle=math.rad(SVCleanerDB.minimap.angle)
    local x,y=math.cos(angle),math.sin(angle)
    local shape=GetMinimapShape and GetMinimapShape() or "ROUND"
    local corner=(y>0 and "TOP" or "BOTTOM")..(x<0 and "LEFT" or "RIGHT")
    local round=shape~="SQUARE"
    if shape:match("^CORNER%-") then round=shape=="CORNER-"..corner
    elseif shape:match("^TRICORNER%-") then round=shape~="TRICORNER-"..corner
    elseif shape:match("^SIDE%-") then round=corner:find(shape:sub(6),1,true)~=nil end
    if not round then local divisor=math.max(math.abs(x),math.abs(y)); x,y=x/divisor,y/divisor end
    self.minimapButton:ClearAllPoints()
    self.minimapButton:SetPoint("CENTER",Minimap,"CENTER",x*(Minimap:GetWidth()/2+8),y*(Minimap:GetHeight()/2+8))
end

function SVC:CreateMinimapButton()
    if not Minimap then return end
    if type(SVCleanerDB.minimap)~="table" then SVCleanerDB.minimap={} end
    local angle=SVCleanerDB.minimap.angle
    if type(angle)~="number" or angle~=angle or angle==math.huge or angle==-math.huge then SVCleanerDB.minimap.angle=225 else SVCleanerDB.minimap.angle=angle%360 end
    if self.minimapButton then self:PositionMinimapButton(); return end
    local button=CreateFrame("Button","SVCleanerMinimapButton",Minimap); self.minimapButton=button
    button:SetSize(32,32); button:SetFrameLevel(Minimap:GetFrameLevel()+5)
    button:SetClampedToScreen(true); button:RegisterForClicks("LeftButtonUp"); button:RegisterForDrag("LeftButton")
    button:SetHighlightTexture("Interface\\Minimap\\UI-Minimap-ZoomButton-Highlight")
    local icon=button:CreateTexture(nil,"ARTWORK"); button.icon=icon
    icon:SetTexture("Interface\\AddOns\\SVCleaner\\Assets\\logo.tga"); icon:SetSize(26,26); icon:SetPoint("CENTER",0,0)
    local border=button:CreateTexture(nil,"OVERLAY"); border:SetTexture("Interface\\Minimap\\MiniMap-TrackingBorder"); border:SetSize(53,53); border:SetPoint("TOPLEFT",0,0)
    button:SetScript("OnClick",function(self) if not self.dragged then SVC:Toggle() end end)
    button:SetScript("OnMouseDown",function(self) self.dragged=false end)
    button:SetScript("OnEnter",function(self)
        GameTooltip:SetOwner(self,"ANCHOR_LEFT"); GameTooltip:SetText("SV Cleaner")
        GameTooltip:AddLine(L.MINIMAP_OPEN,1,1,1); GameTooltip:AddLine(L.MINIMAP_MOVE,.65,.65,.65); GameTooltip:Show()
    end)
    button:SetScript("OnLeave",function() GameTooltip:Hide() end)
    button:SetScript("OnDragStart",function(self)
        self.dragged=true; GameTooltip:Hide()
        self:SetScript("OnUpdate",function()
            local mx,my=Minimap:GetCenter(); local cx,cy=GetCursorPosition(); local scale=Minimap:GetEffectiveScale()
            if mx and my and scale and scale>0 then
                SVCleanerDB.minimap.angle=math.deg(math.atan2(cy/scale-my,cx/scale-mx))%360; SVC:PositionMinimapButton()
            end
        end)
    end)
    button:SetScript("OnDragStop",function(self) self:SetScript("OnUpdate",nil) end)
    button:SetScript("OnHide",function(self) self:SetScript("OnUpdate",nil); GameTooltip:Hide() end)
    self:PositionMinimapButton()
end

local events = CreateFrame("Frame")
events:RegisterEvent("ADDON_LOADED")
events:RegisterEvent("PLAYER_LOGIN")
events:RegisterEvent("PLAYER_REGEN_DISABLED")
events:SetScript("OnEvent", function(_, event, name)
    if event == "ADDON_LOADED" and name == ADDON then
        SVCleanerDB = SVCleanerDB or {}
        SVCleanerDB.schema = 1
        if SVCleanerDB.theme ~= "dark" and SVCleanerDB.theme ~= "light" then SVCleanerDB.theme = "dark" end
        SVCleanerDB.characters = SVCleanerDB.characters or {}
        SVCleanerDB.requests = SVCleanerDB.requests or {}
        SVC.pending = SVCleanerDB.requests
    elseif event == "PLAYER_LOGIN" then
        local guid = UnitGUID("player")
        local playerName, realm = SVC.Compat:PlayerIdentity()
        if guid then SVCleanerDB.characters[guid] = {name = playerName, realm = realm, lastSeen = time()} end
        SVC:CreateMinimapButton()
        -- Discovery is deferred until the manager is opened.
    elseif event == "PLAYER_REGEN_DISABLED" and SVC.frame then
        SVC.frame:Hide()
    end
end)

SLASH_SVCLEANER1, SLASH_SVCLEANER2 = "/svc", "/svcleaner"
SlashCmdList.SVCLEANER = function() SVC:Toggle() end
function SVCleaner_OnAddonCompartmentClick() SVC:Toggle() end
