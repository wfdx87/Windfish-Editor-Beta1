"""Native dungeon graphics assignments and their nonmodal settings window."""
from windfish.compatibility import api as profile

import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageTk
import windfish.rendering.windfish_dungeon_render as dungeon
import windfish.dungeon.windfish_dungeon_room_data as rooms
from windfish.rendering.windfish_sprite_graphics import graphics_source_offset

COLOR_SLOTS=(0x806AA,0x806D6,0x80702,0x8072E)
CONFIG_COUNT=0x81


def configuration_offset(map_id,room,data=None):
    rooms.sprite_index(map_id,room)
    if map_id==255:raise ValueError('Color rooms use four direct graphics slots instead of a configuration ID.')
    return profile.bank20_table(data,0x830DB)+(512 if dungeon.room_bank(map_id)=='B' else 256)+room


def configuration_changes(data,map_id,room,value):
    if map_id==0x10 and room==0xB5:raise ValueError('The camera shop forces configuration 3D in game code.')
    if not isinstance(value,int) or not 0<=value<CONFIG_COUNT:raise ValueError('Indoor sprite configuration must be 00–80.')
    at=configuration_offset(map_id,room,data)
    # Decode before offering a configuration whose slots point outside the ROM.
    for selector in data[profile.bank20_table(data,0x83643)+value*4:profile.bank20_table(data,0x83643)+value*4+4]:graphics_source_offset(data,selector)
    return [] if data[at]==value else [(at,data[at],value)]


def color_slot_changes(data,room,slot,page,bank):
    rooms.sprite_index(255,room)
    if slot not in range(4):raise ValueError('Sprite slot must be 0–3.')
    if not ((page==bank==0) or (isinstance(page,int) and isinstance(bank,int) and 0x40<=page<=0x7F and 1<=bank<0x80 and bank*0x4000+(page-0x40)*256+256<=len(data))):
        raise ValueError('Choose an existing graphics source, or Empty / inherited.')
    at=COLOR_SLOTS[slot]+room*2
    return [(at+i,data[at+i],v) for i,v in enumerate((page,bank)) if data[at+i]!=v]


def bg_selector_changes(data,map_id,room,value,sideview=False):
    rooms.sprite_index(map_id,room)
    if map_id==255 or sideview:raise ValueError('This room uses a special BG graphics loader.')
    if value not in (*range(0x30),255):raise ValueError('Indoor BG block must be 00–2F or FF (inherited).')
    at=profile.indoor_bg_table(data,dungeon.BG_SELECTORS)+(256 if dungeon.room_bank(map_id)=='B' else 0)+room
    return [] if data[at]==value else [(at,data[at],value)]


def source_choices(data):
    sources={(0,0)}
    for selector in range(1,255):
        at=graphics_source_offset(data,selector)
        if at is not None and at//0x4000:sources.add((0x40+(at%0x4000)//256,at//0x4000))
    for base in COLOR_SLOTS:
        for room in range(22):
            page,bank=data[base+room*2:base+room*2+2]
            if bank and 0x40<=page<=0x7F:sources.add((page,bank))
    return tuple(sorted(sources,key=lambda pair:(pair[1],pair[0])))


def graphics_sheet(raw,colors):
    image=Image.new('RGB',(128,128));pixels=image.load()
    for tile in range(256):
        at=(tile^128)*16
        for y in range(8):
            lo,hi=raw[at+y*2:at+y*2+2]
            for x in range(8):pixels[tile%16*8+x,tile//16*8+y]=colors[((lo>>(7-x))&1)|(((hi>>(7-x))&1)<<1)]
    return image


class DungeonGraphics(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.key=None;self.loading=False;self.target=None
        self.title('Room GFX Settings');self.geometry('780x600');self.resizable(False,False);self.transient(owner)
        self.protocol('WM_DELETE_WINDOW',self.close);owner.bind_history_shortcuts(self)
        self.heading=tk.StringVar();self.feedback=tk.StringVar()
        ttk.Label(self,textvariable=self.heading,font=('TkDefaultFont',11,'bold')).pack(anchor='w',padx=12,pady=10)
        tabs=ttk.Notebook(self);tabs.pack(fill='both',expand=True,padx=12)
        bg=ttk.Frame(tabs,padding=12);tabs.add(bg,text='BG')
        row=ttk.Frame(bg);row.pack(fill='x')
        ttk.Label(row,text='Room BG block (hex)').pack(side='left')
        self.bg_value=tk.StringVar();self.bg_combo=ttk.Combobox(row,textvariable=self.bg_value,state='readonly',width=7,values=[f'{v:02X}' for v in range(0x30)]+['FF'])
        self.bg_combo.pack(side='left',padx=8);self.bg_combo.bind('<<ComboboxSelected>>',self.change_bg)
        self.bg_info=tk.StringVar();ttk.Label(bg,textvariable=self.bg_info,wraplength=725,justify='left').pack(anchor='w',pady=10)
        pictures=ttk.Frame(bg);pictures.pack(anchor='w')
        self.bg_sheet=ttk.Label(pictures);self.bg_sheet.pack(side='left')
        ttk.Label(bg,text='Loaded 8×8 tiles using BG palette 0.\nFF inherits the previous room’s BG block; its preview uses block 00.',wraplength=715).pack(anchor='w',pady=10)
        sprites=ttk.Frame(tabs,padding=12);tabs.add(sprites,text='Sprites')
        controls=ttk.Frame(sprites);controls.pack(fill='x')
        ttk.Label(controls,text='Sprite configuration (hex)').pack(side='left')
        self.config=tk.StringVar();self.config_combo=ttk.Combobox(controls,textvariable=self.config,state='readonly',width=7,values=[f'{v:02X}' for v in range(CONFIG_COUNT)])
        self.config_combo.pack(side='left',padx=8);self.config_combo.bind('<<ComboboxSelected>>',self.change_config)
        self.sprite_sheet=ttk.Label(sprites);self.sprite_sheet.pack(anchor='w',pady=12)
        self.slot_vars=[];self.slot_combos=[];self.slot_sources=[]
        grid=ttk.Frame(sprites);grid.pack(anchor='w')
        for slot in range(4):
            ttk.Label(grid,text=f'Slot {slot} · OBJ {0x40+slot*16:02X}–{0x4F+slot*16:02X}').grid(row=slot,column=0,sticky='w',padx=(0,12),pady=4)
            value=tk.StringVar();self.slot_vars.append(value)
            combo=ttk.Combobox(grid,textvariable=value,width=25,state='disabled');combo.grid(row=slot,column=1,padx=4);self.slot_combos.append(combo)
            combo.bind('<<ComboboxSelected>>',lambda event,s=slot:self.change_slot(s))
            source=tk.StringVar();self.slot_sources.append(source);ttk.Label(grid,textvariable=source).grid(row=slot,column=2,sticky='w',padx=12)
        self.sprite_info=tk.StringVar();ttk.Label(sprites,textvariable=self.sprite_info,wraplength=710).pack(anchor='w',pady=12)
        ttk.Label(self,textvariable=self.feedback,wraplength=750).pack(anchor='w',padx=12,pady=10)
        self.refresh()

    def close(self):self.owner.graphics_window=None;self.destroy()
    @staticmethod
    def pair_label(pair):
        page,bank=pair
        return 'Empty / inherited' if not bank else f'Bank {bank:02X} · Page {page:02X}'
    def refresh(self):
        owner=self.owner
        if owner.data is None:
            self.target=None;self.key=None;self.heading.set('Open a ROM first.')
            for widget in (self.bg_combo,self.config_combo,*self.slot_combos):widget.configure(state='disabled')
            for widget in (self.bg_sheet,self.sprite_sheet):widget.configure(image='')
            return
        m,side=owner.render_context(owner.room);key=(owner._digest,m,owner.room,side)
        if key==self.key:return
        self.loading=True;self.key=key;self.target=(m,owner.room,side,owner.data)
        self.heading.set(f'Bank {dungeon.room_bank(m)} · Room {owner.room:02X} · Map context {m:02X}'+(' · Side-view' if side else ''))
        self.feedback.set('Changes apply immediately. Ctrl+Z / Ctrl+Y undo and redo; File → Save ROM keeps them.')
        try:self.refresh_bg(m,owner.room,side)
        except (ValueError,IndexError) as exc:self.bg_info.set(str(exc));self.bg_sheet.configure(image='')
        try:self.refresh_sprites(m,owner.room)
        except (ValueError,IndexError) as exc:self.sprite_info.set(str(exc));self.sprite_sheet.configure(image='')
        self.loading=False
    def refresh_bg(self,m,room,side):
        data=self.owner.data;record=dungeon.read_room(data,m,room);raw,selector,warnings=dungeon.graphics(data,record,side)
        self.bg_combo.configure(state='readonly' if m!=255 and not side else 'disabled');self.bg_value.set('' if selector is None else f'{selector:02X}')
        at=dungeon.palette_offset(data,m,side,room)
        if side:details=f'Side-view graphics ROM {0xB7000 if m==6 else 0xB7800:06X}; normal room BG block is bypassed.'
        elif m==255:details='Color Dungeon uses its dedicated BG tables and graphics loader.'
        else:
            floor=data[0x80589+m];wall=data[0x805A9+m];item=data[0x805CA+m]
            details=f'Context floor ROM {dungeon.bank_address(0x2D,floor*256):06X}; walls ROM {dungeon.bank_address(0x2D,wall*256):06X}; items ROM {dungeon.bank_address(0x32,item*256):06X}.'
        self.bg_info.set(details+f'\nBG palette record ROM {at:06X}. Context graphics and palettes are shared settings.\n'+' '.join(warnings))
        colors=dungeon.palette(data,m,side,room)
        sheet=graphics_sheet(raw,colors[:4])
        self.bg_photo=ImageTk.PhotoImage(sheet.resize((256,256),Image.Resampling.NEAREST));self.bg_sheet.configure(image=self.bg_photo)
    def refresh_sprites(self,m,room):
        data=self.owner.data;image,group,selectors,sources=rooms.sprite_graphics(data,m,room)
        forced=m==0x10 and room==0xB5
        self.config.set('' if group is None else f'{group:02X}');self.config_combo.configure(state='readonly' if m!=255 and not forced else 'disabled')
        self.sprite_photo=ImageTk.PhotoImage(image.resize((512,128),Image.Resampling.NEAREST));self.sprite_sheet.configure(image=self.sprite_photo)
        self.pairs=source_choices(data);labels=[self.pair_label(pair) for pair in self.pairs]
        for slot,at in enumerate(sources):
            self.slot_sources[slot].set('Empty / inherited' if at is None else f'ROM {at:06X}')
            self.slot_combos[slot].configure(values=labels if m==255 else (),state='readonly' if m==255 else 'disabled')
            self.slot_vars[slot].set(self.pair_label(selectors[slot]) if m==255 else f'Selector {selectors[slot]:02X}')
        self.sprite_info.set('Color rooms have four individually assigned sources.' if m==255 else 'The camera shop forces configuration 3D in game code.' if forced else 'Selecting a configuration changes this bank/room assignment; the shared configuration’s four sources stay intact. Empty slots may retain earlier graphics in game; previews use placeholders when unavailable.')
    def commit(self,operation):
        if self.loading or self.target is None:return
        m,room,side,data=self.target
        try:
            current,view=self.owner.render_context(self.owner.room)
            if data is not self.owner.data or (m,room,side)!=(current,self.owner.room,view):raise ValueError('Selected room changed. Refresh the graphics settings.')
            self.owner.apply_room_changes(operation(data,m,room,side))
        except (ValueError,IndexError) as exc:self.feedback.set(str(exc));self.key=None;return
        self.refresh()
    def change_config(self,event=None):self.commit(lambda data,m,room,side:configuration_changes(data,m,room,int(self.config.get(),16)))
    def change_bg(self,event=None):self.commit(lambda data,m,room,side:bg_selector_changes(data,m,room,int(self.bg_value.get(),16),side))
    def change_slot(self,slot):
        def operation(data,m,room,side):
            if m!=255:raise ValueError('Direct slot assignments apply only to Color rooms.')
            pair=next((p for p in self.pairs if self.pair_label(p)==self.slot_vars[slot].get()),None)
            if pair is None:raise ValueError('Choose an existing source.')
            return color_slot_changes(data,room,slot,*pair)
        self.commit(operation)
