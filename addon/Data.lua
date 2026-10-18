local _, SVC = ...
local L = SVC.L

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

function SVC:FormatBytes(bytes)
    if bytes >= 1048576 then return string.format("%.2f MiB", bytes / 1048576) end
    if bytes >= 1024 then return string.format("%.1f KiB", bytes / 1024) end
    return tostring(bytes) .. " B"
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

-- Literal snapshots also let the companion check table deletions without executing Lua.
function SVC:Snapshot(value)
    local seen, nodes = {}, 0
    local function copy(item, depth)
        nodes = nodes + 1
        if nodes > 40000 or depth > 50 or issecretvalue and issecretvalue(item) then error(L.READ_ONLY) end
        local typ = type(item)
        if typ == "number" and (item ~= item or item == math.huge or item == -math.huge) then error(L.NON_FINITE) end
        if typ == "string" and #item > 32768 then error(L.READ_ONLY) end
        if typ ~= "table" then
            if typ ~= "nil" and typ ~= "string" and typ ~= "number" and typ ~= "boolean" then error(L.READ_ONLY) end
            return item
        end
        if seen[item] then error(L.READ_ONLY) end
        seen[item] = true
        local result = {}
        for key, child in pairs(item) do
            if type(key) ~= "string" and type(key) ~= "number" and type(key) ~= "boolean" then error(L.READ_ONLY) end
            result[copy(key, depth + 1)] = copy(child, depth + 1)
        end
        seen[item] = nil
        return result
    end
    return pcall(copy, value, 0)
end

function SVC:Equal(a, b)
    if type(a) ~= type(b) then return false end
    if type(a) ~= "table" then return a == b end
    for key, value in pairs(a) do if not self:Equal(value, rawget(b, key)) then return false end end
    for key in pairs(b) do if rawget(a, key) == nil then return false end end
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
