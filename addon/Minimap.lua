local _, SVC = ...
local L = SVC.L

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
