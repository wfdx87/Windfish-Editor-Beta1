"""Overworld Select-map editor with existing shared location-name editing."""
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from pathlib import Path
from PIL import Image,ImageTk,ImageOps
from windfish.rom import windfish_world_map as maps,windfish_dialogue as dialogue


class WorldMapEditor(ttk.Frame):
    def __init__(self,owner,parent=None):
        super().__init__(parent or owner);self.owner=owner;self.room=owner.room;self.identity=None;self.target=None
        self.map_selection=None;self.sheet_selection=None;self.selection_start=None;self.selection_source=None
        self.stamp=None;self.paint_active=False;self.paint_last=None;self.selected_border=False
        root=ttk.Frame(self,padding=12);root.pack(fill='both',expand=True)
        left=ttk.Frame(root);left.grid(row=0,column=0,sticky='nw',padx=(0,16))
        self.map_canvas=tk.Canvas(left,width=480,height=432,highlightthickness=0);self.map_canvas.pack()
        self.map_canvas.bind('<ButtonPress-1>',lambda event:self.begin_selection(event,'map'))
        self.map_canvas.bind('<B1-Motion>',self.drag_selection)
        self.map_canvas.bind('<ButtonRelease-1>',self.end_selection)
        self.map_canvas.bind('<ButtonPress-3>',self.begin_paint)
        self.map_canvas.bind('<B3-Motion>',self.paint)
        self.map_canvas.bind('<ButtonRelease-3>',self.end_paint)
        ttk.Label(left,text='Left-drag on the map or tile sheet to select a rectangular stamp.\nRight-click/drag on the map to paint. Selected colors are inverted.',wraplength=480).pack(anchor='w',pady=6)
        self.border_enabled=tk.BooleanVar(value=False)
        ttk.Checkbutton(left,text='Enable Border Editing',variable=self.border_enabled,
                        command=self.toggle_border).pack(anchor='w')
        right=ttk.Frame(root);right.grid(row=0,column=1,sticky='nw')
        self.context=tk.StringVar();ttk.Label(right,textvariable=self.context).pack(anchor='w')
        self.sheet_canvas=tk.Canvas(right,width=256,height=128,highlightthickness=1);self.sheet_canvas.pack(pady=6)
        self.sheet_canvas.bind('<ButtonPress-1>',lambda event:self.begin_selection(event,'sheet'))
        self.sheet_canvas.bind('<B1-Motion>',self.drag_selection)
        self.sheet_canvas.bind('<ButtonRelease-1>',self.end_selection)
        self.sheet_canvas.bind('<Motion>',self.hover_tile)
        controls=ttk.Frame(right);controls.pack(anchor='w',pady=4)
        ttk.Label(controls,text='Tile ID (hex)').pack(side='left')
        self.tile=tk.StringVar();ttk.Entry(controls,textvariable=self.tile,width=5).pack(side='left',padx=5)
        self.palette=tk.StringVar(value='0')
        combo=ttk.Combobox(controls,textvariable=self.palette,values=tuple(range(8)),state='readonly',width=3)
        combo.bind('<<ComboboxSelected>>',self.change_brush)
        self.tile.trace_add('write',lambda *args:self.typed_tile())
        ttk.Separator(right).pack(fill='x',pady=8)
        self.owl_seen=tk.BooleanVar(value=True)
        ttk.Checkbutton(right,text='Preview owl reminder as unlocked',variable=self.owl_seen,command=lambda:self.refresh(force=True)).pack(anchor='w')
        self.name_info=tk.StringVar();ttk.Label(right,textvariable=self.name_info,wraplength=365,justify='left').pack(anchor='w',pady=6)
        self.text=tk.Text(right,width=44,height=7,wrap='none',undo=True)
        self.text.pack(fill='x')
        self.count=tk.StringVar();ttk.Label(right,textvariable=self.count,wraplength=365).pack(anchor='w')
        self.text.bind('<<Modified>>',self.modified)
        self.apply_name_button=ttk.Button(right,text='Apply Shared Name Text',command=self.apply_name)
        self.apply_name_button.pack(anchor='w',pady=5)
        ttk.Label(right,text='Edits affect every use of this dialogue. Existing text length limits apply.\nVWF padding/control tokens are editable text; preserve them as needed.',wraplength=365).pack(anchor='w')
        self.status=tk.StringVar(value='Apply changes the ROM buffer. File → Save ROM writes the file.')
        ttk.Label(root,textvariable=self.status,wraplength=860).grid(row=2,column=0,columnspan=2,sticky='w',pady=(5,0))
        self.bind('<<WindfishRoomChanged>>',lambda event:self.refresh())
        self.bind('<<WindfishRomChanged>>',lambda event:self.refresh(force=True))
        self.refresh(force=True)

    def close(self):
        self.end_paint()
        self.owner.catalog_windows.pop('world_map',None);self.destroy()

    def refresh(self,force=False):
        data=self.owner.data
        if data is None:return
        if self.identity!=id(data):
            self.identity=id(data);self.room=self.owner.room;self.target=None
            self.map_selection=None;self.sheet_selection=None;self.selection_start=None
            self.paint_active=False;self.paint_last=None
            self.border_enabled.set(False);self.selected_border=False
            offsets=maps.world_map_offsets(data)
            self.tile.set(f'{data[offsets["tiles"]+self.room]:02X}')
            self.palette.set(str(data[offsets['attributes']+self.room]&7))
            self.stamp=maps.capture_stamp(data,(self.room%16,self.room//16,self.room%16,self.room//16))
        try:
            offsets=maps.world_map_offsets(data)
            self.draw_map()
            self.context.set(f'Room {self.room:02X} · Map position ({self.room%16:X}, {self.room//16:X})')
            self.draw_sheet()
            if self.selected_border:
                self.context.set('Map border selection')
                self.name_info.set('Border tiles have no location name.')
                self.target=None;self.text.configure(state='disabled')
                self.apply_name_button.configure(state='disabled');self.count.set('')
                return
            self.text.configure(state='normal');self.apply_name_button.configure(state='normal')
            info=maps.location(data,self.room,self.owl_seen.get());index=info['dialogue']
            entries=dialogue.records(data);record=entries[index]
            aliases=[i for i,e in enumerate(entries) if e[0]==record[0]]
            uses=[r for r in range(256) if maps.location(data,r,self.owl_seen.get())['dialogue'] in aliases]
            condition='\nOwl reminder is conditional; unchecked preview shows the region fallback.' if info['conditional'] else ''
            self.name_info.set(f'Region block {info["region"]:02X} · Special code {info["code"]:02X} ({info["category"]})\nResolved dialogue {index:03X} · Used by {len(uses)} map cells in this preview.\nText pointer aliases: '+', '.join(f'{i:03X}' for i in aliases)+condition)
            target=(self.identity,self.room,index,record)
            if force or self.target!=target:
                self.target=target;decoded,self.ending=dialogue.decode(record[1],data)
                self.text.delete('1.0','end');self.text.insert('1.0',decoded);self.text.edit_reset();self.text.edit_modified(False)
                self.update_count()
        except (ValueError,IndexError) as exc:
            self.target=None;self.status.set(f'Map unavailable: {exc}')

    @staticmethod
    def inverted(image,rect,cell,origin=(0,0)):
        if rect is None:return image
        x0,y0,x1,y1=rect;ox,oy=origin
        box=(ox+x0*cell,oy+y0*cell,ox+(x1+1)*cell,oy+(y1+1)*cell)
        image.paste(ImageOps.invert(image.crop(box)),box[:2]);return image

    def draw_map(self):
        image=self.inverted(maps.render(self.owner.data),self.map_selection,8)
        self.map_canvas.photo=ImageTk.PhotoImage(image.resize((480,432),Image.Resampling.NEAREST))
        self.map_canvas.delete('all');self.map_canvas.create_image(0,0,anchor='nw',image=self.map_canvas.photo)

    def draw_sheet(self):
        try:
            image=maps.sheet(self.owner.data,int(self.palette.get()))
            self.inverted(image,self.sheet_selection,8)
            self.sheet_canvas.photo=ImageTk.PhotoImage(image.resize((256,128),Image.Resampling.NEAREST))
            self.sheet_canvas.delete('all');self.sheet_canvas.create_image(0,0,anchor='nw',image=self.sheet_canvas.photo)
        except (ValueError,IndexError):return

    def event_cell(self,event,source,clamp=False):
        if source=='map':
            x=event.x//24;y=event.y//24
            x0,y0,x1,y1=(0,0,19,17) if self.border_enabled.get() else (2,1,17,16)
        else:x=event.x//16;y=event.y//16;x0,y0,x1,y1=0,0,15,7
        if clamp:return max(x0,min(x1,x)),max(y0,min(y1,y))
        return (x,y) if x0<=x<=x1 and y0<=y<=y1 else None

    def begin_selection(self,event,source):
        self.end_paint()
        point=self.event_cell(event,source)
        if point is None:return
        self.selection_source=source;self.selection_start=point
        if source=='map':
            self.selected_border=not (2<=point[0]<18 and 1<=point[1]<17)
            if not self.selected_border:
                self.room=(point[1]-1)*16+point[0]-2
            self.sheet_selection=None;self.refresh(force=True)
        else:self.map_selection=None
        self.update_selection(point)

    def drag_selection(self,event):
        if self.selection_start is not None:
            self.update_selection(self.event_cell(event,self.selection_source,clamp=True))

    def end_selection(self,event):
        self.drag_selection(event);self.selection_start=None

    def update_selection(self,point):
        rect=maps.selection_rect(self.selection_start,point)
        if self.selection_source=='map':
            self.map_selection=rect;self.stamp=maps.capture_screen_stamp(self.owner.data,rect)
        else:
            self.sheet_selection=rect;x0,y0,x1,y1=rect;palette=int(self.palette.get())
            cells=tuple((maps.TILE_IDS[y*16+x],palette) for y in range(y0,y1+1) for x in range(x0,x1+1))
            self.stamp=(x1-x0+1,y1-y0+1,cells,False)
        self._syncing_brush=True
        self.tile.set(f'{self.stamp[2][0][0]:02X}')
        if self.selection_source=='map':self.palette.set(str(self.stamp[2][0][1]&7))
        self._syncing_brush=False
        self.draw_map();self.draw_sheet()
        self.status.set(f'{self.stamp[0]} × {self.stamp[1]} tile stamp selected. Right-click the map to draw.')

    def typed_tile(self):
        if getattr(self,'_syncing_brush',False):return
        # Entry edits explicitly choose a single tile. Empty intermediate input
        # leaves the last valid brush intact; refresh never resets that brush.
        try:
            tile=int(self.tile.get(),16);palette=int(self.palette.get())
            if tile not in maps.TILE_IDS:return
            self.stamp=(1,1,((tile,palette),),False)
            self.map_selection=None;pos=maps.TILE_IDS.index(tile)
            self.sheet_selection=(pos%16,pos//16,pos%16,pos//16)
            if self.owner.data is not None:self.draw_map();self.draw_sheet()
        except (ValueError,AttributeError):return

    def change_brush(self,event=None):
        if self.stamp is None:return
        width,height,cells,full=self.stamp;palette=int(self.palette.get())
        self.stamp=(width,height,tuple((tile,(attr&0xf8)|palette) for tile,attr in cells),full)
        self.draw_sheet()

    def hover_tile(self,event):
        point=self.event_cell(event,'sheet')
        if point is not None:self.status.set(f'Map tile {maps.TILE_IDS[point[1]*16+point[0]]:02X} · Left-drag to select; right-click map to draw.')

    def begin_paint(self,event):
        if self.event_cell(event,'map') is None:return
        self.owner.end_stroke();self.paint_active=True;self.paint_last=None;self.paint(event)

    def paint(self,event):
        if not self.paint_active or self.stamp is None:return
        point=self.event_cell(event,'map')
        if point is None or point==self.paint_last:return
        try:
            edits=maps.screen_stamp_changes(self.owner.data,*point,self.stamp,border_enabled=self.border_enabled.get())
            for at,old,new in edits:
                self.owner.history.record(at,old,new,self.owner.room,False);self.owner.data[at]=new
            self.paint_last=point;self.draw_map()
        except (ValueError,IndexError) as exc:
            self.end_paint();messagebox.showerror('Cannot draw map tiles',str(exc),parent=self)

    def end_paint(self,event=None):
        if not self.paint_active:return
        self.paint_active=False;self.paint_last=None
        self.owner.history.commit();self.owner.show_room();self.refresh()
        self.status.set('Map tiles drawn. Undo ROM restores the stroke; File → Save ROM writes the file.')

    def toggle_border(self):
        self.end_paint();self.map_selection=None;self.selection_start=None
        if not self.border_enabled.get():self.selected_border=False
        self.refresh(force=True)
        self.status.set('Border editing enabled.' if self.border_enabled.get() else 'Border editing disabled; only inner map cells can be painted.')

    def commit(self,edits):
        self.end_paint()
        owner=self.owner
        if not edits:return
        owner.end_stroke()
        for at,old,new in edits:
            if owner.data[at]!=old:raise ValueError('ROM data changed; reload before applying.')
        for at,old,new in edits:
            owner.history.record(at,old,new,owner.room,False);owner.data[at]=new
        owner.history.commit();owner.show_room();self.refresh()

    def modified(self,event=None):
        if self.text.edit_modified():self.text.edit_modified(False);self.update_count()

    def update_count(self):
        if self.target is None:return
        try:
            raw=dialogue.encode(self.text.get('1.0','end-1c'),self.ending,data=self.owner.data)
            self.count.set(f'{len(raw)} / {len(self.target[3][1])} bytes including ending')
        except ValueError as exc:self.count.set(str(exc))

    def apply_name(self):
        if self.target is None:return
        try:
            identity,room,index,record=self.target
            if identity!=id(self.owner.data) or self.owner.document is None:raise ValueError('The ROM changed; reload the map.')
            edits=dialogue.changes(self.owner.data,index,self.text.get('1.0','end-1c'),self.ending,expected=record)
            self.commit(edits);self.status.set(f'Shared dialogue {index:03X} applied. File → Save ROM writes the file.')
        except (ValueError,IndexError) as exc:messagebox.showerror('Cannot apply location name',str(exc),parent=self)

