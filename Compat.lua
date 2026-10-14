local _, SVC = ...
SVC.Compat = {}
local fold = {}
local chars = {}; for char in ("ÀàÁáÂâÃãÄäÅåÆæÇçÈèÉéÊêËëÌìÍíÎîÏïÐðÑñÒòÓóÔôÕõÖöØøÙùÚúÛûÜüÝýÞþŸÿẞßАаБбВвГгДдЕеЁёЖжЗзИиЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЪъЫыЬьЭэЮюЯя"):gmatch("[\194-\244][\128-\191]*") do chars[#chars+1]=char end
for i=1,#chars,2 do fold[chars[i]]=chars[i+1] end
function SVC:Fold(value) return (tostring(value or ""):gsub("[A-Z]",function(char) return char:lower() end):gsub("[\194-\244][\128-\191]*",fold)) end

-- Resolve each member independently: a namespace can exist while a client still
-- exposes some functions through the legacy global API.
function SVC.Compat:GetAddOnAPI()
    local api = {}
    for _, name in ipairs({"GetNumAddOns", "GetAddOnInfo", "GetAddOnMetadata", "IsAddOnLoaded"}) do
        local modern = C_AddOns and C_AddOns[name]
        api[name] = type(modern) == "function" and modern or type(_G[name]) == "function" and _G[name] or nil
    end
    return api
end

function SVC.Compat:PlayerIdentity()
    local name, realm
    if type(UnitFullName) == "function" then name, realm = UnitFullName("player") end
    if not name and type(UnitName) == "function" then name, realm = UnitName("player") end
    if not realm or realm == "" then realm = type(GetRealmName) == "function" and GetRealmName() or "?" end
    return name or "?", realm
end

function SVC.Compat:BackdropTemplate()
    return BackdropTemplateMixin and "BackdropTemplate" or nil
end

function SVC.Compat:NextFrame(callback)
    if C_Timer and type(C_Timer.After) == "function" then C_Timer.After(0, callback); return end
    local frame = CreateFrame("Frame")
    frame:SetScript("OnUpdate", function(self)
        self:SetScript("OnUpdate", nil)
        self:Hide()
        callback()
    end)
end
