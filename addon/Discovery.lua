local ADDON, SVC = ...
local L = SVC.L

function SVC:Estimate(value, checkpoint)
    local seen, nodes, truncated = {}, 0, false
    local function measure(item, depth)
        nodes = nodes + 1
        if checkpoint and nodes % 512 == 0 then checkpoint() end
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

function SVC:Discover()
    local generation = (self.generation or 0) + 1
    self.generation = generation
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
    -- Yield within a large database, not just between databases. A new scan
    -- invalidates every pending callback from the previous generation.
    local index, task = 1, nil
    local function nextEstimate()
        if self.generation ~= generation then return end
        local row = self.rows[index]
        if not row then if self.Refresh then self:Refresh() end; return end
        if row.available then
            if not task then task = coroutine.create(function() return self:Estimate(row.value, coroutine.yield) end) end
            local ok, bytes, truncated = coroutine.resume(task)
            if ok and coroutine.status(task) ~= "dead" then
                self.Compat:NextFrame(nextEstimate)
                return
            end
            -- Another addon may remove the current iteration key between
            -- frames. An interrupted estimate is explicitly incomplete.
            row.bytes, row.truncated = ok and bytes or 0, not ok or truncated
            task = nil
        end
        index = index + 1
        self.Compat:NextFrame(nextEstimate)
    end
    nextEstimate()
end
