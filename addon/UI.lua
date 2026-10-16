local _, SVC = ...
local UI, L = SVC.UI, SVC.L
local function pathText(path) local parts={}; for i,key in ipairs(path or {}) do parts[i]=tostring(key) end; return table.concat(parts," / ") end
local function place(frame,parent,x,y,w,h) frame:ClearAllPoints(); frame:SetPoint("TOPLEFT",parent,"TOPLEFT",x,-y); if w and h then frame:SetSize(w,h) end end
local function pathCopy(path) local p={}; for i,key in ipairs(path or {}) do p[i]=key end; return p end

function SVC:Notice(text) if self.status then self.status:SetText(text or "") end end
function SVC:ResetFilters()
    self.filters={state="loaded",scope="all",addon="all",kind="all"}; self.query,self.charQuery="",""
    self.search:SetText(""); self.charSearch:SetText(""); self:Refresh()
end
function SVC:Refresh()
    if not self.frame then return end
    local items, addons, options={}, {}, {{value="all",label=L.ALL_ADDONS}}
    local f=self.filters; local bytes,loaded=0,0
    for _,row in ipairs(self.rows) do
        if row.loaded then loaded=loaded+1 end; if row.available then bytes=bytes+row.bytes end
        if not addons[row.addon] then addons[row.addon]=true; options[#options+1]={value=row.addon,label=row.addon,detail=row.title} end
        if (f.state=="all" or (f.state=="loaded")==not not row.loaded) and (f.scope=="all" or f.scope==row.scope) and (f.addon=="all" or f.addon==row.addon)
            and self:Fold(row.addon.." "..row.title.." "..row.root):find(self:Fold(self.query),1,true) then items[#items+1]=row end
    end
    local selected
    for _,row in ipairs(items) do if self.selected and row.addon==self.selected.addon and row.root==self.selected.root and row.scope==self.selected.scope then selected=row; break end end
    if self.selected and not selected then self.selected,self.path,self.editSelection=nil,{},nil elseif selected then self.selected=selected end
    self.catalog:SetItems(items,true); self.catalog.selected=self.selected; self.catalog:Render()
    self.addonFilter:SetOptions(options,f.addon); self.stateFilter:SetOptions(self.stateFilter.options,f.state); self.scopeFilter:SetOptions(self.scopeFilter.options,f.scope)
    self.kindFilter:SetOptions(self.kindFilter.options,f.kind)
    self.count:SetText(string.format(L.RESULTS,#items,#self.rows)); self.metric:SetText(L.ESTIMATE..": "..self:FormatBytes(bytes))
    self.loadedCount:SetText(string.format(L.LOADED_COUNT,loaded,#self.rows-loaded)); self.queueCount:SetText(string.format(L.REQUEST_COUNT,#self.pending))
    self.reloadButton:SetEnabled(#self.pending > 0 and not InCombatLockdown())
    self:RefreshTree(); self:RefreshDetail()
end
function SVC:OpenRow(row)
    self.selected,self.path,self.editSelection=row,{},nil; self.comparisonSelection={}; self.detail:Hide(); self.charQuery=""; self.charSearch:SetText("")
    self.catalog.selected=row; self.catalog:Render(); self:RefreshTree(); self:RefreshDetail(); self:Layout()
end
function SVC:RefreshTree()
    if not self.tree then return end
    local row=self.selected
    if not row then self.tree:SetItems({}); self.pathLabel:SetText(L.SELECT_VARIABLE); self.treeCount:SetText(""); self.compareButton:SetEnabled(false); self.createButton:SetEnabled(false); return end
    self.pathLabel:SetText(row.root..(#(self.path or {})>0 and " / "..pathText(self.path) or ""))
    local value=self:Resolve(row.root,self.path or {}); local items={}; local query=self:Fold(self.charQuery); local kind=self.filters.kind
    if row.available and type(value)=="table" then
        if self.treeValue~=value or self.treeGeneration~=self.generation then self.treeValue,self.treeGeneration,self.treeKeys=value,self.generation,self:Keys(value) end
        for _,key in ipairs(self.treeKeys) do
            local child=rawget(value,key)
            if child~=nil and (not issecretvalue or not issecretvalue(child)) then
                local characterLabel=self:CharacterLabel(key); local label=characterLabel or tostring(key); local char=characterLabel~=nil
                local path=pathCopy(self.path); path[#path+1]=key; local protected=self:Protected(row.root,path)
                if (kind=="all" or kind=="char" and char or kind=="table" and type(child)=="table" or kind=="value" and type(child)~="table" or kind=="protected" and protected)
                    and self:Fold(tostring(key).." "..self:Preview(child)):find(query,1,true) then
                    items[#items+1]={key=key,label=label,value=child,path=path,protected=protected}
                end
            end
        end
    elseif row.available and value~=nil then items[1]={key=row.root,label=row.root,value=value,path=pathCopy(self.path),protected=self:Protected(row.root,self.path)} end
    local visible=false; for _,item in ipairs(items) do if self.editSelection and item.key==self.editSelection.key then visible=true; break end end
    if self.editSelection and not visible then self.editSelection=nil; self:RefreshDetail() end
    local marked={}; for _,entry in ipairs(self.comparisonSelection or {}) do for _,item in ipairs(items) do if entry.key==item.key then marked[#marked+1]=item; break end end end; self.comparisonSelection=marked
    self.tree.selected=self.editSelection and self.editSelection.key; self.tree:SetItems(items,true)
    self.treeCount:SetText(string.format(L.COUNT,#items)); self.up:SetEnabled(#self.path>0)
    self.compareButton:SetEnabled(row.available); self.compareButton.label:SetText(L.COMPARE..((#(self.comparisonSelection or {})>0) and " ("..#self.comparisonSelection..")" or ""))
    self.createButton:SetEnabled(row.loaded and (type(value)=="table" or value==nil and #self.path==0) and not self:Protected(row.root,self.path))
end
function SVC:SelectValue(item)
    self.editSelection=item; self.tree.selected=item.key; self.tree:Render()
    self.detail:SetShown(type(item.value)~="table"); self:RefreshDetail(); self:Layout()
end
function SVC:OpenSelection()
    if self.editSelection and type(self.editSelection.value)=="table" then self.path=pathCopy(self.editSelection.path); self.editSelection=nil; self.comparisonSelection={}; self.detail:Hide(); self.tree.offset=0; self:RefreshTree(); self:RefreshDetail(); self:Layout() end
end
function SVC:MarkComparison(item)
    if not item then return end
    local selected=self.comparisonSelection or {}; self.comparisonSelection=selected
    for i,entry in ipairs(selected) do if entry.key==item.key then table.remove(selected,i); self:RefreshTree(); return end end
    if #selected==2 then table.remove(selected,1) end
    selected[#selected+1]=item; self:RefreshTree()
end
function SVC:CompareSelection()
    if not self.selected or not self.selected.available then return end
    local marked=self.comparisonSelection or {}
    self.left={row=self.selected,path=pathCopy(marked[1] and marked[1].path or self.editSelection and self.editSelection.path or self.path)}
    self.right=marked[2] and {row=self.selected,path=pathCopy(marked[2].path)} or nil
    self:ShowDiff()
end
function SVC:RefreshDetail()
    if not self.detail then return end
    local row,item=self.selected,self.editSelection
    if not item then self.detail:Hide(); self:Layout() end
    self.detailTitle:SetText(item and tostring(item.key).." ("..type(item.value)..")" or row and row.root or L.DETAIL)
    self.detailPath:SetText(row and row.root.." / "..pathText(item and item.path or self.path) or L.SELECT_VARIABLE)
    local editable=item and row.available and not item.protected and (type(item.value)=="string" or type(item.value)=="number" or type(item.value)=="boolean")
    if editable and type(item.value)=="string" and #item.value>32768 then editable=false end
    self.editButton:SetEnabled(not not editable); self.deleteButton:SetEnabled(not not (item and row.available and not item.protected))
    self.openButton:SetEnabled(not not (item and type(item.value)=="table")); self.detailButton:SetEnabled(not not item)
    if self.detailSelection~=item or self.detailRow~=row then self.editor:SetText(editable and tostring(item.value) or "") end
    self.detailSelection,self.detailRow=item,row; self.editor:SetEnabled(not not editable)
    local hint=L.SELECT_VALUE
    if row and not row.available then hint=row.loaded and L.UNAVAILABLE or L.NOT_LOADED
    elseif item then hint=item.protected and L.LOCKED or type(item.value)=="table" and L.SCALAR_HINT or type(item.value)=="boolean" and L.BOOL_HINT or type(item.value)=="number" and L.NUMBER_HINT or L.STAGING_HINT end
    self.detailHint:SetText(hint)
    self.original:SetText(item and (type(item.value)=="table" and self:Preview(item.value) or tostring(item.value)) or hint)
end
function SVC:Review(title,before,after,callback)
    self.reviewConfirm.label:SetText(L.PREPARE)
    self.reviewTitle:SetText(title); self.reviewBefore:SetText(L.ORIGINAL.."\n\n"..before); self.reviewAfter:SetText(L.NEW_VALUE.."\n\n"..after); self.reviewCallback=callback; self.reviewBlocker:Show(); self.review:Show()
end
function SVC:PrepareReload()
    if #self.pending == 0 then return end
    self:Review(L.APPLY_RELOAD, string.format(L.REQUEST_COUNT,#self.pending), L.APPLY_HINT, function()
        local ok,err=self:ApplyPending(); if not ok then self:Notice(err) end
    end)
    self.reviewConfirm.label:SetText(L.APPLY_RELOAD)
end

function SVC:ShowCreate()
    local row=self.selected; if not row then return end
    self.createRow,self.createPath=row,pathCopy(self.path)
    self.createKey:SetText(""); self.createValue:SetText(""); self.createBlocker:Show(); self.createDialog:Show()
end

function SVC:PrepareCreate()
    local row,path=self.createRow,pathCopy(self.createPath)
    local key=self.createKey:GetText()
    if not (#path==0 and self:Resolve(row.root,{})==nil) then
        if self.createKeyType.value=="number" then key=tonumber(key)
        elseif self.createKeyType.value=="boolean" then
            if key~="true" and key~="false" then self:Notice(L.BOOL_HINT); return end; key=key=="true"
        end
        if key==nil or type(key)=="number" and (key~=key or key==math.huge or key==-math.huge) then self:Notice(L.NUMBER_HINT); return end
        path[#path+1]=key
    end
    local value=self.createValue:GetText(); local typ=self.createValueType.value
    if typ=="number" then value=tonumber(value); if not value then self:Notice(L.NUMBER_HINT); return end
    elseif typ=="boolean" then if value~="true" and value~="false" then self:Notice(L.BOOL_HINT); return end; value=value=="true"
    elseif typ=="table" then value={} end
    local ok,err=self:Queue(row,path,"create",value)
    self:Notice(ok and L.QUEUED or err)
    if ok then self.createDialog:Hide(); self:Refresh() end
end

function SVC:WarnPending()
    if #self.pending==0 or self.reloading then return end
    local warning = self:PendingWarning()
    print("SVCleaner: "..warning)
    if StaticPopupDialogs and StaticPopup_Show then
        StaticPopupDialogs.SVCLEANER_PENDING={text=warning,button1=L.CLOSE,
            timeout=0,whileDead=1,hideOnEscape=1}
        StaticPopup_Show("SVCLEANER_PENDING")
    end
end

function SVC:DiscoverCVars()
    self.cvarNames = {}
    if type(ConsoleGetAllCommands) == "function" then
        local ok, commands = pcall(ConsoleGetAllCommands)
        if ok and type(commands) == "table" then
            local seen = {}
            for _, command in ipairs(commands) do
                if type(command.command) == "string" and command.commandType == (Enum and Enum.ConsoleCommandType and Enum.ConsoleCommandType.Cvar or 0) and not seen[command.command:lower()] then
                    seen[command.command:lower()] = true
                    self.cvarNames[#self.cvarNames + 1] = {name = command.command, help = command.help or ""}
                end
            end
        end
    end
    table.sort(self.cvarNames, function(a,b) return a.name:lower() < b.name:lower() end)
    self:RefreshCVars()
end

function SVC:RefreshCVars()
    if not self.cvarList then return end
    local items, query, found = {}, self:Fold(self.cvarQuery), false
    local names = self.cvarNames or {}
    -- Exact lookup remains usable on clients without console enumeration.
    local candidates = {}; for _, entry in ipairs(names) do candidates[#candidates + 1] = entry end
    for _, entry in ipairs(names) do if entry.name:lower() == query then found = true end end
    if not found and query:match("^[%w_]+$") then candidates[#candidates + 1] = {name = self.cvarQuery, help = ""} end
    for _, entry in ipairs(candidates) do
        local info = self:ReadCVar(entry.name)
        if info and self:Fold(entry.name .. " " .. entry.help .. " " .. info.value):find(query,1,true) then
            info.help = entry.help
            for _, request in ipairs(self.pending) do
                local player, realm = self.Compat:PlayerIdentity()
                if request.kind == "cvar" and request.root:lower() == info.name:lower() and request.character == player .. " - " .. realm then info.prepared = request.value; break end
            end
            items[#items + 1] = info
        end
    end
    self.cvarList:SetItems(items,true)
    self.cvarCount:SetText(string.format(L.CVAR_COUNT,#items))
    if self.cvarSelection then
        local current = self:ReadCVar(self.cvarSelection.name)
        self.cvarApply:SetEnabled(current ~= nil and not current.readOnly)
        self.cvarEditor:SetEnabled(current ~= nil and not current.readOnly)
        self.cvarDefault:SetEnabled(current ~= nil and not current.readOnly and current.default ~= nil)
        if current then
            self.cvarOriginal:SetText(current.value)
            self.cvarDefaultLabel:SetText(L.CVAR_DEFAULT .. ": " .. (current.default or L.UNAVAILABLE))
        end
    end
end

function SVC:SelectCVar(item)
    self.cvarSelection = item
    self.cvarTitle:SetText(item.name)
    self.cvarDescription:SetText(item.help ~= "" and item.help or L.CVAR_HINT)
    self.cvarOriginal:SetText(item.value)
    self.cvarDefaultLabel:SetText(L.CVAR_DEFAULT .. ": " .. (item.default or L.UNAVAILABLE))
    self.cvarEditor:SetText(item.prepared ~= nil and item.prepared or item.value)
    self.cvarEditor:SetEnabled(not item.readOnly)
    self.cvarApply:SetEnabled(not item.readOnly)
    self.cvarDefault:SetEnabled(not item.readOnly and item.default ~= nil)
end

function SVC:PrepareCVar(useDefault)
    local item = self.cvarSelection
    if not item then return end
    local current = self:ReadCVar(item.name)
    if not current or current.readOnly then self:Notice(L.CVAR_LOCKED); return end
    local value = self.cvarEditor:GetText()
    if useDefault then value = current.default end
    if value == nil then self:Notice(L.UNAVAILABLE); return end
    self:Review(L.CVARS .. " / " .. item.name,current.value,value,function()
        local latest = self:ReadCVar(item.name)
        if not latest or latest.value ~= current.value then self:Notice(L.CONFLICT); return end
        local ok,err = self:QueueCVar(item.name,value)
        self:Notice(ok and L.QUEUED or err); self:Refresh(); self:RefreshCVars()
    end)
end
function SVC:QueueSelection(operation)
    local item,row=self.editSelection,self.selected; if not item or not row then self:Notice(L.SELECT_VALUE); return end
    local value=self.editor:GetText()
    if operation=="edit" then
        if type(item.value)=="number" then value=tonumber(value); if not value then self:Notice(L.NUMBER_HINT); return end
        elseif type(item.value)=="boolean" then if value~="true" and value~="false" then self:Notice(L.BOOL_HINT); return end; value=value=="true" end
    end
    if item.protected then self:Notice(L.LOCKED); return end
    local path=pathCopy(item.path)
    if type(item.value)~="table" and self:Resolve(row.root,path)~=item.value then self:Notice(L.UNAVAILABLE); return end
    self:Review((operation=="edit" and L.EDIT or L.CONFIRM_DELETE).."\n"..row.root.." / "..pathText(path),self:Preview(item.value),operation=="edit" and tostring(value) or L.MISSING,function()
        if type(item.value)~="table" and self:Resolve(row.root,path)~=item.value then self:Notice(L.UNAVAILABLE); return end
        local ok,err=self:Queue(row,path,operation,value); self:Notice(ok and L.QUEUED or err); self:Refresh()
    end)
end
function SVC:ShowPage(id)
    self.activePage=id; self.dataPage:SetShown(id=="data"); self.diff:SetShown(id=="compare"); self.cvarPage:SetShown(id=="cvars"); self.overlay:SetShown(id=="guide" or id=="requests")
    local activeTab=id=="compare" and "data" or id
    for key,button in pairs(self.tabs) do UI:Active(button,key==activeTab) end
    if UI.menu then UI.menu:Hide() end
    if id=="compare" then self:RefreshDiff()
    elseif id=="cvars" then self:DiscoverCVars()
    elseif id=="guide" then self.guideTitle:SetText(L.CACHES); self.guideText:SetText(table.concat({L.GUIDE_RELOAD,L.GUIDE_GX,L.GUIDE_GC,L.GUIDE_DISK,L.GUIDE_SETTINGS,L.GUIDE_NOTE},"\n\n"))
    elseif id=="requests" then
        self.guideTitle:SetText(string.format(L.REQUEST_COUNT,#self.pending)); local lines={L.REQUEST_HINT}
        for _,request in ipairs(self.pending) do if request.kind=="cvar" then lines[#lines+1]=L.CVAR_HINT; break end end
        for _,request in ipairs(self.pending) do local path={}; for i,k in ipairs(request.path) do path[i]=k.value end; lines[#lines+1]=(request.kind=="cvar" and L.CVARS or request.addon).." / "..request.root.." / "..pathText(path).."\n"..(request.operation=="create" and L.CREATE or request.operation=="edit" and L.EDIT or L.DELETE)..": "..tostring(request.expectedValue).." -> "..(request.operation~="delete-value" and self:Preview(request.value) or L.MISSING).."\n"..(request.status and L["RESULT_"..request.status:upper():gsub("-","_")] or L.PREPARED) end
        for _,request in ipairs(SVCleanerDB.lastApplication or {}) do
            local path={}; for i,k in ipairs(request.path or {}) do path[i]=k.value end
            lines[#lines+1]=request.root.." / "..pathText(path).." · "..L["RESULT_"..request.status:upper():gsub("-","_")]
                .."\n"..L.ORIGINAL..": "..(request.before or "").."\n"..L.NEW_VALUE..": "..(request.desired or "").."\n"..L.VALUE..": "..(request.observed or "")
        end
        self.guideText:SetText(table.concat(lines,"\n\n"))
    end
end
function SVC:ShowGuide() self:ShowPage("guide") end
function SVC:Layout()
    if not self.frame or self.layoutBusy then return end; self.layoutBusy=true
    local w,h=self.frame:GetWidth(),self.frame:GetHeight(); local inner=w-32
    place(self.metrics,self.frame,16,106,inner,34)
    self.metric:SetWidth(inner*.45); self.loadedCount:SetPoint("LEFT",self.metrics,"LEFT",inner*.46,0)
    self.queueCount:SetPoint("RIGHT",self.metrics,"RIGHT",-12,0)
    for _,page in ipairs({self.dataPage,self.diff,self.overlay,self.cvarPage}) do place(page,self.frame,16,150,inner,h-204) end
    place(self.cvarSearch,self.cvarPage,16,14,inner-210,28); place(self.cvarCount,self.cvarPage,inner-180,18,164,22)
    place(self.cvarHint,self.cvarPage,16,50,inner-32,36)
    place(self.cvarList,self.cvarPage,16,92,inner-32,h-536)
    place(self.cvarTitle,self.cvarPage,16,h-430,inner-32,22)
    place(self.cvarDescription,self.cvarPage,16,h-403,inner-32,38)
    place(self.cvarOriginal,self.cvarPage,16,h-358,inner*.38-24,70)
    place(self.cvarEditor,self.cvarPage,inner*.38,h-358,inner*.62-16,28)
    place(self.cvarDefaultLabel,self.cvarPage,inner*.38,h-324,inner*.62-16,22)
    place(self.cvarApply,self.cvarPage,inner*.38,h-292,160,28)
    place(self.cvarDefault,self.cvarPage,inner*.38+168,h-292,240,28)
    local widths={inner*.27,inner*.24,inner*.19,inner*.17,inner*.10}; local controls={self.search,self.addonFilter,self.stateFilter,self.scopeFilter,self.reset}; local x=0
    for i,c in ipairs(controls) do place(c,self.dataPage,x,0,widths[i],26); x=x+widths[i]+6 end
    local catalogWidth=220; local treeX=catalogWidth+12; local treeWidth=inner-treeX
    place(self.catalogLabel,self.dataPage,0,41,catalogWidth,20)
    place(self.catalog,self.dataPage,0,66,catalogWidth,h-276)
    place(self.pathLabel,self.dataPage,treeX+36,39,treeWidth-36,22)
    place(self.up,self.dataPage,treeX,36,26,26)
    place(self.charSearch,self.dataPage,treeX,72,treeWidth-210,28); place(self.kindFilter,self.dataPage,inner-200,72,200,28)
    local actions={self.openButton,self.detailButton,self.compareButton,self.createButton}; x=treeX
    for i,button in ipairs(actions) do local width=i==3 and 132 or 88; place(button,self.dataPage,x,108,width,26); x=x+width+6 end
    place(self.treeCount,self.dataPage,inner-180,112,180,20)
    local detailHeight=self.detail:IsShown() and 170 or 0
    place(self.tree,self.dataPage,treeX,142,treeWidth,h-354-detailHeight)
    place(self.detail,self.dataPage,treeX,h-206-detailHeight,treeWidth,detailHeight)
    local dw=treeWidth
    place(self.detailTitle,self.detail,12,9,dw-48,20); place(self.detailClose,self.detail,dw-34,6,24,24)
    place(self.detailPath,self.detail,12,31,dw-24,18)
    place(self.originalLabel,self.detail,12,57,dw*.42-18,18); place(self.original,self.detail,12,79,dw*.42-18,70)
    place(self.newLabel,self.detail,dw*.42,57,dw*.58-14,18); place(self.editor,self.detail,dw*.42,79,dw*.58-14,28)
    place(self.detailHint,self.detail,dw*.42,112,dw*.58-14,22)
    place(self.editButton,self.detail,dw*.42,138,100,26); place(self.deleteButton,self.detail,dw*.42+106,138,120,26)
    self:LayoutDiff(inner,h-204)
    place(self.guideTitle,self.overlay,22,20,inner-44,30); place(self.guideText,self.overlay,22,65,inner-44,h-295)
    self.review:SetSize(math.min(900,inner-30),420); self.review:SetPoint("CENTER")
    self.createDialog:SetSize(600,290); self.createDialog:SetPoint("CENTER")
    local rw=self.review:GetWidth(); place(self.reviewTitle,self.review,20,20,rw-40,60)
    place(self.reviewBefore,self.review,20,96,(rw-52)/2,250); place(self.reviewAfter,self.review,32+(rw-52)/2,96,(rw-52)/2,250)
    self.layoutBusy=false
end
function SVC:CreateUI()
    self.filters=self.filters or {state="loaded",scope="all",addon="all",kind="all"}
    local frame=UI:Panel(UIParent,"window"); self.frame=frame; _G.SVCleanerWindow=frame; table.insert(UISpecialFrames,"SVCleanerWindow")
    frame:SetFrameStrata("DIALOG"); frame:EnableMouse(true); frame:SetClampedToScreen(true); frame:SetMovable(true); frame:SetResizable(true)
    local scale=math.min(1,(UIParent:GetWidth()-40)/1040,(UIParent:GetHeight()-50)/680)
    if frame.SetResizeBounds then frame:SetResizeBounds(1040,680,math.max(1040,UIParent:GetWidth()/scale-32),math.max(680,UIParent:GetHeight()/scale-48)) elseif frame.SetMinResize then frame:SetMinResize(1040,680) end
    frame:SetScale(scale)
    local geometry=SVCleanerDB.geometry or {}; frame:SetSize(math.max(1040,math.min(geometry.width or 1260,UIParent:GetWidth()-40)),math.max(680,math.min(geometry.height or 820,UIParent:GetHeight()-50))); frame:SetPoint("CENTER")
    local header=CreateFrame("Frame",nil,frame); header:SetPoint("TOPLEFT"); header:SetPoint("TOPRIGHT"); header:SetHeight(62); header:EnableMouse(true); header:RegisterForDrag("LeftButton")
    header:SetScript("OnDragStart",function() frame:StartMoving() end); header:SetScript("OnDragStop",function() frame:StopMovingOrSizing() end)
    local logo=header:CreateTexture(nil,"ARTWORK"); logo:SetTexture("Interface\\AddOns\\SVCleaner\\Assets\\logo.tga"); logo:SetSize(40,40); logo:SetPoint("TOPLEFT",16,-10)
    local brand=UI:Text(header,"SV Cleaner",22,"accent"); brand:SetPoint("TOPLEFT",66,-12)
    local tagline=UI:Text(header,L.TAGLINE,11,"muted"); tagline:SetPoint("TOPLEFT",66,-39)
    local theme=UI:Button(header,L.THEME,140,function() SVCleanerDB.theme=SVCleanerDB.theme=="dark" and "light" or "dark"; UI:Theme(); self:ShowPage(self.activePage or "data") end); theme:SetPoint("TOPRIGHT",-66,-16)
    local close=UI:IconButton(header,3,L.CLOSE,function() frame:Hide() end); close:SetPoint("TOPRIGHT",-20,-16)
    self.tabs={}; local x=16
    for _,def in ipairs({{"data",L.DATA},{"cvars",L.CVARS},{"requests",L.REQUESTS},{"guide",L.CACHES}}) do
        local id=def[1]; local tab=UI:Button(frame,def[2],154,function() self:ShowPage(id) end); tab:SetPoint("TOPLEFT",x,-66); self.tabs[id]=tab; x=x+160
    end
    self.metrics=UI:Panel(frame); self.metric=UI:Text(self.metrics,"",11,"muted"); self.metric:SetPoint("LEFT",12,0)
    self.loadedCount=UI:Text(self.metrics,"",11,"muted"); self.queueCount=UI:Text(self.metrics,"",11,"accent")
    self.dataPage=CreateFrame("Frame",nil,frame); self.overlay=UI:Panel(frame); self.diff=UI:Panel(frame)
    self.cvarPage=UI:Panel(frame)
    self.cvarSearch=UI:Input(self.cvarPage,600,"",function(value) self.cvarQuery=value; self.cvarList.offset=0; self:RefreshCVars() end); self.cvarSearch.placeholder:SetText(L.CVAR_SEARCH)
    self.cvarCount=UI:Text(self.cvarPage,"",11,"muted"); self.cvarHint=UI:Text(self.cvarPage,L.CVAR_HINT,11,"muted")
    self.cvarList=UI:Grid(self.cvarPage,{{label=L.NAME,width=.32},{label=L.VALUE,width=.24},{label=L.CVAR_DEFAULT,width=.24},{label=L.STATUS,width=.20}},function(button,item)
        button.cells[1]:SetText(UI:Display(item.name)); button.cells[2]:SetText(UI:Display(item.value)); button.cells[3]:SetText(UI:Display(item.default or L.UNAVAILABLE))
        button.cells[4]:SetText(item.readOnly and L.READ_ONLY or item.prepared~=nil and L.PREPARED or "")
        button:SetScript("OnClick",function() self:SelectCVar(item) end)
        UI:Tooltip(button,function() return item.name.."\n"..item.help end)
    end)
    self.cvarTitle=UI:Text(self.cvarPage,L.SELECT_VALUE,15,"accent"); self.cvarDescription=UI:Text(self.cvarPage,"",11,"muted")
    self.cvarOriginal=UI:ReadBox(self.cvarPage,300,70); self.cvarEditor=UI:Input(self.cvarPage,400,""); self.cvarEditor.placeholder:SetText(L.NEW_VALUE); self.cvarEditor:SetEnabled(false)
    self.cvarDefaultLabel=UI:Text(self.cvarPage,"",11,"muted")
    self.cvarApply=UI:Button(self.cvarPage,L.PREPARE,160,function() self:PrepareCVar(false) end); self.cvarApply:SetEnabled(false)
    self.cvarDefault=UI:Button(self.cvarPage,L.CVAR_RESET,240,function() self:PrepareCVar(true) end); self.cvarDefault:SetEnabled(false)
    self.search=UI:Input(self.dataPage,250,"",function(value) self.query=value; self.catalog.offset=0; self:Refresh() end); self.search.placeholder:SetText(L.SEARCH)
    self.addonFilter=UI:Choice(self.dataPage,240,{{value="all",label=L.ALL_ADDONS}},"all",function(value) self.filters.addon=value; self.catalog.offset=0; self:Refresh() end)
    self.stateFilter=UI:Choice(self.dataPage,160,{{value="loaded",label=L.LOADED},{value="unloaded",label=L.UNLOADED},{value="all",label=L.ALL_STATES}},"loaded",function(value) self.filters.state=value; self.catalog.offset=0; self:Refresh() end)
    self.scopeFilter=UI:Choice(self.dataPage,150,{{value="all",label=L.ALL_SCOPES},{value="account",label=L.ACCOUNT},{value="character",label=L.CHARACTER}},"all",function(value) self.filters.scope=value; self.catalog.offset=0; self:Refresh() end)
    self.reset=UI:Button(self.dataPage,L.RESET_SHORT,150,function() self:ResetFilters() end)
    self.catalogLabel=UI:Text(self.dataPage,L.DATA,12); self.count=self.catalogLabel
    self.catalog=UI:List(self.dataPage,300,500,function(button,item)
        button.text:SetText(item.root); button.detail:SetText(item.addon.." · "..(item.available and self:FormatBytes(item.bytes) or item.loaded and L.UNAVAILABLE or L.UNLOADED))
        button:SetScript("OnClick",function() self:OpenRow(item) end); UI:Tooltip(button,function() return item.title.."\n"..item.root.."\n"..(item.scope=="character" and L.CHARACTER or L.ACCOUNT).."\n"..(item.available and self:FormatBytes(item.bytes) or L.NOT_LOADED) end)
    end,48)
    self.pathLabel=UI:Text(self.dataPage,"",12,"accent"); self.pathLabel:SetWordWrap(false)
    self.up=UI:IconButton(self.dataPage,2,L.UP,function() if #self.path>0 then table.remove(self.path) end; self.editSelection=nil; self.comparisonSelection={}; self.detail:Hide(); self.tree.offset=0; self:RefreshTree(); self:RefreshDetail(); self:Layout() end)
    self.charSearch=UI:Input(self.dataPage,400,"",function(value) self.charQuery=value; self.tree.offset=0; self:RefreshTree() end); self.charSearch.placeholder:SetText(L.FILTER_VALUES)
    self.kindFilter=UI:Choice(self.dataPage,400,{{value="all",label=L.SHOW_ALL},{value="char",label=L.ONLY_CHARS},{value="table",label=L.ONLY_TABLES},{value="value",label=L.ONLY_VALUES},{value="protected",label=L.PROTECTED_ONLY}},"all",function(value) self.filters.kind=value; self.tree.offset=0; self:RefreshTree() end)
    self.tree=UI:Grid(self.dataPage,{{width=.04,icon=true},{label=L.KEY,width=.32},{label=L.TYPE,width=.12,role="muted"},{label=L.VALUE,width=.38},{label=L.STATUS,width=.14,role="muted"}},function(button,item)
        local display=tostring(item.key); local characterName,guid=display:match("^(.-)%-(Player%-%d+%-%x+)$")
        if characterName then display=characterName end
        button.cells[1]:SetText(""); button.cells[2]:SetText(UI:Display(display))
        button.cells[3]:SetText(L[string.upper(type(item.value))] or type(item.value))
        button.cells[4]:SetText(UI:Display(self:Preview(item.value)))
        button.cells[5]:SetText(item.protected and L.LOCKED or type(item.value)=="table" and L.OPEN_SHORT or "")
        local marked=false; for _,entry in ipairs(self.comparisonSelection or {}) do if entry.key==item.key then marked=true end end
        button.check.icon:SetTexCoord((marked and 6 or 5)/8,(marked and 7 or 6)/8,0,1)
        button:SetScript("OnClick",function() self:SelectValue(item) end)
        button:SetScript("OnDoubleClick",function() self:SelectValue(item); self:OpenSelection() end)
        UI:Tooltip(button,function() return item.label.."\n"..self:Preview(item.value):sub(1,1500) end)
    end); self.treeCount=UI:Text(self.dataPage,"",11,"muted"); self.treeCount:SetJustifyH("RIGHT")
    self.detail=UI:Panel(self.dataPage); self.detailTitle=UI:Text(self.detail,L.DETAIL,15,"accent"); self.detailPath=UI:Text(self.detail,"",11,"muted")
    self.originalLabel=UI:Text(self.detail,L.ORIGINAL,11,"muted"); self.original=UI:ReadBox(self.detail,350,180); self.detailHint=UI:Text(self.detail,L.SELECT_VALUE,11,"muted")
    self.newLabel=UI:Text(self.detail,L.NEW_VALUE,11,"muted"); self.editor=UI:Input(self.detail,350,""); self.editor.placeholder:SetText(L.NEW_VALUE)
    self.editButton=UI:Button(self.detail,L.EDIT,350,function() self:QueueSelection("edit") end)
    self.deleteButton=UI:Button(self.detail,L.DELETE,350,function() self:QueueSelection("delete-value") end,"danger")
    self.detail:Hide()
    self.detailClose=UI:IconButton(self.detail,3,L.CLOSE,function() self.detail:Hide(); self:Layout() end)
    self.openButton=UI:Button(self.dataPage,L.OPEN_SHORT,88,function() self:OpenSelection() end)
    self.detailButton=UI:Button(self.dataPage,L.DETAIL_SHORT,88,function() if self.editSelection then self.detail:Show(); self:RefreshDetail(); self:Layout() end end)
    self.compareButton=UI:Button(self.dataPage,L.COMPARE,132,function() self:CompareSelection() end); UI:Tooltip(self.compareButton,L.SELECT_TWO)
    self.createButton=UI:Button(self.dataPage,L.CREATE,88,function() self:ShowCreate() end)
    self.guideTitle=UI:Text(self.overlay,"",22,"accent"); self.guideText=UI:ReadBox(self.overlay,1000,500)
    self:CreateDiff()
    self.status=UI:Text(frame,L.LOADED_ONLY,11,"muted"); self.status:SetPoint("BOTTOMLEFT",16,14); self.status:SetPoint("BOTTOMRIGHT",-510,14); self.status:SetHeight(30)
    local refresh=UI:Button(frame,L.REFRESH,126,function() self:Discover(); self:Refresh(); if self.activePage=="compare" then self:RefreshDiff() elseif self.activePage=="cvars" then self:DiscoverCVars() end end); refresh:SetPoint("BOTTOMRIGHT",-20,14)
    local clear=UI:Button(frame,L.CLEAR,140,function() self.pending={}; SVCleanerDB.requests=self.pending; self:Refresh(); if self.activePage=="requests" then self:ShowPage("requests") elseif self.activePage=="cvars" then self:RefreshCVars() end end); clear:SetPoint("BOTTOMRIGHT",-154,14)
    self.reloadButton=UI:Button(frame,L.APPLY_RELOAD,200,function() self:PrepareReload() end); self.reloadButton:SetPoint("BOTTOMRIGHT",-302,14)
    local grip=UI:IconButton(frame,4,L.RESIZE,function() end); grip:SetPoint("BOTTOMRIGHT",-1,1); grip:SetSize(16,16)
    grip:SetScript("OnMouseDown",function(_,key) if key=="LeftButton" then frame:StartSizing("BOTTOMRIGHT") end end)
    grip:SetScript("OnMouseUp",function() frame:StopMovingOrSizing(); SVCleanerDB.geometry={width=frame:GetWidth(),height=frame:GetHeight()}; self:Layout() end)
    self.reviewBlocker=UI:Panel(frame); self.reviewBlocker:SetAllPoints(); self.reviewBlocker:SetFrameLevel(frame:GetFrameLevel()+85); self.reviewBlocker:SetBackdropColor(0,0,0,.75); self.reviewBlocker:EnableMouse(true); self.reviewBlocker:Hide()
    self.review=UI:Panel(self.reviewBlocker,"window"); self.review:SetFrameLevel(frame:GetFrameLevel()+90); self.review:Hide(); self.review:SetScript("OnHide",function() self.reviewBlocker:Hide() end)
    self.reviewTitle=UI:Text(self.review,"",18,"accent"); self.reviewBefore=UI:ReadBox(self.review,400,250); self.reviewAfter=UI:ReadBox(self.review,400,250)
    local confirm=UI:Button(self.review,L.PREPARE,220,function() local callback=self.reviewCallback; self.review:Hide(); if callback then callback() end end); confirm:SetPoint("BOTTOMRIGHT",-20,18)
    self.reviewConfirm=confirm
    local cancel=UI:Button(self.review,L.CANCEL,120,function() self.review:Hide() end); cancel:SetPoint("BOTTOMRIGHT",-248,18)
    self.createBlocker=UI:Panel(frame); self.createBlocker:SetAllPoints(); self.createBlocker:SetFrameLevel(frame:GetFrameLevel()+85); self.createBlocker:EnableMouse(true); self.createBlocker:Hide()
    self.createDialog=UI:Panel(self.createBlocker,"window"); self.createDialog:SetFrameLevel(frame:GetFrameLevel()+90); self.createDialog:Hide()
    self.createDialog:SetScript("OnHide",function() self.createBlocker:Hide() end)
    place(UI:Text(self.createDialog,L.CREATE_HINT,13,"accent"),self.createDialog,20,16,560,50)
    local keyTypes={{value="string",label=L.STRING},{value="number",label=L.NUMBER},{value="boolean",label=L.BOOLEAN}}
    self.createKey=UI:Input(self.createDialog,350,""); self.createKey.placeholder:SetText(L.KEY); place(self.createKey,self.createDialog,20,80,350,28)
    self.createKeyType=UI:Choice(self.createDialog,190,keyTypes,"string",function() end); place(self.createKeyType,self.createDialog,380,80,190,28)
    self.createValue=UI:Input(self.createDialog,350,""); self.createValue.placeholder:SetText(L.VALUE); place(self.createValue,self.createDialog,20,130,350,28)
    local valueTypes={unpack(keyTypes)}; valueTypes[#valueTypes+1]={value="table",label=L.TABLE}
    self.createValueType=UI:Choice(self.createDialog,190,valueTypes,"string",function() end); place(self.createValueType,self.createDialog,380,130,190,28)
    local create=UI:Button(self.createDialog,L.PREPARE,220,function() self:PrepareCreate() end); create:SetPoint("BOTTOMRIGHT",-20,18)
    local cancelCreate=UI:Button(self.createDialog,L.CANCEL,120,function() self.createDialog:Hide() end); cancelCreate:SetPoint("BOTTOMLEFT",20,18)
    frame:SetScript("OnSizeChanged",function() self:Layout() end)
    frame:SetScript("OnHide",function() frame:StopMovingOrSizing(); if UI.menu then UI.menu:Hide() end; self.review:Hide(); self.createDialog:Hide(); SVCleanerDB.geometry={width=frame:GetWidth(),height=frame:GetHeight()}; if self.uiReady then self:WarnPending() end end)
    self:Layout(); self:ShowPage("data"); frame:Hide(); self.uiReady=true
end
function SVC:Toggle()
    if InCombatLockdown() then print("SVCleaner: "..L.OUT_COMBAT); return end
    if not self.frame then self:CreateUI() end
    if self.frame:IsShown() then self.frame:Hide(); return end
    self:Discover(); self:Refresh(); if self.activePage=="compare" then self:RefreshDiff() elseif self.activePage=="cvars" then self:DiscoverCVars() end; self.frame:Show(); self:Notice(self.applicationNotice or L.LOADED_ONLY)
end
