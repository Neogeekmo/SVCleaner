-- Select the WoW client language, with English fallback.
local _, SVC = ...
SVC.locale = GetLocale()
SVC.L = setmetatable({}, {__index = function(_, key) return (SVC.Locales[SVC.locale] or SVC.Locales.enUS)[key] or SVC.Locales.enUS[key] or key end})
SVC.font = STANDARD_TEXT_FONT or (GameFontNormal and select(1, GameFontNormal:GetFont())) or "Fonts\\FRIZQT__.TTF"
