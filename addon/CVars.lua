local ADDON, SVC = ...
local L = SVC.L

function SVC:ReadCVar(name)
    if type(name) ~= "string" or not name:match("^[%w_]+$") then return nil end
    local api = self.Compat:GetCVarAPI()
    if not api.GetCVar then return nil end
    local ok, value = pcall(api.GetCVar, name)
    if not ok or type(value) ~= "string" or issecretvalue and issecretvalue(value) then return nil end
    local default, locked, secure, readOnly
    if api.GetCVarInfo then
        local info, _, def, _, _, lock, sec, ro = pcall(api.GetCVarInfo, name)
        if info then default, locked, secure, readOnly = def, lock, sec, ro end
    end
    if default == nil and api.GetCVarDefault then local got, def = pcall(api.GetCVarDefault, name); if got then default = def end end
    return {name = name, value = value, default = default, readOnly = not api.SetCVar or not not (locked or secure or readOnly)}
end

function SVC:CVarTarget(request, verifying)
    local name, realm = self.Compat:PlayerIdentity()
    if request.character ~= name .. " - " .. realm then return nil, L.UNAVAILABLE end
    local info = self:ReadCVar(request.root)
    if not info or info.readOnly and not verifying then return nil, L.CVAR_LOCKED end
    return {cvar = request.root, old = info.value, key = request.root}
end

function SVC:QueueCVar(name, value)
    if type(value) ~= "string" or #value > 32768 or value:find("%z") then return false, L.CVAR_FAILED end
    local info = self:ReadCVar(name)
    if not info or info.readOnly then return false, L.CVAR_LOCKED end
    local player, realm = self.Compat:PlayerIdentity()
    local slot = #self.pending + 1
    for i, request in ipairs(self.pending) do
        if request.kind == "cvar" and request.root:lower() == name:lower() and request.character == player .. " - " .. realm then slot = i; break end
    end
    self.pending[slot] = {kind = "cvar", addon = ADDON, root = name, scope = "cvar", path = {}, operation = "edit",
        value = value, expectedType = "string", expectedValue = info.value, character = player .. " - " .. realm, created = time()}
    SVCleanerDB.requests = self.pending
    return true
end

function SVC:CVarMatches(actual, desired)
    if actual == desired then return true end
    local a, b = tonumber(actual), tonumber(desired)
    return a ~= nil and b ~= nil and a == b
end
