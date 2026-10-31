"""Compact Room Properties presentation matching the overworld inspector."""
import tkinter as tk
from tkinter import ttk
from windfish.app.windfish_property_palettes import build_palette_view


class WarpTypeVar(tk.StringVar):
    def get(self):return super().get()[:2]
    def set(self,value):
        labels={'00':'00 — Overworld','01':'01 — Indoor','02':'02 — Side-view','03':'03 — Reserved'}
        super().set(labels.get(value,value))


class RecordList:
    """Keep guarded record identities while displaying the inspector's text list."""
    def __init__(self,page,formatter,height=8):
        self.master=page;self.formatter=formatter;self.ids=[];self.serial=0
        container=ttk.Frame(page);container.pack(fill='both',expand=True,pady=8)
        self.widget=tk.Listbox(container,font=('Consolas',10),exportselection=False,height=height)
        scroll=ttk.Scrollbar(container,command=self.widget.yview)
        self.widget.configure(yscrollcommand=scroll.set);self.widget.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
    def bind(self,key,callback):self.widget.bind('<<ListboxSelect>>' if key=='<<TreeviewSelect>>' else key,callback)
    def insert(self,parent,index,values):
        item=str(self.serial);self.serial+=1;self.ids.append(item);self.widget.insert('end',self.formatter(values));return item
    def get_children(self):return tuple(self.ids)
    def delete(self,item):
        i=self.ids.index(item);self.widget.delete(i);del self.ids[i]
    def selection(self):return tuple(self.ids[i] for i in self.widget.curselection())
    def selection_set(self,item):self.widget.selection_clear(0,'end');self.widget.selection_set(self.ids.index(item))
    def see(self,item):self.widget.see(self.ids.index(item))
    def selection_clear(self):self.widget.selection_clear(0,'end')


def build_properties(window):
    w=window
    w.title('Room Properties');w.geometry('560x620');w.minsize(300,320);w.transient(w.owner)
    if w.tk.call('tk','windowingsystem')=='win32':w.wm_attributes('-toolwindow',True)
    chest=ttk.Frame(w,padding=(12,8,12,0));chest.pack(fill='x')
    ttk.Label(chest,textvariable=w.heading).pack(side='left',padx=(0,8))
    w.chest_value=tk.StringVar();w.chest_combo=ttk.Combobox(chest,textvariable=w.chest_value,state='disabled',width=28)
    w.chest_combo.pack(side='left',fill='x',expand=True);w.chest_combo.bind('<<ComboboxSelected>>',w.change_chest)
    ttk.Label(w,text='A0 = chest graphics/object. One reward per room; layouts share it.',wraplength=440).pack(anchor='w',padx=12,pady=(4,0))
    tabs=ttk.Notebook(w);w.tabs=tabs;tabs.pack(fill='both',expand=True,padx=6,pady=6)
    collision=ttk.Frame(tabs,padding=8);tabs.add(collision,text='Collision Objects');w.general_page=collision
    ttk.Label(collision,textvariable=w.summary,wraplength=430).pack(anchor='w')
    # Retain dungeon header editing in a compact row rather than a separate tab.
    headers=ttk.Frame(collision);headers.pack(fill='x')
    for i,(name,var) in enumerate((name,var) for name,var in w.fields.items() if name!='Animation'):
        ttk.Label(headers,text={'Floor tile':'Floor','Wall template':'Walls','Animation':'Animation'}[name]).grid(row=0,column=i*2,padx=(0,3))
        combo=ttk.Combobox(headers,textvariable=var,state='disabled',width=3,values=[f'{v:02X}' for v in range(18 if name=='Animation' else 16)])
        combo.grid(row=0,column=i*2+1,padx=(0,8));combo.bind('<<ComboboxSelected>>',w.apply);w.controls.append(combo)
    w.objects=RecordList(collision,lambda r:f'{r[1]}  ID {r[2]}  X={r[3]} Y={r[4]}'+('' if r[5]=='Single' else f'  {r[5].lower()} ×{r[6]}'))
    w.objects.bind('<<TreeviewSelect>>',w.select_object);w.objects.bind('<Delete>',w.delete_object)
    ttk.Label(collision,text='Raw placements in ROM order. Macros are not expanded.\nWarps are listed separately. Clear all objects preserves them; Clear Room removes them.',wraplength=430).pack(anchor='w')
    fields=ttk.Frame(collision);fields.pack(fill='x',pady=4)
    w.place_fields={name:tk.StringVar() for name in ('X','Y','Length','Direction')};w.place_inputs=[]
    for i,(name,var) in enumerate(w.place_fields.items()):
        if name!='Direction':ttk.Label(fields,text=name).grid(row=0,column=i)
        widget=(ttk.Combobox(fields,textvariable=var,values=('Single','Horizontal','Vertical'),width=12,state='disabled') if name=='Direction' else ttk.Spinbox(fields,textvariable=var,from_=1 if name=='Length' else 0,to=15 if name=='Length' else 9 if name=='X' else 7,width=5,state='disabled'))
        widget.grid(row=1,column=i,padx=2);w.place_inputs.append(widget)
    # Collision ID editing remains available without adding another line of controls.
    ttk.Label(fields,text='ID (hex)').grid(row=0,column=4)
    w.object_combo=ttk.Combobox(fields,textvariable=w.object_id,values=[f'{v:02X}' for v in range(254)],width=3,state='disabled');w.object_combo.grid(row=1,column=4,padx=3)
    actions=ttk.Frame(collision);actions.pack(fill='x')
    ttk.Button(actions,text='Apply move / resize',command=lambda:w.edit_object(False)).pack(side='left')
    w.delete_button=ttk.Button(actions,text='Delete placement',command=w.delete_object,state='disabled');w.delete_button.pack(side='left',padx=6)
    ttk.Label(collision,textvariable=w.object_feedback,wraplength=430).pack(anchor='w',pady=4)
    ttk.Button(collision,text='Recalculate collisions',command=w.owner.calculate_collisions).pack(anchor='w',pady=(8,0))
    ttk.Button(collision,text='Clear all objects…',command=w.clear_objects).pack(anchor='w',pady=8)
    ttk.Button(collision,text='Clear Room…',command=w.clear_room).pack(anchor='w',pady=(0,8))
    ttk.Button(collision,text='Add Collisions…',command=w.owner.open_collision_selector).pack(anchor='w')
    ttk.Label(collision,textvariable=w.feedback,wraplength=430).pack(anchor='w')
    w.build_events(tabs)
    warp=ttk.Frame(tabs,padding=8);tabs.add(warp,text='Warps')
    w.warp_summary=tk.StringVar();ttk.Label(warp,textvariable=w.warp_summary,wraplength=430).pack(anchor='w')
    w.warps=RecordList(warp,lambda r:f'{int(r[0],16)+1}: {r[2]}  Map {r[3]} Room {r[4]}  X {r[5]} Y {r[6]}',height=7);w.warps.bind('<<TreeviewSelect>>',w.select_warp)
    fields=ttk.Frame(warp);fields.pack(fill='x');w.warp_vars={name:(WarpTypeVar() if name=='Type' else tk.StringVar()) for name in ('Type','Map','Room','X','Y')};w.warp_inputs=[];w.warp_feedback=tk.StringVar()
    for i,(name,var) in enumerate(w.warp_vars.items()):
        ttk.Label(fields,text={'Type':'Type','Map':'Destination map','Room':'Destination room','X':'Arrival X (pixels)','Y':'Arrival Y (pixels)'}[name]).grid(row=i,column=0,sticky='w',padx=(0,12),pady=3)
        widget=ttk.Combobox(fields,textvariable=var,values=('00 — Overworld','01 — Indoor','02 — Side-view'),width=22,state='disabled') if i==0 else ttk.Entry(fields,textvariable=var,width=8,state='disabled')
        widget.grid(row=i,column=1,sticky='w');w.warp_inputs.append(widget)
    ttk.Label(warp,text='All values are hexadecimal. X/Y are pixel positions.\nWarp order follows entrance order. Interior return warps are separate.',wraplength=430).pack(anchor='w',pady=8)
    ttk.Button(warp,text='Apply warp changes',command=w.edit_warp).pack(anchor='w')
    actions=ttk.Frame(warp);actions.pack(anchor='w',pady=(8,0));ttk.Button(actions,text='Add warp',command=w.add_warp).pack(side='left');ttk.Button(actions,text='Remove warp',command=w.remove_warp).pack(side='left',padx=8)
    ttk.Label(warp,textvariable=w.warp_feedback,wraplength=430).pack(anchor='w',pady=6)
    palette=ttk.Frame(tabs,padding=12);tabs.add(palette,text='Palettes');w.palette_canvas=build_palette_view(palette,w.paint_palettes)
    sprites=ttk.Frame(tabs,padding=8);tabs.add(sprites,text='Sprites')
    ttk.Label(sprites,text='Room sprite placements — select to preview').pack(anchor='w')
    w.sprites_table=RecordList(sprites,lambda r:f'{r[0]}  ({r[3]},{r[4]})  ID {r[1]} — {r[2]}');w.sprites_table.bind('<<TreeviewSelect>>',w.select_sprite)
    w.sprite_feedback=tk.StringVar();ttk.Label(sprites,textvariable=w.sprite_feedback,wraplength=400).pack(anchor='w')
    ttk.Label(sprites,text='Static sprite preview (decoded from opened ROM)',font=('TkDefaultFont',9,'bold')).pack(anchor='w',pady=(10,2))
    w.sprite_preview_label=ttk.Label(sprites);w.sprite_preview_label.pack(anchor='w');w.sprite_preview_status=tk.StringVar(value='Select a sprite to preview its graphics.')
    ttk.Label(sprites,textvariable=w.sprite_preview_status,wraplength=400).pack(anchor='w',pady=(2,6))
    sheet=ttk.Frame(tabs,padding=8);tabs.add(sheet,text='Sprite Tileset')
    ttk.Label(sheet,text='Room sprite graphics (raw 8x8 tiles; read-only)').pack(anchor='w',pady=(8,0))
    w.sprite_sheet=ttk.Label(sheet);w.sprite_sheet.pack(anchor='w',pady=4);w.sprite_graphics_info=tk.StringVar()
    ttk.Label(sheet,textvariable=w.sprite_graphics_info,justify='left',wraplength=420).pack(anchor='w')
    from windfish.app.windfish_music_page import MusicPage
    w.music_page = MusicPage(w.owner, tabs, indoor=True)
    from windfish.dungeon.windfish_dungeon_animation import DungeonAnimationPage
    w.animation_page=DungeonAnimationPage(w,tabs)
    w._extra_loading=True;w._warp_rows={};w._warp_key=None;w._sprite_rows={};w._sprite_expected=None
