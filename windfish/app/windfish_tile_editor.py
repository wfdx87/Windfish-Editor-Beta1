"""16x16 tile map editor with quadrant ID entry and per-piece attributes."""
import tkinter as tk
from tkinter import ttk,filedialog
from pathlib import Path
from PIL import Image,ImageTk
from windfish.rendering.windfish_overworld_render import render
from windfish.rom.windfish_room_tiles import (room_set,is_custom,changes_between,
    definition_offset,attribute_offset,tile_changes,assign_set,clear_set)


class TileEditorMixin:
    def tile_page_index(self):
        return int(hasattr(self,'map16_page') and self.map16_page.get().startswith('01'))

    def build_tile_page_control(self,parent):
        row=ttk.Frame(parent);row.pack(fill='x',pady=(0,8))
        ttk.Label(row,text='Map16 page').pack(side='left')
        combo=ttk.Combobox(row,textvariable=self.map16_page,
            values=('00 — Room tiles','01 — Additional tiles'),state='readonly',width=22)
        combo.pack(side='left',padx=6)
        combo.bind('<<ComboboxSelected>>',self.change_tile_page)
        return combo

    def change_tile_page(self,event=None):
        self.tile_selection=None
        self._tile_definition_selected=set()
        self._tile_definition_drag_anchor=None
        self.selected_tile.set((self.selected_tile.get()&255)+256*self.tile_page_index())
        callback=getattr(self,'_tile_catalog_update',None)
        if callback:callback()
        self.refresh_tile_definition_editor(force=True)
        self._refresh_selection_only()

    def definition_edit_changes(self,tile,pieces,attrs,behavior=None):
        from windfish.rom import windfish_shared_map16 as shared
        if tile>=256:return shared.definition_changes(self.data,tile,pieces,attrs,behavior,room=self.room)
        return tile_changes(self.data,self.room,tile,pieces,attrs)

    def save_gfx_table(self):
        if self.data is None:return
        from windfish.rom.windfish_gfx_table import export_table
        try:
            raw=export_table(self.data,self.room,page=self.tile_page_index())
            path=filedialog.asksaveasfilename(parent=getattr(self,'tile_editor_window',None) or self,title='Save GFX table',defaultextension='.gfx-table',initialfile=f'room_{self.room:02X}.gfx-table',filetypes=[('GFX table','*.gfx-table'),('All files','*')])
            if path:Path(path).write_bytes(raw)
        except (ValueError,OSError) as exc:
            from tkinter import messagebox
            messagebox.showerror('Save GFX table',str(exc),parent=self)

    def load_gfx_table(self):
        if self.data is None:return
        from windfish.rom.windfish_gfx_table import import_changes
        try:
            path=filedialog.askopenfilename(parent=getattr(self,'tile_editor_window',None) or self,title='Load GFX table',filetypes=[('GFX table','*.gfx-table'),('All files','*')])
            if not path:return
            raw=Path(path).read_bytes()
            changes,chosen=import_changes(self.data,self.room,raw,page=self.tile_page_index())
            self.commit_tile_definition_changes(changes)
        except (ValueError,OSError) as exc:
            from tkinter import messagebox
            messagebox.showerror('Load GFX table',str(exc),parent=self)

    def open_tile_definition_editor(self):
        old=getattr(self,'tile_editor_window',None)
        if old is not None and old.winfo_exists():old.deiconify();old.lift();return
        win=tk.Toplevel(self);self.tile_editor_window=win
        win.title('16x16 Tile Map Editor');win.resizable(False,False);win.transient(self)
        root=ttk.Frame(win,padding=12);root.pack(fill='both',expand=True)
        self.build_tile_page_control(root)
        self.tile_editor_info=tk.StringVar()
        ttk.Label(root,textvariable=self.tile_editor_info,wraplength=740).pack(anchor='w',pady=(0,8))
        body=ttk.Frame(root);body.pack(fill='both',expand=True)
        left=ttk.Frame(body,width=210);left.grid(row=0,column=0,sticky='nw',padx=(0,12))
        selection=ttk.Frame(left);selection.pack(anchor='w',pady=(0,8))
        ttk.Label(selection,text='16x16 tile ID').pack(side='left')
        self.tile_id_var=tk.StringVar(value='04')
        self._tile_definition_selected=set()
        self._tile_definition_drag_anchor=None
        self._tile_definition_scope=None
        self.tile_bulk_palette=tk.StringVar(value='0')
        self.tile_corner_buttons=[]
        valid=(win.register(lambda text:len(text)<=2 and all(c in '0123456789abcdefABCDEF' for c in text)),'%P')
        self.tile_id_entry=ttk.Entry(selection,textvariable=self.tile_id_var,width=5,validate='key',validatecommand=valid)
        self.tile_id_entry.pack(side='left',padx=6)
        self.tile_id_entry.bind('<Return>',self.select_tile_map_id)
        self.tile_id_entry.bind('<FocusOut>',self.select_tile_map_id)
        self.tile_definition_preview=ttk.Label(left)
        self.tile_definition_preview.pack(anchor='w',pady=(0,10))
        ttk.Label(left,text='8x8 tile IDs (hex)').pack(anchor='w')
        pieces=ttk.Frame(left);pieces.pack(anchor='w',pady=(4,10))
        self.tile_bank_fields=[tk.BooleanVar() for _ in range(5)]
        for var in self.tile_bank_fields:var.trace_add('write',lambda *args:self.paint_tile_definition_preview())
        self.tile_corner=tk.IntVar(value=0);self.tile_fields=[];self.tile_field_widgets=[]
        labels=('Top left','Top right','Bottom left','Bottom right')
        for i,label in enumerate(labels):
            piece=tk.StringVar();pal=tk.StringVar();fx=tk.BooleanVar();fy=tk.BooleanVar()
            self.tile_fields.append((piece,pal,fx,fy))
            cell=ttk.Frame(pieces);cell.grid(row=i//2,column=i%2,sticky='w',padx=(0,10),pady=3)
            radio=ttk.Radiobutton(cell,text=label,value=i,variable=self.tile_corner,command=self.select_tile_map_corner)
            radio.pack(anchor='w');self.tile_corner_buttons.append(radio)
            entry=ttk.Entry(cell,textvariable=piece,width=7,validate='key',validatecommand=valid)
            entry.pack(anchor='w');entry.bind('<FocusIn>',lambda event,corner=i:self.select_tile_map_corner(corner))
            self.tile_field_widgets.append(entry)
            for var in (piece,pal,fx,fy):var.trace_add('write',lambda *args:self.paint_tile_definition_preview())
        radio=ttk.Radiobutton(left,text='All',value=4,variable=self.tile_corner,command=self.select_tile_map_corner)
        radio.pack(anchor='w');self.tile_corner_buttons.append(radio)
        self.tile_all_fields=(tk.StringVar(value='0'),tk.BooleanVar(),tk.BooleanVar())
        self.tile_corner_label=ttk.Label(left,text='Top left attributes')
        self.tile_corner_label.pack(anchor='w')
        attributes=ttk.Frame(left);attributes.pack(anchor='w',pady=4)
        ttk.Label(attributes,text='BG palette').pack(side='left')
        self.tile_palette_selector=ttk.Combobox(attributes,textvariable=self.tile_fields[0][1],values=list(range(8)),width=3,state='readonly')
        self.tile_palette_selector.pack(side='left',padx=6)
        self.tile_palette_selector.bind('<<ComboboxSelected>>',lambda event:self.change_all_tile_attributes(0))
        self.tile_flip_x=ttk.Checkbutton(left,text='Flip X',variable=self.tile_fields[0][2],command=lambda:self.change_all_tile_attributes(1));self.tile_flip_x.pack(anchor='w')
        self.tile_flip_y=ttk.Checkbutton(left,text='Flip Y',variable=self.tile_fields[0][3],command=lambda:self.change_all_tile_attributes(2));self.tile_flip_y.pack(anchor='w')
        self.tile_bank_check=ttk.Checkbutton(left,text='Use VRAM bank 1',variable=self.tile_bank_fields[0],command=self.change_tile_bank)
        self.tile_bank_check.pack(anchor='w')
        self.tile_behavior=tk.StringVar(value='Walkable')
        ttk.Label(left,text='Shared tile behavior').pack(anchor='w',pady=(6,0))
        self.tile_behavior_combo=ttk.Combobox(left,textvariable=self.tile_behavior,
            values=('Walkable','Solid','Custom'),state='disabled',width=14)
        self.tile_behavior_combo.pack(anchor='w')
        self.tile_behavior_combo.bind('<<ComboboxSelected>>',self.change_selected_tile_behavior)
        self.tile_apply_button=ttk.Button(left,text='Apply tile definition',command=self.apply_tile_definition)
        self.tile_apply_button.pack(anchor='w',pady=(10,0))
        self.tile_copy_button=ttk.Button(left,text='Copy Tile',command=self.begin_copy_tile)
        self.tile_copy_button.pack(anchor='w',pady=(6,0))
        fill=ttk.Frame(left);fill.pack(anchor='w',pady=(6,0))
        self.tile_fill_button=ttk.Button(fill,text='Fill',command=self.fill_tile_definitions)
        self.tile_fill_button.pack(side='left')
        self.tile_fill_id=tk.StringVar(value='00')
        self.tile_fill_entry=ttk.Entry(fill,textvariable=self.tile_fill_id,width=5,validate='key',validatecommand=valid)
        self.tile_fill_entry.pack(side='left',padx=6)
        self.tile_fill_entry.bind('<Return>',self.fill_tile_definitions)
        ttk.Label(fill,text='8x8 ID (hex)').pack(side='left')
        self._tile_copy_target=None
        ttk.Button(left,text='Save GFX Table…',command=self.save_gfx_table).pack(anchor='w',pady=(12,2))
        ttk.Button(left,text='Load GFX Table…',command=self.load_gfx_table).pack(anchor='w')
        # 256 room metatiles in their original ID order; each 16x16 tile is
        # displayed at 2x. The four text fields mirror its quadrant positions.
        self.tile_piece_canvas=tk.Canvas(body,width=512,height=512,highlightthickness=1)
        self.tile_piece_canvas.grid(row=0,column=1,sticky='nw')
        self.tile_piece_canvas.bind('<Button-1>',self.pick_tile_definition_piece)
        self.tile_piece_canvas.bind('<B1-Motion>',self.drag_tile_definition_selection)
        self.tile_piece_canvas.bind('<ButtonRelease-1>',self.end_tile_definition_selection)
        ttk.Label(root,text='Drag to select a rectangle; Ctrl-click toggles tiles, Ctrl-drag adds, Shift-click extends.\nFor multiple tiles, BG palette changes all four pieces immediately. Fill sets all four 8x8 IDs; Undo/Redo is available.',wraplength=740).pack(anchor='w',pady=(8,0))
        self.tile_editor_status=tk.StringVar()
        ttk.Label(root,textvariable=self.tile_editor_status,wraplength=740).pack(anchor='w',pady=5)
        self._tile_editor_signature=None
        self.refresh_tile_definition_editor(force=True)

    def select_tile_map_id(self,event=None):
        """Commit a complete selection; blank intermediate input is harmless."""
        try:
            value=int(self.tile_id_var.get(),16)
            if not 0<=value<256:raise ValueError()
        except ValueError:
            self.tile_id_var.set(f'{(self._tile_editor_signature[2]&255) if self._tile_editor_signature else 4:02X}')
            return
        self.tile_id_var.set(f'{value:02X}')
        current=value+256*self.tile_page_index()
        previous=self._tile_editor_signature[2] if self._tile_editor_signature else None
        # Moving focus away from an unchanged ID entry must not collapse a
        # multi-selection before the palette/Fill control receives its click.
        if current!=previous or event is None or getattr(event,'keysym','') in ('Return','KP_Enter'):
            self._tile_definition_selected={current}
            self._tile_definition_anchor=value
        self.refresh_tile_definition_editor(force=True)

    def select_tile_map_corner(self,corner=None):
        if corner is not None:self.tile_corner.set(corner)
        index=self.tile_corner.get()
        if len(self.tile_definition_selection())>1:
            self.tile_palette_selector.configure(textvariable=self.tile_bulk_palette)
            self.tile_corner_label.configure(text=f'{len(self.tile_definition_selection())} tiles — all four palettes')
            self.paint_tile_definition_preview()
            return
        if index==4:
            pal,fx,fy=self.tile_all_fields
            for aggregate,source in zip(self.tile_all_fields,self.tile_fields[0][1:]):aggregate.set(source.get())
        else:_,pal,fx,fy=self.tile_fields[index]
        if index==4:self.tile_bank_fields[4].set(self.tile_bank_fields[0].get())
        self.tile_bank_check.configure(variable=self.tile_bank_fields[index])
        self.tile_palette_selector.configure(textvariable=pal)
        self.tile_flip_x.configure(variable=fx);self.tile_flip_y.configure(variable=fy)
        self.tile_corner_label.configure(text=('Top left','Top right','Bottom left','Bottom right','All four tiles')[index]+' attributes')
        self.paint_tile_definition_preview()

    def change_tile_bank(self):
        if self.tile_corner.get()==4:
            self._tile_editor_loading=True
            for var in self.tile_bank_fields[:4]:var.set(self.tile_bank_fields[4].get())
            self._tile_editor_loading=False
        self.paint_tile_definition_preview()

    def change_all_tile_attributes(self,field):
        """Only the control the user changed is broadcast; mixed fields survive."""
        if field==0 and len(self.tile_definition_selection())>1:
            self.apply_selected_tile_palettes()
            return
        if self.tile_corner.get()!=4:return
        self._tile_editor_loading=True
        try:
            for fields in self.tile_fields:fields[field+1].set(self.tile_all_fields[field].get())
        finally:self._tile_editor_loading=False
        self.paint_tile_definition_preview()

    def begin_copy_tile(self):
        if self.data is None:return
        if len(self.tile_definition_selection())>1:
            self.tile_editor_status.set('Select one target tile before using Copy Tile.');return
        if not self.tile_page_index() and not is_custom(self.data,self.room):
            self.tile_editor_status.set('Select a custom 16x16 set before copying.');return
        self._tile_copy_target=(self.room,int(self.tile_id_var.get(),16)+256*self.tile_page_index())
        self.tile_editor_status.set('Click the source tile in the map to copy its four IDs and attributes into the selected tile. Collision data stays unchanged.')

    def refresh_tile_definition_editor(self,force=False):
        win=getattr(self,'tile_editor_window',None)
        if win is None or not win.winfo_exists():return
        if self.data is None:
            self.tile_editor_info.set('Open a ROM first.');return
        try:tile=int(self.tile_id_var.get(),16)
        except ValueError:return
        if not 0<=tile<256:return
        tile+=256*self.tile_page_index()
        room=self.room;assigned=room_set(self.data,room)
        scope=(id(self.data),room,assigned,self.tile_page_index())
        if getattr(self,'_tile_definition_scope',None)!=scope:
            self._tile_definition_selected={tile}
            self._tile_definition_anchor=tile&255
            self._tile_definition_drag_anchor=None
            self._tile_definition_scope=scope
        elif not self.tile_definition_selection():self._tile_definition_selected={tile}
        multiple=len(self.tile_definition_selection())>1
        from windfish.rom import windfish_shared_map16 as shared_page
        at,attr=shared_page.locations(self.data,room,tile)
        behavior=self.data[shared_page.BEHAVIORS+(tile&255)] if tile>=256 else None
        signature=(room,assigned,tile,bytes(self.data[at:at+4]),bytes(self.data[attr:attr+4]),behavior)
        if not force and signature==self._tile_editor_signature:
            self.paint_tile_definition_preview();return
        self._tile_editor_signature=signature
        active=tile>=256 or is_custom(self.data,room)
        shared=sum(room_set(self.data,r)==assigned for r in range(256)) if active else 0
        if tile>=256:
            from windfish.rom import windfish_room_map16 as room_tables
            chosen=room_tables.room_set(self.data,room)
            name=f'table {chosen:02X}' if chosen else 'global table'
            count=room_tables.users(self.data,chosen) if chosen else sum(room_tables.room_set(self.data,r)==0 for r in range(256))
            self.tile_editor_info.set(f'Room {room:02X}, page 1 {name} — artwork has {count} room/page assignment(s). Behaviors remain global. Appearance uses this room’s graphics.')
        else:
            self.tile_editor_info.set(f'Room {room:02X} — '+(f'custom set {assigned:02X}, shared by {shared} room(s). Editing changes all of them.' if active else 'original definitions.'))
        self.tile_behavior_combo.configure(state='readonly' if tile>=256 else 'disabled')
        if tile>=256:
            behaviors={self.data[shared_page.BEHAVIORS+(selected&255)] for selected in self.tile_definition_selection()}
            self.tile_behavior.set({0:'Solid',2:'Walkable',3:'Custom'}.get(next(iter(behaviors)),'Solid') if len(behaviors)==1 else 'Mixed')
        self.tile_apply_button.configure(state='normal' if active and not multiple else 'disabled')
        self.tile_copy_button.configure(state='normal' if active and not multiple else 'disabled')
        self.tile_fill_button.configure(state='normal' if active else 'disabled')
        self.tile_fill_entry.configure(state='normal' if active else 'disabled')
        for widget in self.tile_corner_buttons:widget.configure(state='disabled' if multiple else 'normal')
        if multiple:
            colors=set()
            for selected in self.tile_definition_selection():
                _,offset=shared_page.locations(self.data,room,selected)
                colors.update(value&7 for value in self.data[offset:offset+4])
            self.tile_bulk_palette.set(str(next(iter(colors))) if len(colors)==1 else 'Mixed')
        self._tile_editor_loading=True
        for i,(piece,pal,fx,fy) in enumerate(self.tile_fields):
            self.tile_bank_fields[i].set(bool(self.data[attr+i]&8))
            value=self.data[attr+i];piece.set(f'{self.data[at+i]:02X}');pal.set(str(value&7));fx.set(bool(value&32));fy.set(bool(value&64))
        for widget in self.tile_field_widgets:widget.configure(state='normal' if active and not multiple else 'disabled')
        self.tile_palette_selector.configure(state='readonly' if active else 'disabled')
        for widget in (self.tile_flip_x,self.tile_flip_y):widget.configure(state='normal' if active and not multiple else 'disabled')
        self.tile_bank_check.configure(state='normal' if active and not multiple else 'disabled')
        self._tile_editor_loading=False
        self.select_tile_map_corner()

    def build_room_graphics_controls(self,root,bank1_root):
        row=ttk.Frame(root);row.pack(fill='x',pady=3)
        ttk.Label(row,text='16×16 Tileset').pack(side='left')
        self.tile_set_var=tk.StringVar()
        self.tile_set_combo=ttk.Combobox(row,textvariable=self.tile_set_var,width=16,state='readonly')
        self.tile_set_combo.pack(side='left',padx=6)
        self.tile_set_combo.bind('<<ComboboxSelected>>',self.assign_tile_definition_set)
        self.tile_clear_button=ttk.Button(row,text='Clear selected set',command=self.clear_tile_definition_set)
        self.tile_clear_button.pack(side='left',padx=6)
        ttk.Label(root,text='Sets 40–FF are always selectable. An unused set copies this room on first selection.\nClear sets all pieces and palette/flip attributes to 00; it affects every room sharing that set.',wraplength=550).pack(anchor='w')
        self.room_tile_set_info=tk.StringVar()
        ttk.Label(root,textvariable=self.room_tile_set_info,wraplength=550).pack(anchor='w',pady=3)
        ttk.Separator(root).pack(fill='x',pady=3)
        self.custom_bg_var=tk.BooleanVar()
        self.custom_bg_check=ttk.Checkbutton(root,text='Enable VRAM0 GFX Override',variable=self.custom_bg_var,command=self.apply_custom_bg_slots)
        self.custom_bg_check.pack(anchor='w',pady=5)
        self.custom_bg_slots=[];self.custom_bg_combos=[]
        for i in range(4):
            row=ttk.Frame(root);row.pack(fill='x',pady=3)
            ttk.Label(row,text=f'Slot {i+1} — tiles {i*32:02X}–{i*32+31:02X}',width=26).pack(side='left')
            var=tk.StringVar();self.custom_bg_slots.append(var)
            combo=ttk.Combobox(row,textvariable=var,state='readonly',width=20)
            combo.pack(side='left',fill='x',expand=True);combo.bind('<<ComboboxSelected>>',self.apply_custom_bg_slots)
            self.custom_bg_combos.append(combo)
        ttk.Label(root,text='Choose inserted ExGFX IDs, or Original to keep that slot’s normal graphics.\nInsert/update files in Extraction/Insert GFX. IDs are hexadecimal.',wraplength=550).pack(anchor='w',pady=3)
        self.bank1_enabled=tk.BooleanVar()
        ttk.Checkbutton(bank1_root,text='Enable additional VRAM bank 1 graphics (experimental)',variable=self.bank1_enabled,command=self.apply_bank1_slots).pack(anchor='w')
        row=ttk.Frame(bank1_root);row.pack(fill='x',pady=(6,3))
        ttk.Label(row,text='16×16 table (Map16 page 1)',width=26).pack(side='left')
        self.bank1_map16_set=tk.StringVar(value='Global')
        self.bank1_map16_combo=ttk.Combobox(row,textvariable=self.bank1_map16_set,
            values=('Global',)+tuple(f'{i:02X}' for i in range(0x40,256)),state='readonly',width=20)
        self.bank1_map16_combo.pack(side='left',fill='x',expand=True)
        self.bank1_map16_combo.bind('<<ComboboxSelected>>',self.assign_bank1_map16_set)
        ttk.Label(bank1_root,text='Select an unused table to copy the current layout. Rooms using the same table share edits. Page 1 collision behaviors remain global.',wraplength=550).pack(anchor='w',pady=3)
        self.bank1_slots=[];self.bank1_combos=[]
        for i in range(8):
            row=ttk.Frame(bank1_root);row.pack(fill='x',pady=3)
            ttk.Label(row,text=f'Bank 1 — tiles {i*32:02X}–{i*32+31:02X}',width=26).pack(side='left')
            var=tk.StringVar(value='Blank');self.bank1_slots.append(var)
            combo=ttk.Combobox(row,textvariable=var,state='readonly',width=20)
            combo.pack(side='left',fill='x',expand=True);combo.bind('<<ComboboxSelected>>',self.apply_bank1_slots)
            self.bank1_combos.append(combo)
        ttk.Label(bank1_root,text='Uses the same inserted ExGFX library. In the 16x16 Tile Map Editor, enable VRAM bank 1 for the desired corners. All bank 1 tile IDs 00–FF are supported.',wraplength=550).pack(anchor='w',pady=3)
        self.tile_graphics_info=tk.StringVar()
        ttk.Label(root,textvariable=self.tile_graphics_info,wraplength=550).pack(anchor='w',pady=3)

    def build_graphics_transfer_controls(self,root):
        ttk.Label(root,text='Extract from the current room',font=('TkDefaultFont',10,'bold')).pack(anchor='w',pady=(0,8))
        self.graphics_extract_checks=[];self.graphics_extract_ids=[]
        for i in range(4):
            row=ttk.Frame(root);row.pack(fill='x',pady=3)
            check=tk.BooleanVar(value=True);self.graphics_extract_checks.append(check)
            ttk.Checkbutton(row,text=f'{i*32:02X}–{i*32+31:02X}',variable=check,width=12).pack(side='left')
            ttk.Label(row,text='Export as exgfx_').pack(side='left')
            var=tk.StringVar(value=f'{i:02X}');self.graphics_extract_ids.append(var)
            ttk.Entry(row,textvariable=var,width=4).pack(side='left')
            ttk.Label(row,text='.bin').pack(side='left')
        ttk.Button(root,text='Extract selected blocks…',command=self.export_room_graphics_blocks).pack(anchor='w',pady=3)
        ttk.Label(root,text='Each checked range exports 32 raw Game Boy 2bpp tiles (512 bytes).\nEdit the files in YY-CHR. The two-digit file ID can be 00–FF.',wraplength=550).pack(anchor='w')
        ttk.Separator(root).pack(fill='x',pady=10)
        ttk.Label(root,text='Insert / update the reusable graphics library',font=('TkDefaultFont',10,'bold')).pack(anchor='w',pady=(0,8))
        ttk.Button(root,text='Insert exgfx_XX.bin files…',command=self.insert_exgfx_files).pack(anchor='w',pady=5)
        ttk.Label(root,text='The filename assigns the ID: exgfx_00.bin through exgfx_FF.bin.\nInsert once, then reuse the ID in any room’s four BG slots. Reinserting an existing ID updates every room that uses it. A 2 MiB ROM is required.',wraplength=550).pack(anchor='w',pady=3)
        self.exgfx_library_info=tk.StringVar()
        ttk.Label(root,textvariable=self.exgfx_library_info,wraplength=550).pack(anchor='w',pady=3)
        self._graphics_extract_room=None

    def refresh_room_graphics_controls(self):
        if self.data is None:return
        from windfish.rom.windfish_room_graphics import custom,version as graphics_version,available_assets,room_slots
        assigned=room_set(self.data,self.room);active=is_custom(self.data,self.room)
        shared=sum(room_set(self.data,r)==assigned for r in range(256)) if active else 0
        self.room_tile_set_info.set(f'Set {assigned:02X}: shared by {shared} room(s). Editing/Clear changes all of them.' if active else 'Original 16×16 definitions.')
        self.tile_set_combo.configure(values=['00 — Original']+[f'{i:02X}' for i in range(0x40,256)],state='readonly')
        self.tile_set_var.set(f'{assigned:02X}' if active else '00 — Original')
        self.tile_clear_button.configure(state='normal' if active else 'disabled')
        ver=graphics_version(self.data);assets=available_assets(self.data);slots=room_slots(self.data,self.room)
        enabled=custom(self.data,self.room);self.custom_bg_var.set(enabled)
        self.custom_bg_check.configure(state='normal')
        for i,(combo,var,asset) in enumerate(zip(self.custom_bg_combos,self.custom_bg_slots,slots)):
            combo.configure(values=['Original']+[f'{a:02X}' for a in assets],state='readonly' if enabled and ver>=2 else 'disabled')
            var.set('Original' if asset is None else f'{asset:02X}')
        from windfish.rom import windfish_vram_bank1 as bank1
        bank1_active=bank1.enabled(self.data,self.room);self.bank1_enabled.set(bank1_active)
        from windfish.rom import windfish_room_map16 as room_tables
        selected=room_tables.room_set(self.data,self.room)
        self.bank1_map16_set.set(f'{selected:02X}' if selected else 'Global')
        self.bank1_map16_combo.configure(state='readonly' if room_tables.enabled(self.data) else 'disabled')
        for combo,var,asset in zip(self.bank1_combos,self.bank1_slots,bank1.room_slots(self.data,self.room)):
            combo.configure(values=['Blank']+[f'{a:02X}' for a in assets],state='readonly' if bank1_active else 'disabled')
            var.set('Blank' if asset is None else f'{asset:02X}')
        self.tile_graphics_info.set(f'Room {self.room:02X}: '+('custom BG enabled.' if enabled else 'original BG enabled.'))
        self.exgfx_library_info.set(f'{len(assets)} / 256 ExGFX IDs inserted.')
        if self._graphics_extract_room!=self.room:
            for i,var in enumerate(self.graphics_extract_ids):var.set(f'{slots[i] if enabled and slots[i] is not None else i:02X}')
            self._graphics_extract_room=self.room

    def proposed_tile_definition(self):
        tile=int(self.tile_id_var.get(),16)+256*self.tile_page_index()
        from windfish.rom.windfish_shared_map16 import locations
        _,attr=locations(self.data,self.room,tile)
        pieces=[];attrs=[]
        for i,(piece,pal,fx,fy) in enumerate(self.tile_fields):
            value=int(piece.get(),16);color=int(pal.get())
            if not 0<=value<=255 or not 0<=color<8:raise ValueError('Use tile IDs 00-FF and palettes 0-7.')
            pieces.append(value);attrs.append((self.data[attr+i]&0x90)|(8 if self.tile_bank_fields[i].get() else 0)|color|(32 if fx.get() else 0)|(64 if fy.get() else 0))
        return tile,pieces,attrs

    def paint_tile_definition_preview(self):
        if self.data is None or not hasattr(self,'tile_definition_preview') or getattr(self,'_tile_editor_loading',False):return
        try:
            tile,pieces,attrs=self.proposed_tile_definition()
            trial=self.data
            if tile>=256 or is_custom(self.data,self.room):
                trial=bytearray(self.data)
                for at,b,a in self.definition_edit_changes(tile,pieces,attrs):trial[at]=a
            atlas=render(trial,self.room,scale=1)[1]
            sample=atlas.crop((tile%16*16,tile//16*16,tile%16*16+16,tile//16*16+16)).resize((96,96),Image.Resampling.NEAREST)
            page=self.tile_page_index();atlas=atlas.crop((0,page*256,256,page*256+256))
            self.tile_definition_preview.photo=ImageTk.PhotoImage(sample);self.tile_definition_preview.configure(image=self.tile_definition_preview.photo)
            self.tile_piece_canvas.photo=ImageTk.PhotoImage(atlas.resize((512,512),Image.Resampling.NEAREST))
            self.tile_piece_canvas.delete('all');self.tile_piece_canvas.create_image(0,0,anchor='nw',image=self.tile_piece_canvas.photo)
            self.draw_tile_definition_selection()
        except (ValueError,IndexError,tk.TclError):return

    def pick_tile_definition_piece(self,event):
        """Select a 16x16 definition from the atlas, including original sets."""
        if self.data is None:return
        if 0<=event.x<512 and 0<=event.y<512:
            source=event.y//32*16+event.x//32+256*self.tile_page_index()
            target=getattr(self,'_tile_copy_target',None)
            self._tile_copy_target=None
            if target is not None:
                if target[0]!=self.room:
                    self.tile_editor_status.set('Room changed; choose Copy Tile again.');return
                from windfish.rom.windfish_shared_map16 import locations
                at,attr=locations(self.data,self.room,source)
                try:
                    self.commit_tile_definition_changes(self.definition_edit_changes(target[1],
                        list(self.data[at:at+4]),list(self.data[attr:attr+4])))
                    self.tile_editor_status.set(f'Tile {source:02X} copied to {target[1]:02X}. Undo/Redo available.')
                except ValueError as exc:self.tile_editor_status.set(str(exc))
                return
            previous=self.tile_definition_selection()
            state=getattr(event,'state',0);control=bool(state&4);shift=bool(state&1)
            anchor=getattr(self,'_tile_definition_anchor',source&255) if shift else source&255
            rectangle=self.tile_definition_rectangle(anchor,source&255)
            if shift:selected=previous|rectangle if control else rectangle
            elif control:
                selected=previous^{source}
                if not selected:selected={source}
            else:selected={source}
            self._tile_definition_selected=selected
            self._tile_definition_anchor=anchor
            self._tile_definition_drag_anchor=anchor
            self._tile_definition_drag_base=previous if control else set()
            self._tile_definition_drag_last=source&255
            primary=source if source in selected else min(selected)
            self.tile_id_var.set(f'{primary&255:02X}')
            self.refresh_tile_definition_editor(force=True)

    def tile_definition_selection(self):
        """Selection is page-local; the ID entry remains the primary preview."""
        page=self.tile_page_index()
        selected={t for t in getattr(self,'_tile_definition_selected',set()) if t//256==page}
        if selected:return selected
        try:return {int(self.tile_id_var.get(),16)+256*page}
        except ValueError:return set()

    def tile_definition_rectangle(self,start,end):
        x0,x1=sorted((start%16,end%16));y0,y1=sorted((start//16,end//16))
        page=256*self.tile_page_index()
        return {page+y*16+x for y in range(y0,y1+1) for x in range(x0,x1+1)}

    def draw_tile_definition_selection(self):
        canvas=getattr(self,'tile_piece_canvas',None)
        if canvas is None:return
        canvas.delete('definition-selection')
        for tile in sorted(self.tile_definition_selection()):
            x=tile%16*32;y=(tile&255)//16*32
            canvas.create_rectangle(x+1,y+1,x+31,y+31,outline='yellow',width=2,tags='definition-selection')

    def drag_tile_definition_selection(self,event):
        anchor=getattr(self,'_tile_definition_drag_anchor',None)
        if anchor is None:return
        x=max(0,min(511,event.x));y=max(0,min(511,event.y));cell=y//32*16+x//32
        if cell==getattr(self,'_tile_definition_drag_last',None):return
        self._tile_definition_drag_last=cell
        self._tile_definition_selected=self._tile_definition_drag_base|self.tile_definition_rectangle(anchor,cell)
        # Only redraw outlines while dragging; no ROM copies or atlas decoding.
        self.draw_tile_definition_selection()

    def end_tile_definition_selection(self,event=None):
        if getattr(self,'_tile_definition_drag_anchor',None) is None:return
        self._tile_definition_drag_anchor=None
        selected=self.tile_definition_selection()
        primary=int(self.tile_id_var.get(),16)+256*self.tile_page_index()
        if selected and primary not in selected:self.tile_id_var.set(f'{min(selected)&255:02X}')
        self.refresh_tile_definition_editor(force=True)
        self.tile_editor_status.set(f'{len(selected)} tile(s) selected. Palette, behavior and Fill changes are one Undo step each.')

    def selected_definition_changes(self,*,palette=None,fill=None,behavior=None):
        """Build one atomic edit without copying any primary tile attributes.

        Bulk operations retain each target's flips, bank, priority and shared
        behavior unless explicitly changed. Validate the combined undo stroke.
        """
        from windfish.rom.windfish_shared_map16 import locations
        if behavior is not None and (behavior not in (0,2,3) or not self.tile_page_index()):
            raise ValueError('Behavior editing is available for shared page 1 tiles only.')
        if palette is not None and not 0<=palette<=7:raise ValueError('Use BG palettes 0-7.')
        if fill is not None and not 0<=fill<=255:raise ValueError('Use an 8x8 tile ID from 00-FF.')
        if not self.tile_page_index() and not is_custom(self.data,self.room):
            raise ValueError('Select a custom 16x16 set before editing its definitions.')
        selected=self.tile_definition_selection()
        if not selected:raise ValueError('Select one or more 16x16 tiles.')
        changes=[]
        for tile in sorted(selected):
            at,attr=locations(self.data,self.room,tile)
            pieces=list(self.data[at:at+4]) if fill is None else [fill]*4
            attrs=list(self.data[attr:attr+4])
            if palette is not None:attrs=[(value&0xF8)|palette for value in attrs]
            changes.extend(self.definition_edit_changes(tile,pieces,attrs,behavior))
        return changes

    def change_selected_tile_behavior(self,event=None):
        """Single tiles use Apply; bulk changes commit as one undo stroke."""
        if self.document is None or len(self.tile_definition_selection())<2:return
        try:
            name=self.tile_behavior.get()
            behavior={'Solid':0,'Walkable':2,'Custom':3}.get(name)
            if behavior is None:raise ValueError('Choose Solid, Walkable or Custom.')
            count=len(self.tile_definition_selection())
            self.commit_tile_definition_changes(self.selected_definition_changes(behavior=behavior))
            self.tile_editor_status.set(f'{name} behavior applied to {count} shared tile(s). Undo/Redo available.')
        except ValueError as exc:self.tile_editor_status.set(str(exc))

    def apply_selected_tile_palettes(self):
        if self.document is None:return
        try:
            palette=int(self.tile_bulk_palette.get())
            count=len(self.tile_definition_selection())
            self.commit_tile_definition_changes(self.selected_definition_changes(palette=palette))
            self.tile_editor_status.set(f'Palette {palette} applied to all four pieces of {count} tile(s). Undo/Redo available.')
        except ValueError as exc:self.tile_editor_status.set(str(exc))

    def fill_tile_definitions(self,event=None):
        if self.document is None:return
        try:
            try:value=int(self.tile_fill_id.get(),16)
            except ValueError:raise ValueError('Enter an 8x8 tile ID from 00-FF.') from None
            count=len(self.tile_definition_selection())
            changes=self.selected_definition_changes(fill=value)
            self.commit_tile_definition_changes(changes)
            self.tile_fill_id.set(f'{value:02X}')
            self.tile_editor_status.set(f'Filled all four pieces of {count} tile(s) with 8x8 ID {value:02X}. Undo/Redo available.')
        except ValueError as exc:self.tile_editor_status.set(str(exc))

    def commit_tile_definition_changes(self,changes):
        self.commit_collision_changes(changes,self.room,False)
        self.refresh_tile_definition_editor(force=True)

    def clear_tile_definition_set(self):
        if self.document is None:return
        try:
            selected=room_set(self.data,self.room)
            if not selected:raise ValueError('Select a custom 16×16 set first.')
            self.commit_tile_definition_changes(clear_set(self.data,selected))
            self.room_graphics_status.set(f'Set {selected:02X} cleared for every room sharing it. Undo/Redo available.')
        except ValueError as exc:self.room_graphics_status.set(str(exc))

    def apply_tile_definition(self):
        if self.document is None:return
        if len(self.tile_definition_selection())>1:
            self.tile_editor_status.set('Use BG palette, shared behavior or Fill for a multiple-tile selection.');return
        try:
            tile,pieces,attrs=self.proposed_tile_definition()
            changes=self.definition_edit_changes(tile,pieces,attrs,{'Walkable':2,'Solid':0,'Custom':3}[self.tile_behavior.get()]);self.commit_tile_definition_changes(changes)
            self.tile_editor_status.set(f'Page-1 tile {tile:03X} updated in this room’s assigned table. Behavior remains global.' if tile>=256 else f'Tile {tile:02X} updated for room {self.room:02X}. Collision data unchanged.')
        except ValueError as exc:self.tile_editor_status.set(str(exc))

    def assign_tile_definition_set(self,event=None):
        if self.document is None:return
        try:
            set_id=int(self.tile_set_var.get().split()[0],16)
            changes=assign_set(self.data,self.room,set_id)
            self.commit_tile_definition_changes(changes)
            self.room_graphics_status.set('Room set assignment updated. Collision data unchanged.')
        except ValueError as exc:self.room_graphics_status.set(str(exc));self.refresh_room_graphics_controls()

    def apply_bank1_slots(self,event=None):
        if self.document is None:return
        from windfish.rom import windfish_vram_bank1 as bank1
        try:
            slots=[None if var.get()=='Blank' else int(var.get(),16) for var in self.bank1_slots]
            changes=bank1.assign_slots(self.data,self.room,slots,self.bank1_enabled.get())
            self.commit_tile_definition_changes(changes)
            self.room_graphics_status.set('Bank 1 graphics updated. Test transitions and menus in your emulator.')
        except ValueError as exc:
            self.room_graphics_status.set(str(exc));self.refresh_room_graphics_controls()

    def apply_custom_bg_slots(self,event=None):
        if self.document is None:return
        from windfish.rom.windfish_room_graphics import assign_slots,use_original
        try:
            if not self.custom_bg_var.get():changes=use_original(self.data,self.room)
            else:
                slots=[None if var.get()=='Original' else int(var.get(),16) for var in self.custom_bg_slots]
                changes=assign_slots(self.data,self.room,slots,enabled=True)
            self.commit_tile_definition_changes(changes)
            self.room_graphics_status.set(f'Room {self.room:02X} BG slot selection updated. Undo/Redo available.')
        except ValueError as exc:self.room_graphics_status.set(str(exc));self.refresh_room_graphics_controls()

    def insert_exgfx_files(self):
        if self.document is None:return
        from windfish.rom.windfish_room_graphics import filename_id,insert_assets
        paths=filedialog.askopenfilenames(parent=self.room_settings_window,title='Insert exgfx_XX.bin files',filetypes=[('ExGFX blocks','*.bin'),('All files','*.*')])
        if not paths:return
        try:
            entries=[(filename_id(path),Path(path).read_bytes()) for path in paths]
            changes=insert_assets(self.data,entries)
            self.commit_tile_definition_changes(changes)
            listed=', '.join(f'{i:02X}' for i,raw in entries[:8])+('…' if len(entries)>8 else '')
            self.room_graphics_status.set(f'Inserted/updated {len(entries)} ExGFX ID(s): {listed}. Rooms sharing them use the update. Undo/Redo available.')
        except (ValueError,OSError) as exc:self.room_graphics_status.set(str(exc))

    def export_room_graphics_blocks(self):
        if self.document is None:return
        from windfish.rom.windfish_room_graphics import export_block
        try:
            outputs={}
            for i,check in enumerate(self.graphics_extract_checks):
                if not check.get():continue
                asset=int(self.graphics_extract_ids[i].get(),16)
                if not 0<=asset<=255:raise ValueError('Export file IDs must be 00–FF.')
                raw=export_block(self.data,self.room,i)
                if asset in outputs and outputs[asset]!=raw:raise ValueError('Different blocks need different export file IDs.')
                outputs[asset]=raw
            if not outputs:raise ValueError('Check at least one tile range to extract.')
            directory=filedialog.askdirectory(parent=self.room_settings_window,title='Extract selected ExGFX blocks into folder')
            if not directory:return
            files=[(Path(directory)/f'exgfx_{asset:02X}.bin',raw) for asset,raw in outputs.items()]
            if any(path.exists() for path,raw in files):raise ValueError('An export file already exists. Choose another folder, change the file ID, or rename the existing file.')
            written=[]
            try:
                for path,raw in files:
                    with path.open('xb') as handle:written.append(path);handle.write(raw)
            except OSError:
                for path in written:path.unlink(missing_ok=True)
                raise
            self.room_graphics_status.set(f'Extracted {len(files)} block(s) from room {self.room:02X}. Edit in YY-CHR using Game Boy 2bpp mode.')
        except (ValueError,OSError) as exc:self.room_graphics_status.set(str(exc))

    def assign_bank1_map16_set(self,event=None):
        if self.document is None:return
        from windfish.rom import windfish_room_map16 as room_tables
        try:
            value=self.bank1_map16_set.get()
            selected=0 if value=='Global' else int(value,16)
            self.commit_tile_definition_changes(room_tables.assign_set(self.data,self.room,selected))
            self.room_graphics_status.set('Page-1 artwork table assigned. Rooms sharing the table share artwork edits; collisions are unchanged.')
        except ValueError as exc:
            self.room_graphics_status.set(str(exc));self.refresh_room_graphics_controls()
