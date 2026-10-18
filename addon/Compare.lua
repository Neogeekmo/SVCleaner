local _,SVC=...
local L,UI=SVC.L,SVC.UI
local function text(path) local p={}; for i,key in ipairs(path or {}) do p[i]=tostring(key) end; return table.concat(p," / ") end
local function append(base,path) local p={}; for _,k in ipairs(base) do p[#p+1]=k end; for _,k in ipairs(path or {}) do p[#p+1]=k end; return p end
local function name(slot)
    if not slot then return L.SELECT_VARIABLE end
    for _,key in ipairs(slot.path) do if type(key)=="string" then local n=key:match("^(.-)%-Player%-%d+%-%x+$"); if n then return n end end end
    for i,key in ipairs(slot.path) do if (key=="profiles" or key=="char") and slot.path[i+1] then return tostring(slot.path[i+1]) end end
    return tostring(slot.path[#slot.path] or slot.row.root)
end
function SVC:ShowDiff() self:ShowPage("compare") end
function SVC:ComparisonChoices(side)
    local options={{value="",label=L.SELECT_VARIABLE}}; local opposite=side=="left" and self.right or self.left
    local current=self[side]; if current then options[#options+1]={value=current,label=name(current),detail=current.row.addon.." / "..current.row.root.." / "..text(current.path)} end
    local function visit(row,value,path,depth)
        if #options>=400 or type(value)~="table" then return end
        local slot={row=row,path=path}; options[#options+1]={value=slot,label=name(slot),detail=row.addon.." / "..row.root.." / "..text(path)}
        if depth<2 then for _,key in ipairs(self:Keys(value)) do local child=rawget(value,key); if type(child)=="table" and not (issecretvalue and issecretvalue(child)) then visit(row,child,append(path,{key}),depth+1) end; if #options>=400 then break end end end
    end
    for _,row in ipairs(self.rows) do if row.available and (not opposite or row.addon==opposite.row.addon and row.root==opposite.row.root and row.scope==opposite.row.scope) then visit(row,row.value,{},0) end end
    return options
end
function SVC:RefreshDiff()
    if not self.diffList then return end
    self.diffGeneration=self.generation
    self.diffRows,self.diffItem={},nil; self.copyAllLeft:SetEnabled(false); self.copyAllRight:SetEnabled(false)
    self.leftPicker:SetOptions(self:ComparisonChoices("left"),self.left or ""); self.rightPicker:SetOptions(self:ComparisonChoices("right"),self.right or "")
    self.leftTitle:SetText(L.REFERENCE); self.rightTitle:SetText(L.COMPARE_WITH)
    self.diffList.headings[2]:SetText(name(self.left)); self.diffList.headings[3]:SetText(name(self.right))
    self.leftPath:SetText(self.left and self.left.row.root.." / "..text(self.left.path) or "")
    self.rightPath:SetText(self.right and self.right.row.root.." / "..text(self.right.path) or "")
    self.copyLeft.label:SetText(string.format(L.COPY_TO,name(self.left))); self.copyRight.label:SetText(string.format(L.COPY_TO,name(self.right)))
    self.copyAllLeft.label:SetText(L.COPY_ALL..": "..name(self.left)); self.copyAllRight.label:SetText(L.COPY_ALL..": "..name(self.right))
    self.diffBefore:SetText(""); self.diffAfter:SetText("")
    self.copyLeft:SetEnabled(false); self.copyRight:SetEnabled(false)
    if not self.left or not self.right then self.diffList:SetItems({}); self.diffTitle:SetText(L.SELECT_TWO); return end
    if self.left.row.root~=self.right.row.root or self.left.row.addon~=self.right.row.addon or self.left.row.scope~=self.right.row.scope then self.diffList:SetItems({}); self.diffTitle:SetText(L.TYPE_ID); return end
    local rows,limited=self:Diff(self:Resolve(self.left.row.root,self.left.path),self:Resolve(self.right.row.root,self.right.path))
    if self:Protected(self.left.row.root,self.left.path) or self:Protected(self.right.row.root,self.right.path) then for _,row in ipairs(rows) do row.protected,row.copyable=true,false end end
    self.diffRows=rows; self.diffTitle:SetText(limited and L.LIMIT or #rows==0 and L.IDENTICAL or string.format(L.DIFFERENCES,#rows))
    for _,row in ipairs(rows) do
        for _,side in ipairs({"left","right"}) do
            local slot=self[side]; local full=append(slot.path,row.path)
            for _,request in ipairs(self.pending) do
                local same=request.root==slot.row.root and request.addon==slot.row.addon and #request.path==#full
                for i,key in ipairs(full) do if not request.path[i] or request.path[i].value~=key or request.path[i].type~=type(key) then same=false end end
                if same then row[side.."Prepared"]=true; row[side.."Planned"]=request.value end
            end
        end
    end
    for _,row in ipairs(rows) do row.searchText=self:Fold(text(row.path).." "..self:Preview(row.left).." "..self:Preview(row.right)) end
    self:FilterDiff()
    local compatible=0; for _,row in ipairs(rows) do if row.copyable then compatible=compatible+1 end end
    self.copyAllLeft:SetEnabled(compatible>0 and not limited); self.copyAllRight:SetEnabled(compatible>0 and not limited)
end
-- Typing only filters the last comparison. Explicit refresh, changing either
-- side, and preparing requests rebuild it from the live values.
function SVC:FilterDiff()
    if not self.diffList then return end
    if self.diffGeneration~=self.generation then self:RefreshDiff(); return end
    local filtered,visible={},false
    local query=self:Fold(self.diffQuery)
    for _,row in ipairs(self.diffRows or {}) do
        if row.searchText:find(query,1,true) then
            filtered[#filtered+1]=row
            if row==self.diffItem then visible=true end
        end
    end
    if not visible then
        self.diffItem=nil; self.diffList.selected=nil
        self.copyLeft:SetEnabled(false); self.copyRight:SetEnabled(false)
        self.diffBefore:SetText(""); self.diffAfter:SetText("")
    end
    self.diffList:SetItems(filtered,true)
end
function SVC:InspectDiff(item)
    self.diffItem=item; self.diffList.selected=item; self.diffList:Render()
    self.diffBefore:SetText(name(self.left).."\n"..text(item.path).."\n\n"..(item.left==nil and L.MISSING or self:Preview(item.left)))
    self.diffAfter:SetText(name(self.right).."\n"..text(item.path).."\n\n"..(item.right==nil and L.MISSING or self:Preview(item.right)))
    self.copyLeft:SetEnabled(item.copyable); self.copyRight:SetEnabled(item.copyable)
end
function SVC:QueueDiff(item,direction)
    if item and not item.copyable then self:Notice(L.LOCKED); return end
    local source=direction=="right" and self.left or self.right; local target=direction=="right" and self.right or self.left
    if not source or not target then return end
    local candidates={}; local before,after={},{}
    for _,row in ipairs(item and {item} or self.diffRows or {}) do
        local targetPath=append(target.path,row.path); local sourcePath=append(source.path,row.path)
        if row.copyable and not self:Protected(source.row.root,sourcePath) and not self:Protected(target.row.root,targetPath) then
            local value=direction=="right" and row.left or row.right
            -- Explicit branching preserves false values.
            if direction=="right" then value=row.left else value=row.right end
            candidates[#candidates+1]={path=targetPath,value=value,expected=self:Resolve(target.row.root,targetPath)}
            before[#before+1]=text(row.path).." = "..self:Preview(self:Resolve(target.row.root,targetPath))
            after[#after+1]=text(row.path).." = "..self:Preview(value)
        end
    end
    if #candidates==0 then self:Notice(L.LOCKED); return end
    self:Review(string.format(L.COPY_CONFIRM,name(target),name(source)),table.concat(before,"\n"),table.concat(after,"\n"),function()
        for _,request in ipairs(candidates) do if self:Resolve(target.row.root,request.path)~=request.expected then self:Notice(L.UNAVAILABLE); return end end
        for _,request in ipairs(candidates) do local ok,err=self:Queue(target.row,request.path,"edit",request.value); if not ok then self:Notice(err); return end end
        self:Notice(L.QUEUED); self:Refresh(); self:RefreshDiff()
    end)
end
function SVC:CreateDiff()
    self.leftTitle=UI:Text(self.diff,L.REFERENCE,11,"muted"); self.rightTitle=UI:Text(self.diff,L.COMPARE_WITH,11,"muted")
    self.leftPath=UI:Text(self.diff,"",10,"muted"); self.rightPath=UI:Text(self.diff,"",10,"muted")
    self.leftPath:SetWordWrap(false); self.rightPath:SetWordWrap(false)
    self.leftPicker=UI:Choice(self.diff,400,{},"",function(value) self.left=value~="" and value or nil; self:RefreshDiff() end)
    self.rightPicker=UI:Choice(self.diff,400,{},"",function(value) self.right=value~="" and value or nil; self:RefreshDiff() end)
    self.swap=UI:IconButton(self.diff,7,L.SWAP,function() self.left,self.right=self.right,self.left; self:RefreshDiff() end)
    self.diffTitle=UI:Text(self.diff,L.SELECT_TWO,12,"muted")
    self.diffSearch=UI:Input(self.diff,340,"",function(query) self.diffQuery=query; self.diffList.offset=0; self:FilterDiff() end); self.diffSearch.placeholder:SetText(L.FILTER_VALUES)
    self.diffList=UI:Grid(self.diff,{{label=L.KEY,width=.28},{label=L.REFERENCE,width=.29,role="left"},{label=L.COMPARE_WITH,width=.29,role="right"},{label=L.STATUS,width=.14,role="muted"}},function(button,item)
        button.cells[1]:SetText(UI:Display(text(item.path)))
        for i,side in ipairs({"left","right"}) do
            local value=item[side]==nil and L.MISSING or self:Preview(item[side])
            if item[side.."Prepared"] then value=value.." -> "..self:Preview(item[side.."Planned"]) end
            button.cells[i+1]:SetText(UI:Display(value))
        end
        button.cells[4]:SetText((item.leftPrepared or item.rightPrepared) and L.PREPARED or item.protected and L.LOCKED or item.large and L.READ_ONLY or (item.left==nil or item.right==nil) and L.MISSING or not item.copyable and L.TYPE_MISMATCH or "")
        button:SetScript("OnClick",function() self:InspectDiff(item) end)
        UI:Tooltip(button,function() return text(item.path).."\n"..name(self.left)..": "..self:Preview(item.left):sub(1,1200).."\n"..name(self.right)..": "..self:Preview(item.right):sub(1,1200) end)
    end)
    self.diffBefore=UI:ReadBox(self.diff,450,90); self.diffAfter=UI:ReadBox(self.diff,450,90)
    self.copyLeft=UI:Button(self.diff,"",180,function() if self.diffItem then self:QueueDiff(self.diffItem,"left") end end,"left")
    self.copyRight=UI:Button(self.diff,"",180,function() if self.diffItem then self:QueueDiff(self.diffItem,"right") end end,"right")
    self.copyAllLeft=UI:Button(self.diff,"",200,function() self:QueueDiff(nil,"left") end,"left")
    self.copyAllRight=UI:Button(self.diff,"",200,function() self:QueueDiff(nil,"right") end,"right")
    for _,pair in ipairs({{self.copyLeft,"left"},{self.copyAllLeft,"left"},{self.copyRight,"right"},{self.copyAllRight,"right"}}) do
        local side=pair[2]; UI:Tooltip(pair[1],function() return string.format(L.COPY_CONFIRM,name(self[side]),name(self[side=="left" and "right" or "left"])) end)
    end
end
function SVC:LayoutDiff(w,h)
    local half=(w-48)/2
    local function put(f,x,y,width,height) f:ClearAllPoints(); f:SetPoint("TOPLEFT",self.diff,"TOPLEFT",x,-y); f:SetSize(width,height) end
    put(self.leftTitle,16,12,half,18); put(self.rightTitle,32+half,12,half,18)
    put(self.leftPicker,16,34,half-48,28); put(self.rightPicker,32+half,34,half,28); put(self.swap,half-18,34,26,28)
    put(self.leftPath,16,70,half,18); put(self.rightPath,32+half,70,half,18)
    put(self.diffTitle,16,102,w-400,20); put(self.diffSearch,w-368,96,352,28)
    put(self.diffList,16,136,w-32,math.max(90,h-288))
    put(self.diffBefore,16,h-144,half,90); put(self.diffAfter,32+half,h-144,half,90)
    put(self.copyLeft,16,h-42,half*.50-4,26); put(self.copyAllLeft,20+half*.50,h-42,half*.50-4,26)
    put(self.copyRight,32+half,h-42,half*.50-4,26); put(self.copyAllRight,36+half+half*.50,h-42,half*.50-4,26)
end
