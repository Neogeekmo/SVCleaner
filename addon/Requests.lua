local ADDON, SVC = ...
local L = SVC.L

function SVC:RequestTarget(request, verifying)
    if type(request) == "table" and request.kind == "cvar" then return self:CVarTarget(request, verifying) end
    if type(request) ~= "table" or type(request.root) ~= "string" or type(request.addon) ~= "string"
        or request.addon == ADDON or request.addon:match("^Blizzard_") or request.root == "SVCleanerDB"
        or (request.scope ~= "account" and request.scope ~= "character") then return nil, L.UNAVAILABLE end
    local api, declared = self.Compat:GetAddOnAPI(), false
    if not api.IsAddOnLoaded or not api.IsAddOnLoaded(request.addon) then return nil, L.NOT_LOADED end
    for _, root in ipairs((self.Manifest[request.addon] or {})[request.scope] or {}) do if root == request.root then declared = true end end
    if api.GetAddOnMetadata then
        local ok, metadata = pcall(api.GetAddOnMetadata, request.addon, request.scope == "account" and "SavedVariables" or "SavedVariablesPerCharacter")
        if ok and type(metadata) == "string" then for root in metadata:gmatch("[%a_][%w_]*") do if root == request.root then declared = true end end end
    end
    local name, realm = self.Compat:PlayerIdentity()
    if not declared or request.scope == "character" and request.character ~= name .. " - " .. realm then return nil, L.UNAVAILABLE end
    local path, parent, key = {}, _G, request.root
    if type(request.path) ~= "table" then return nil, L.UNAVAILABLE end
    for i, item in ipairs(request.path) do
        if type(item) ~= "table" or (item.type ~= "string" and item.type ~= "number" and item.type ~= "boolean") or type(item.value) ~= item.type then return nil, L.UNAVAILABLE end
        path[i] = item.value
    end
    if #path > 0 then
        local parentPath = {}; for i = 1, #path - 1 do parentPath[i] = path[i] end
        parent, key = self:Resolve(request.root, parentPath), path[#path]
    end
    if type(parent) ~= "table" or self:Protected(request.root, path) then return nil, L.UNAVAILABLE end
    return {parent = parent, key = key, old = rawget(parent, key)}
end

function SVC:WriteTarget(target, value)
    if not target.cvar then rawset(target.parent, target.key, value); return true end
    local setter = self.Compat:GetCVarAPI().SetCVar
    if not setter then return false end
    local ok, result = pcall(setter, target.cvar, value)
    local info = self:ReadCVar(target.cvar)
    return ok and result ~= false and info ~= nil and self:CVarMatches(info.value, value)
end

function SVC:PendingWarning()
    for _, request in ipairs(self.pending) do if request.kind == "cvar" then return L.PENDING_WARNING .. "\n\n" .. L.CVAR_HINT end end
    return L.PENDING_WARNING
end

function SVC:Queue(row, path, operation, value)
    if operation ~= "edit" and operation ~= "delete-value" and operation ~= "create" then return false, L.UNAVAILABLE end
    local copied = {}
    for index, key in ipairs(path) do copied[index] = {type = type(key), value = key} end
    local name, realm = self.Compat:PlayerIdentity()
    local request = {addon = row.addon, root = row.root, scope = row.scope, path = copied, character = name .. " - " .. realm}
    local target, err = self:RequestTarget(request)
    if not target then return false, err end
    local old = target.old
    if operation == "create" then
        if old ~= nil or value == nil or self:IsIdentity(path[#path] or row.root, value) then return false, L.CREATE_EXISTS end
        if type(value) ~= "string" and type(value) ~= "number" and type(value) ~= "boolean" and type(value) ~= "table" then return false, L.TYPE_ID end
        if type(value) == "table" and next(value) then return false, L.TYPE_ID end
    elseif old == nil then return false, L.NOT_FOUND end
    if operation == "edit" and ((type(old) ~= "string" and type(old) ~= "number" and type(old) ~= "boolean") or type(old) ~= type(value) or self:IsIdentity(path[#path], value)) then
        return false, L.TYPE_ID
    end
    if type(value) == "number" and (value ~= value or value == math.huge or value == -math.huge) then return false, L.NON_FINITE end
    if operation=="edit" and type(value)=="string" and (#value>32768 or #old>32768) then return false,L.READ_ONLY end
    local ok, snapshot = self:Snapshot(old)
    if not ok then return false, L.READ_ONLY end
    local slot = #self.pending + 1
    for index, request in ipairs(self.pending) do
        local sameOwner = request.addon == row.addon and request.root == row.root and request.scope == row.scope and (row.scope ~= "character" or request.character == name .. " - " .. realm)
        local same = sameOwner and #request.path == #copied
        for i, key in ipairs(copied) do if not request.path[i] or request.path[i].type ~= key.type or request.path[i].value ~= key.value then same = false end end
        if same then slot = index; break end
        if sameOwner then
            local prefix = true
            for i = 1, math.min(#request.path, #copied) do
                if request.path[i].type ~= copied[i].type or request.path[i].value ~= copied[i].value then prefix = false end
            end
            if prefix then return false, L.OVERLAP end
        end
    end
    self.pending[slot] = {addon = row.addon, root = row.root, scope = row.scope, path = copied,
        operation = operation, value = value, expectedType = type(old), expectedValue = type(old) ~= "table" and old or nil,
        character = name .. " - " .. realm, created = time()}
    if type(old) ~= "table" then self.pending[slot].expectedValue = old end
    if type(old) == "table" then self.pending[slot].expectedSnapshot = snapshot end
    SVCleanerDB.requests = self.pending
    return true
end

function SVC:ApplyPending()
    if InCombatLockdown() then return false, L.OUT_COMBAT end
    if #self.pending == 0 then return false, L.EMPTY end
    if type(ReloadUI) ~= "function" then return false, L.API_MISSING end
    local changes = {}
    for _, request in ipairs(self.pending) do
        for _, change in ipairs(changes) do
            local other = change.request
            if other.kind == request.kind and other.root == request.root then
                local prefix = true
                for i = 1, math.min(#other.path, #request.path) do
                    if other.path[i].type ~= request.path[i].type or other.path[i].value ~= request.path[i].value then prefix = false end
                end
                if prefix then return false, L.OVERLAP end
            end
        end
        local target, err = self:RequestTarget(request)
        if not target then return false, err end
        local ok, current = self:Snapshot(target.old)
        local expected = request.expectedValue
        if request.expectedType == "table" then expected = request.expectedSnapshot end
        if not ok or type(current) ~= request.expectedType or not self:Equal(current, expected) then return false, L.CONFLICT end
        if request.operation == "create" then
            if current ~= nil or request.value == nil then return false, L.CONFLICT end
        elseif request.operation == "edit" then
            if type(current) == "table" or type(request.value) ~= type(current) then return false, L.TYPE_ID end
        elseif request.operation ~= "delete-value" then return false, L.UNAVAILABLE end
        if request.operation ~= "delete-value" then
            local valid = self:Snapshot(request.value)
            if not valid or not target.cvar and self:IsIdentity(target.key, request.value) then return false, L.TYPE_ID end
        end
        if target.cvar and (request.operation ~= "edit" or type(request.value) ~= "string" or request.value:find("%z")) then return false, L.CVAR_FAILED end
        changes[#changes + 1] = {target = target, request = request}
    end
    -- SavedVariables use raw assignments; CVar writes are checked by reading them back.
    local applied = {}
    local function rollback()
        local restored = true
        for i = #applied, 1, -1 do
            local change = applied[i]
            if not self:WriteTarget(change.target, change.target.old) then restored = false end
            change.request.verify, change.request.status = nil, nil
        end
        return restored
    end
    for _, change in ipairs(changes) do
        local value = change.request.value
        if type(value) == "table" then local _, copied = self:Snapshot(value); value = copied end
        if change.request.operation == "delete-value" then value = nil end
        applied[#applied + 1] = change
        if not self:WriteTarget(change.target, value) then
            local restored = rollback()
            return false, restored and L.CVAR_FAILED or L.ROLLBACK_FAILED
        end
        change.request.verify, change.request.status = true, "awaiting-reload"
    end
    self.reloading = true
    local ok = pcall(ReloadUI)
    if not ok then
        self.reloading = nil
        local restored = rollback()
        return false, restored and L.RELOAD_FAILED or L.ROLLBACK_FAILED
    end
    return true
end

function SVC:VerifyPending()
    local remaining, checked, failed = {}, 0, 0
    SVCleanerDB.lastApplication = SVCleanerDB.lastApplication or {}
    for _, request in ipairs(self.pending) do
        if request.verify then
            local target, err = self:RequestTarget(request, true)
            local name, realm = self.Compat:PlayerIdentity()
            local deferred = err == L.NOT_LOADED or (request.scope == "character" or request.kind == "cvar") and request.character ~= name .. " - " .. realm
            if not deferred then
                local ok, current = false, nil
                if target then ok, current = self:Snapshot(target.old) end
                local desired = request.value
                if request.operation == "delete-value" then desired = nil end
                local matched = ok and (request.kind == "cvar" and self:CVarMatches(current, desired) or self:Equal(current, desired))
                request.verify, request.status = nil, matched and "verified" or "mismatch"
                checked = checked + 1
                if not matched then failed = failed + 1 end
                -- Keep a compact result, not a second copy of a deleted database.
                local before = request.expectedValue
                if request.expectedType == "table" then before = request.expectedSnapshot end
                table.insert(SVCleanerDB.lastApplication, 1, {addon = request.addon, root = request.root, path = request.path,
                    operation = request.operation, kind = request.kind, status = request.status, checked = time(),
                    before = self:Preview(before), desired = self:Preview(desired), observed = ok and self:Preview(current) or L.UNAVAILABLE})
                if #SVCleanerDB.lastApplication > 100 then table.remove(SVCleanerDB.lastApplication) end
                if not matched then remaining[#remaining + 1] = request end
            else request.status = "deferred"; remaining[#remaining + 1] = request end
        else remaining[#remaining + 1] = request end
    end
    self.pending, SVCleanerDB.requests = remaining, remaining
    if checked > 0 then
        self.applicationNotice = string.format(L.VERIFY_RESULT, checked - failed, failed)
        print("SVCleaner: " .. self.applicationNotice)
    end
    if self.frame then
        self:Refresh()
        if self.activePage == "requests" then self:ShowPage("requests")
        elseif self.activePage == "compare" then self:RefreshDiff() end
    end
end
