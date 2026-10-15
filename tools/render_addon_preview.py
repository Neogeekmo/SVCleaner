"""Preview the actual Lua labels, grids and layout under API doubles, outside WoW."""
import html
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"tests"))
from test_addon import AddonTests


def render(view="route",theme="dark",locale="frFR"):
    addon=AddonTests(); addon.setUp(); addon.lua.globals().SVC.locale=locale; addon.open_ui(); lua=addon.lua
    lua.execute('''
        APRData={ ["Elowen-Player-1305-00000001"]={GUID="Player-1305-00000001",route={step=42,skipCutscenes=true,scale=1},completed={[2021]=true}},
                  ["Thalion-Player-1305-00000002"]={GUID="Player-1305-00000002",route={step=16,skipCutscenes=false,scale=.8},completed={[2021]=false}},
                  ["CustomRoute"]={},["Ancien-Player-1305-00000003"]={step=1},["Exemple-Player-1305-00000004"]={step=6}}
        SVC.rows={{addon="APR",title="Azeroth Pilot Reloaded",root="APRData",scope="account",loaded=true,available=true,bytes=323148,value=APRData},
                  {addon="APR",title="Azeroth Pilot Reloaded",root="APRSettings",scope="account",loaded=true,available=true,bytes=14320},
                  {addon="Vaultloom",title="Vaultloom",root="VaultloomDB",scope="account",loaded=true,available=true,bytes=590400},
                  {addon="Auctionator",title="Auctionator",root="AuctionatorDB",scope="account",loaded=true,available=true,bytes=1202500}}
        SVC:Refresh();SVC:OpenRow(SVC.rows[1])
    ''')
    if view=="route":
        lua.execute('''SVC.path={"Elowen-Player-1305-00000001","route"}; SVC:RefreshTree()
            for _,item in ipairs(SVC.tree.items) do if item.key=="step" then SVC:SelectValue(item);break end end''')
    elif view=="compare":
        lua.execute('''for _,item in ipairs(SVC.tree.items) do
                if item.key=="Elowen-Player-1305-00000001" or item.key=="Thalion-Player-1305-00000002" then SVC:MarkComparison(item) end
            end
            SVC:CompareSelection()
            for _,item in ipairs(SVC.diffRows) do if item.path[#item.path]=="step" then SVC:InspectDiff(item);break end end''')
    svc=lua.globals().SVC; lua.globals().SVCleanerDB.theme=theme;svc.Layout(svc)
    chunks=[]
    def esc(v):return html.escape(str(v or ""))
    def rect(name,parent=(0,0)):
        f=svc[name];p=f._point
        return parent[0]+float(p[4]),parent[1]-float(p[5]),float(f.GetWidth(f)),float(f.GetHeight(f))
    def add(name,cls,body,parent=(0,0)):
        x,y,w,h=rect(name,parent);chunks.append(f'<div class="{cls}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">{body}</div>');return x,y
    def label(name,parent):add(name,"label",esc(svc[name]._text),parent)
    def control(name,parent):
        f=svc[name]; text=esc(f.label._text)
        if name=="up":text="↑"
        if name=="detailClose":text="×"
        if name=="swap":text='<svg width="16" height="16" viewBox="0 0 32 32" style="stroke:var(--text);fill:none;stroke-width:3"><path d="M7 10h18m-5-5 5 5-5 5M25 22H7m5-5-5 5 5 5"/></svg>'
        if name.endswith("Filter") or name.endswith("Picker"):text+='<svg class="arrow" viewBox="0 0 32 32"><path d="m8 12 8 8 8-8"/></svg>'
        add(name,"control"+(" disabled" if not f.IsEnabled(f) else ""),text,parent)
    def grid(name,parent):
        f=svc[name]; cols=list(f.columns.values());style="grid-template-columns:"+" ".join(f"{float(c.width)*100}%" for c in cols)
        headers=''.join('<span>'+esc(h._text)+'</span>' for h in f.headings.values());rows=[]
        for b in f.rows.values():
            if not b.item or not b.IsShown(b):continue
            cells=''.join('<span>'+('□' if c.icon else esc(b.cells[i+1]._text))+'</span>' for i,c in enumerate(cols))
            selected=b.item.key=="step" if name=="tree" else b.item.path[len(b.item.path)]=="step"
            rows.append(f'<div class="gridrow {"selected" if selected else ""}" style="{style}">{cells}</div>')
        add(name,"panel grid",f'<div class="gridhead" style="{style}">{headers}</div>'+''.join(rows),parent)
    data=rect("diff" if view=="compare" else "dataPage")[:2]
    if view=="compare":
        add("diff","panel","")
        for n in ("leftTitle","rightTitle","leftPath","rightPath","diffTitle"):label(n,data)
        for n in ("leftPicker","rightPicker","swap","copyLeft","copyRight","copyAllLeft","copyAllRight"):control(n,data)
        add("diffSearch","input",esc(svc.diffSearch.placeholder._text),data);grid("diffList",data)
        for n in ("diffBefore","diffAfter"):add(n,"readbox",esc(svc[n].fullText),data)
    else:
        for n in ("search","charSearch"):add(n,"input",esc(svc[n].placeholder._text),data)
        for n in ("addonFilter","stateFilter","scopeFilter","reset","up","kindFilter","openButton","detailButton","compareButton"):control(n,data)
        for n in ("count","pathLabel","treeCount"):label(n,data)
        rows=''.join(f'<div class="navrow {"selected" if item.root=="APRData" else ""}"><b>{esc(item.root)}</b><small>{esc(item.addon)} · {esc(svc.FormatBytes(svc,item.bytes))}</small></div>' for item in svc.catalog["items"].values())
        add("catalog","panel list",rows,data);grid("tree",data)
        if svc.detail.IsShown(svc.detail):
            detail=add("detail","panel","",data)
            for n in ("detailTitle","detailPath","originalLabel","detailHint","newLabel"):label(n,detail)
            add("original","readbox",esc(svc.original.fullText),detail);add("editor","input",esc(svc.editor._text),detail)
            for n in ("editButton","deleteButton","detailClose"):control(n,detail)
    w,h=svc.frame.GetWidth(svc.frame),svc.frame.GetHeight(svc.frame)
    active_tab="data" if svc.activePage=="compare" else svc.activePage
    tabs=''.join(f'<div class="tab {"active" if key==active_tab else ""}" style="left:{float(button._point[2])}px">{esc(button.label._text)}</div>'
                 for key,button in sorted(svc.tabs.items(),key=lambda item: float(item[1]._point[2])))
    palette="--window:#09090b;--panel:#111116;--raised:#201e25;--text:#eee;--muted:#aaa5b0;--border:#38343e;--accent:#edc15b" if theme=="dark" else "--window:#f0eee6;--panel:#fffefa;--raised:#e4e1da;--text:#28262e;--muted:#66616b;--border:#c0bbb2;--accent:#8c590f"
    css='''*{box-sizing:border-box}body{margin:0;background:#171922;font:12px Segoe UI,sans-serif;color:var(--text)}.note{padding:12px 16px;color:#aaa;font-size:11px}.note a{margin-left:14px;color:#bddbff}.stage{position:relative;background:var(--window);color:var(--text);border:1px solid var(--border);margin:0 12px}.panel,.control,.input,.readbox,.label{position:absolute}.panel,.readbox{background:var(--panel);border:1px solid var(--border)}.control{background:var(--raised);border:1px solid var(--border);display:flex;align-items:center;justify-content:center;text-align:center;padding:3px 8px;overflow:hidden;white-space:nowrap}.arrow{position:absolute;right:8px;width:12px;height:12px;stroke:var(--text);fill:none;stroke-width:3}.disabled{opacity:.4}.input{border:1px solid var(--border);background:var(--panel);color:var(--muted);padding:5px 10px;overflow:hidden}.readbox{padding:8px;white-space:pre-wrap;overflow:hidden}.label{color:var(--muted);overflow:hidden;white-space:nowrap;line-height:1.4}.list{padding:5px}.navrow{height:48px;padding:8px 10px;overflow:hidden}.navrow b{font-weight:500;display:block}.navrow small{color:var(--muted);display:block;margin-top:5px}.selected{background:var(--raised);box-shadow:inset 2px 0 var(--accent)}.grid{padding:0 16px 0 5px}.gridhead,.gridrow{display:grid;align-items:center;height:30px}.gridhead{color:var(--muted);font-size:11px;border-bottom:1px solid var(--border)}.gridrow{border-bottom:1px solid var(--border)}.gridrow span,.gridhead span{padding:0 8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.gridrow span:nth-child(3){color:var(--muted)}.logo{position:absolute;left:16px;top:10px;width:40px;height:40px}.title{position:absolute;left:66px;top:12px;color:var(--accent);font-size:22px}.tagline{position:absolute;left:66px;top:39px;font-size:11px;color:var(--muted)}.tab{position:absolute;top:66px;height:26px;width:154px;display:grid;place-items:center;border:1px solid var(--border);background:var(--raised)}.tab.active{color:var(--accent);border-color:var(--accent)}.metrics{position:absolute;top:106px;left:16px;height:34px;border:1px solid var(--border);background:var(--panel);display:flex;align-items:center;gap:50px;padding:0 12px;color:var(--muted);font-size:11px}.metrics strong{margin-left:auto;color:var(--accent);font-weight:500}.foot{position:absolute;bottom:14px;left:16px;right:310px;color:var(--muted);line-height:1.4}'''
    note="Lua layout preview · sample data · substitute font · outside WoW" if locale=="enUS" else "Aperçu du layout Lua · données fictives · police de substitution · hors WoW"
    nav='' if locale=="enUS" else '<a href="addon-ui-data.html">Tables</a><a href="addon-ui-preview.html">Édition</a><a href="addon-ui-compare.html">Comparateur</a><a href="addon-ui-light.html">Clair</a>'
    language="en" if locale=="enUS" else "fr"
    page=f'''<!doctype html><html lang="{language}"><meta charset="utf-8"><title>SV Cleaner · {view}</title><style>{css}</style><div class="note">{note} {nav}</div><div class="stage" style="{palette};width:{w}px;height:{h}px"><img class="logo" src="addon-preview-logo.png"><div class="title">SV Cleaner</div><div class="tagline">{esc(svc.L.TAGLINE)}</div>{tabs}<div class="metrics" style="width:{w-32}px">{esc(svc.metric._text)}<span>{esc(svc.loadedCount._text)}</span><strong>{esc(svc.queueCount._text)}</strong></div>{''.join(chunks)}<div class="foot">{esc(svc.L.SELECT_TWO)}</div></div></html>'''
    output=ROOT/"output";output.mkdir(exist_ok=True)
    filename="addon-ui-light.html" if theme=="light" else "addon-ui-preview.html" if view=="route" else f"addon-ui-{view}.html"
    if locale=="enUS": filename=f"addon-ui-en-{view}.html"
    (output/filename).write_text(page,encoding="utf-8");shutil.copy2(ROOT/"Assets"/"logo.png",output/"addon-preview-logo.png");print(output/filename)


if __name__=="__main__":
    for view in ("data","route","compare"):render(view)
    render("route","light")
