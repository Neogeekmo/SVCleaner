local _, SVC = ...
local CURRENT_SCHEMA = 2

-- Each migration runs once, in order. Never downgrade or replace saved data
-- from a newer addon, and retain existing request/snapshot table identities.
local migrations = {
    [1] = function(db)
        db.characters = db.characters or {}
        db.requests = db.requests or {}
        if db.theme ~= "dark" and db.theme ~= "light" then db.theme = "dark" end
    end,
    [2] = function(db)
        db.lastApplication = db.lastApplication or {}
        db.minimap = db.minimap or {}
        db.geometry = db.geometry or {}
    end,
}

local function finite(value)
    return type(value) == "number" and value == value and value ~= math.huge and value ~= -math.huge
end

function SVC:InitializeDatabase()
    local db = SVCleanerDB
    if db == nil then db = {} end
    if type(db) ~= "table" then return false end
    local version = db.schema
    if version == nil then version = 0 end
    if not finite(version) or version < 0 or version > CURRENT_SCHEMA or version % 1 ~= 0 then return false end
    -- Validate before mutating anything. A malformed container is not discarded.
    for _, field in ipairs({"characters", "requests", "lastApplication", "minimap", "geometry"}) do
        if db[field] ~= nil and type(db[field]) ~= "table" then return false end
    end
    for nextVersion = version + 1, CURRENT_SCHEMA do
        migrations[nextVersion](db)
        db.schema = nextVersion
    end
    -- Optional settings can be absent even in a current database.
    for _, field in ipairs({"characters", "requests", "lastApplication", "minimap", "geometry"}) do
        db[field] = db[field] or {}
    end
    if db.theme ~= "dark" and db.theme ~= "light" then db.theme = "dark" end
    if not finite(db.minimap.angle) then db.minimap.angle = 225 end
    db.minimap.angle = db.minimap.angle % 360
    for _, dimension in ipairs({"width", "height"}) do
        if not finite(db.geometry[dimension]) or db.geometry[dimension] <= 0 then db.geometry[dimension] = nil end
    end
    SVCleanerDB = db
    self.pending = db.requests
    return true
end
