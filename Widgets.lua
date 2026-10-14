local _, SVC = ...
local L, UI = SVC.L, {regions = {}}
SVC.UI = UI
local palettes = {
    dark = {window={.035,.035,.045,1},panel={.067,.065,.075,1},raised={.12,.115,.13,1},text={.93,.92,.91,1},muted={.64,.62,.66,1},border={.22,.21,.25,1},accent={.94,.75,.32,1},danger={.94,.43,.40,1},left={.38,.70,.90,1},right={.48,.80,.62,1}},
    light = {window={.94,.93,.90,1},panel={.99,.985,.97,1},raised={.89,.88,.85,1},text={.16,.15,.18,1},muted={.40,.38,.42,1},border={.75,.73,.70,1},accent={.55,.35,.06,1},danger={.73,.22,.20,1},left={.13,.40,.60,1},right={.15,.43,.27,1}}
}
function UI:Display(value,limit)
    local text=tostring(value or ""); limit=limit or 500
    if #text>limit then
        local cut=limit+1
        while cut>1 and text:byte(cut)>=128 and text:byte(cut)<192 do cut=cut-1 end
        text=text:sub(1,cut-1).."..."
    end
    return text:gsub("|","||")
end
function UI:Color(region, role, kind)
    local entry = {region,role,kind}; self.regions[#self.regions+1] = entry; self:Apply(entry)
end
function UI:Apply(entry)
    local color = palettes[SVCleanerDB and SVCleanerDB.theme or "dark"][entry[2]]
    local r, kind = entry[1],entry[3]
    if kind=="text" then r:SetTextColor(unpack(color))
    elseif kind=="border" then r:SetBackdropBorderColor(unpack(color))
    elseif kind=="backdrop" then r:SetBackdropColor(unpack(color))
    elseif kind=="vertex" then r:SetVertexColor(unpack(color))
    else r:SetColorTexture(unpack(color)) end
end
function UI:Theme() for _,entry in ipairs(self.regions) do self:Apply(entry) end end
function UI:Panel(parent,role)
    local f=CreateFrame("Frame",nil,parent,SVC.Compat:BackdropTemplate())
    f:SetBackdrop({bgFile="Interface\\Buttons\\WHITE8X8",edgeFile="Interface\\Buttons\\WHITE8X8",edgeSize=1})
    self:Color(f,role or "panel","backdrop"); self:Color(f,"border","border")
    return f
end
function UI:Text(parent,text,size,role)
    local f=parent:CreateFontString(nil,"OVERLAY")
    f:SetFont(SVC.font,size or 12,""); f:SetText(text or ""); f:SetJustifyH("LEFT"); f:SetJustifyV("TOP")
    self:Color(f,role or "text","text"); return f
end
function UI:Tooltip(target,text)
    target:SetScript("OnEnter",function() GameTooltip:SetOwner(target,"ANCHOR_RIGHT"); GameTooltip:SetText(type(text)=="function" and text() or text,nil,nil,nil,nil,true); GameTooltip:Show() end)
    target:SetScript("OnLeave",function() GameTooltip:Hide() end)
end
function UI:Button(parent,text,width,callback,role)
    local b=CreateFrame("Button",nil,parent,SVC.Compat:BackdropTemplate()); b:SetSize(width or 100,26)
    b:SetBackdrop({bgFile="Interface\\Buttons\\WHITE8X8",edgeFile="Interface\\Buttons\\WHITE8X8",edgeSize=1})
    self:Color(b,"raised","backdrop"); self:Color(b,"border","border")
    b.label=self:Text(b,text,12,role); b.label:SetPoint("LEFT",8,0); b.label:SetPoint("RIGHT",-8,0); b.label:SetJustifyH("CENTER"); b.label:SetJustifyV("MIDDLE"); b.label:SetWordWrap(false)
    b:SetScript("OnClick",callback); b:SetScript("OnEnable",function() b.label:SetAlpha(1); if b.icon then b.icon:SetAlpha(1) end end); b:SetScript("OnDisable",function() b.label:SetAlpha(.4); if b.icon then b.icon:SetAlpha(.4) end end)
    local hi=b:CreateTexture(nil,"HIGHLIGHT"); hi:SetAllPoints(); hi:SetColorTexture(1,.8,.3,.10)
    self:Tooltip(b,text); return b
end
function UI:Icon(parent,id,size)
    local icon=parent:CreateTexture(nil,"ARTWORK"); icon:SetSize(size or 16,size or 16)
    icon:SetTexture("Interface\\AddOns\\SVCleaner\\Assets\\icons.tga"); icon:SetTexCoord(id/8,(id+1)/8,0,1)
    self:Color(icon,"text","vertex")
    return icon
end
function UI:IconButton(parent,id,tooltip,callback)
    local button=self:Button(parent,"",26,callback); button.icon=self:Icon(button,id); button.icon:SetPoint("CENTER")
    self:Tooltip(button,tooltip); return button
end
function UI:Active(button,active) button:SetBackdropBorderColor(unpack(palettes[SVCleanerDB.theme][active and "accent" or "border"])) end
function UI:Input(parent,width,text,callback)
    local e=CreateFrame("EditBox",nil,parent,SVC.Compat:BackdropTemplate()); e:SetSize(width,32)
    e:SetBackdrop({bgFile="Interface\\Buttons\\WHITE8X8",edgeFile="Interface\\Buttons\\WHITE8X8",edgeSize=1})
    self:Color(e,"panel","backdrop"); self:Color(e,"border","border"); self:Color(e,"text","text")
    e:SetFont(SVC.font,12,""); e:SetTextInsets(9,9,4,4); e:SetAutoFocus(false); e:SetMaxLetters(32768); e:SetText(text or "")
    e:SetScript("OnEscapePressed",function(self) self:ClearFocus() end)
    e.placeholder=self:Text(e,L.SEARCH,11,"muted"); e.placeholder:SetPoint("LEFT",10,0)
    e:SetScript("OnTextChanged",function(self,user)
        self.placeholder:SetShown(self:GetText()=="")
        if callback and user then
            self.searchGeneration=(self.searchGeneration or 0)+1; local generation=self.searchGeneration
            local function run() if self.searchGeneration==generation then callback(self:GetText()) end end
            if C_Timer and C_Timer.After then C_Timer.After(.15,run) else SVC.Compat:NextFrame(run) end
        end
    end)
    e.placeholder:SetShown((text or "")==""); return e
end
function UI:List(parent,width,height,bind,rowHeight)
    local list=self:Panel(parent); list:SetSize(width,height); list.items,list.rows,list.offset={}, {},0
    list.rowHeight=rowHeight or 38; list.bind=bind
    local scroll=CreateFrame("Slider",nil,list); list.scroll=scroll; scroll:SetWidth(9); scroll:SetPoint("TOPRIGHT",-4,-6); scroll:SetPoint("BOTTOMRIGHT",-4,6)
    scroll:SetOrientation("VERTICAL"); scroll:SetValueStep(1)
    local thumb=scroll:CreateTexture(nil,"ARTWORK"); thumb:SetSize(7,25); self:Color(thumb,"border"); scroll:SetThumbTexture(thumb)
    function list:Render()
        if self.rendering then return end; self.rendering=true
        local inset=self.topInset or 6
        local count=math.min(80,math.max(1,math.floor((self:GetHeight()-inset-6)/self.rowHeight)))
        self.offset=math.max(0,math.min(self.offset,math.max(0,#self.items-count)))
        for index=1,count do
            if not self.rows[index] then
                local row=CreateFrame("Button",nil,self); row.text=UI:Text(row,"",12); row.detail=UI:Text(row,"",10,"muted")
                row.text:SetPoint("TOPLEFT",10,-8); row.text:SetPoint("TOPRIGHT",-10,-8); row.text:SetWordWrap(false)
                row.detail:SetPoint("BOTTOMLEFT",10,6); row.detail:SetPoint("BOTTOMRIGHT",-10,6); row.detail:SetWordWrap(false)
                row.fill=row:CreateTexture(nil,"BACKGROUND"); row.fill:SetAllPoints(); UI:Color(row.fill,"raised"); row.fill:Hide()
                local hi=row:CreateTexture(nil,"HIGHLIGHT"); hi:SetAllPoints(); hi:SetColorTexture(1,.8,.3,.09)
                self.rows[index]=row
            end
            local row=self.rows[index]; row:SetPoint("TOPLEFT",5,-inset-(index-1)*self.rowHeight); row:SetSize(self:GetWidth()-24,self.rowHeight)
            local item=self.items[index+self.offset]; row:SetShown(item~=nil); row.item=item
            if item then self.bind(row,item); row.fill:SetShown(self.selected==item or self.selected==item.key) end
        end
        for index=count+1,#self.rows do self.rows[index]:Hide() end
        self.scroll:SetMinMaxValues(0,math.max(0,#self.items-count)); self.scroll:SetValue(self.offset); self.scroll:SetShown(#self.items>count)
        self.rendering=false
    end
    function list:SetItems(items,keep) self.items=items or {}; if not keep then self.offset=0 end; self:Render() end
    list:EnableMouseWheel(true); list:SetScript("OnMouseWheel",function(self,delta) self.offset=self.offset-delta*3; self:Render() end)
    scroll:SetScript("OnValueChanged",function(_,value) if not list.rendering then list.offset=math.floor(value+.5); list:Render() end end)
    list:SetScript("OnSizeChanged",function(self) self:Render() end); return list
end
-- One virtualized row per record, with values aligned under real column headers.
function UI:Grid(parent,columns,bind)
    local grid=self:List(parent,700,400,function(row,item)
        row.text:Hide(); row.detail:Hide()
        if not row.cells then
            row.cells={}
            for i,column in ipairs(columns) do
                local cell=UI:Text(row,"",12,column.role); cell:SetWordWrap(false); cell:SetJustifyV("MIDDLE"); row.cells[i]=cell
                if column.icon then row.check=UI:IconButton(row,5,L.COMPARE,function() SVC:MarkComparison(row.item) end) end
            end
            row.line=row:CreateTexture(nil,"BACKGROUND"); UI:Color(row.line,"border"); row.line:SetAlpha(.35); row.line:SetHeight(1); row.line:SetPoint("BOTTOMLEFT"); row.line:SetPoint("BOTTOMRIGHT")
        end
        local x=0
        for i,column in ipairs(columns) do
            local width=row:GetWidth()*column.width; local cell=row.cells[i]
            cell:ClearAllPoints(); cell:SetPoint("LEFT",x+8,0); cell:SetSize(math.max(10,width-16),30)
            if column.icon then row.check:ClearAllPoints(); row.check:SetPoint("LEFT",x,0); row.check:SetSize(24,24) end
            x=x+width
        end
        bind(row,item)
    end,30)
    grid.topInset=30; grid.columns=columns; grid.headings={}
    for i,column in ipairs(columns) do grid.headings[i]=self:Text(grid,column.label or "",11,"muted"); grid.headings[i]:SetWordWrap(false) end
    function grid:LayoutHeaders()
        local x=5
        for i,column in ipairs(self.columns) do
            local width=(self:GetWidth()-24)*column.width; local heading=self.headings[i]
            heading:ClearAllPoints(); heading:SetPoint("TOPLEFT",x+8,-8); heading:SetSize(width-16,18); x=x+width
        end
    end
    grid:SetScript("OnSizeChanged",function(self) self:LayoutHeaders(); self:Render() end); grid:LayoutHeaders()
    return grid
end
function UI:Choice(parent,width,options,value,callback)
    local choice=self:Button(parent,"",width,function() end); choice.options,choice.value=options,value
    function choice:SetOptions(new,value)
        self.options,self.value=new,value; local text=""
        for _,o in ipairs(new) do
            local same=o.value==value
            if type(o.value)=="table" and type(value)=="table" and o.value.row and value.row then
                same=o.value.row.addon==value.row.addon and o.value.row.root==value.row.root and o.value.row.scope==value.row.scope and #o.value.path==#value.path
                for i,key in ipairs(o.value.path) do if value.path[i]~=key or type(value.path[i])~=type(key) then same=false end end
            end
            if same then text=o.label; break end
        end
        self.label:SetText(text)
    end
    choice:SetOptions(options,value)
    choice.label:SetJustifyH("LEFT"); choice.label:SetPoint("RIGHT",-28,0)
    choice.arrow=UI:Icon(choice,1,12); choice.arrow:SetPoint("RIGHT",-8,0)
    UI:Tooltip(choice,function() return choice.label:GetText() end)
    choice:SetScript("OnClick",function()
        local menu=UI.menu
        if menu and menu:IsShown() and menu.choice==choice then menu:Hide(); return end
        if not menu then
            -- A transparent dismissal layer catches clicks anywhere outside the popup.
            local outside=CreateFrame("Button",nil,SVC.frame or parent); UI.menuOutside=outside
            outside:SetAllPoints(UIParent); outside:SetFrameLevel((SVC.frame or parent):GetFrameLevel()+79); outside:EnableMouse(true); outside:Hide()
            menu=UI:Panel(outside); UI.menu=menu; menu:SetFrameLevel((SVC.frame or parent):GetFrameLevel()+80); menu:SetClampedToScreen(true); menu:EnableMouse(true)
            outside:SetScript("OnClick",function() menu:Hide() end)
            menu:SetScript("OnHide",function() outside:Hide(); if menu.search then menu.search:ClearFocus() end end)
            menu.search=UI:Input(menu,260,""); menu.search:SetPoint("TOPLEFT",8,-8)
            menu.close=UI:Button(menu,L.CLOSE,80,function() menu:Hide() end); menu.close:SetPoint("BOTTOMRIGHT",-8,8)
            menu.list=UI:List(menu,260,268,function(row,item)
            row.text:SetText(item.label); row.detail:SetText(item.detail or ""); UI:Tooltip(row,function() return item.label..(item.detail and "\n"..item.detail or "") end)
                row:SetScript("OnClick",function() local c=menu.choice; c:SetOptions(c.options,item.value); menu:Hide(); menu.callback(item.value) end)
            end); menu.list:SetPoint("TOPLEFT",8,-48)
            function menu:Filter(query) local items={}; for _,item in ipairs(self.choice.options) do if SVC:Fold(item.label.." "..(item.detail or "")):find(SVC:Fold(query),1,true) then items[#items+1]=item end end; self.list:SetItems(items) end
            menu.search:SetScript("OnTextChanged",function(self,user) self.placeholder:SetShown(self:GetText()==""); if user then menu:Filter(self:GetText()) end end)
            menu.search:SetScript("OnEscapePressed",function() menu:Hide() end)
        end
        menu:Hide(); menu.choice,menu.callback=choice,callback; menu:ClearAllPoints(); menu:SetPoint("TOPLEFT",choice,"BOTTOMLEFT",0,-3)
        menu:SetSize(math.max(300,width),360); menu.search:SetWidth(menu:GetWidth()-16); menu.list:SetWidth(menu:GetWidth()-16)
        menu.search:SetText(""); menu:Filter(""); UI.menuOutside:Show(); menu:Show()
    end)
    return choice
end
function UI:ReadBox(parent,width,height)
    local box=self:Panel(parent); box:SetSize(width,height)
    local scroll=CreateFrame("ScrollFrame",nil,box); scroll:SetPoint("TOPLEFT",9,-9); scroll:SetPoint("BOTTOMRIGHT",-9,9)
    local child=CreateFrame("Frame",nil,scroll); scroll:SetScrollChild(child); box.child,box.scroll=child,scroll
    local text=self:Text(child,"",12); text:SetPoint("TOPLEFT"); box.text=text
    function box:SetText(value)
        self.fullText=tostring(value or ""); local display=self.fullText
        display=UI:Display(display,32768)
        if #self.fullText>32768 then display=display.."\n\n["..L.COMPANION.."]" end
        self.text:SetWidth(math.max(40,self:GetWidth()-22)); self.text:SetText(display)
        self.child:SetSize(math.max(40,self:GetWidth()-22),math.max(self:GetHeight()-20,self.text:GetStringHeight() or 20)); self.offset=0; self.scroll:SetVerticalScroll(0)
    end
    box:SetScript("OnSizeChanged",function(self) self:SetText(self.fullText) end)
    box:EnableMouseWheel(true); box:SetScript("OnMouseWheel",function(self,delta) self.offset=math.max(0,math.min((self.offset or 0)-delta*28,math.max(0,self.child:GetHeight()-self:GetHeight()+20))); self.scroll:SetVerticalScroll(self.offset) end)
    return box
end
