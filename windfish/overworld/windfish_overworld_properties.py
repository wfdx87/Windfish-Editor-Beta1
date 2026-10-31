"""Overworld Room Properties presentation and guarded edit callbacks."""
import tkinter as tk
from tkinter import messagebox, ttk
from windfish.rendering.windfish_overworld_render import palette, SPECIAL_MAP
from windfish.overworld.windfish_collision_objects import read_room_objects, clear_room_objects
from windfish.overworld.windfish_chests import CHEST_ITEMS, read_chest_item, set_chest_item, chest_item_label
from windfish.rendering.windfish_sprite_palettes import object_palette_offsets

class OverworldPropertiesMixin:
    def toggle_inspector(self):
        if self.data is None:
            self.show_inspector.set(False)
        if not self.show_inspector.get():
            if self.inspector_window is not None and self.inspector_window.winfo_exists():
                self.inspector_window.destroy()
            self.inspector_window = None
            self.inspector_image = None
            return
        if self.inspector_window is not None and self.inspector_window.winfo_exists():
            self.inspector_window.deiconify()
            self.inspector_window.lift(self)
            return
        window = tk.Toplevel(self)
        window.title('Room Properties')
        window.transient(self)
        if self.tk.call('tk', 'windowingsystem') == 'win32':
            window.wm_attributes('-toolwindow', True)
        window.geometry('470x620')
        window.minsize(300, 320)
        window.protocol('WM_DELETE_WINDOW', self.close_inspector)
        self.inspector_window = window
        chest_row = ttk.Frame(window, padding=(12, 8, 12, 0))
        chest_row.pack(fill='x')
        self.chest_room_label = ttk.Label(chest_row, text='Chest contents')
        self.chest_room_label.pack(side='left', padx=(0, 8))
        self.chest_item_var = tk.StringVar()
        self.chest_item_combo = ttk.Combobox(chest_row, textvariable=self.chest_item_var,
                                             state='readonly', width=28)
        self.chest_item_combo.pack(side='left', fill='x', expand=True)
        self.chest_item_combo.bind('<<ComboboxSelected>>', self.change_chest_item)
        ttk.Label(window, text='A0 = chest graphics/object. One reward per room; alternate layouts share it.',
                  wraplength=440).pack(anchor='w', padx=12, pady=(4, 0))
        self._animation_target = None
        tabs = ttk.Notebook(window)
        self.property_tabs = tabs
        tabs.pack(fill='both', expand=True, padx=6, pady=6)
        collision_page = ttk.Frame(tabs, padding=8)
        self.collision_page = collision_page
        tabs.add(collision_page, text='Collision Objects')
        self.collision_summary = tk.StringVar()
        ttk.Label(collision_page, textvariable=self.collision_summary, wraplength=430).pack(anchor='w')
        container = ttk.Frame(collision_page)
        container.pack(fill='both', expand=True, pady=8)
        self.collision_list = tk.Listbox(container, font=('Consolas', 10), exportselection=False)
        scrollbar = ttk.Scrollbar(container, command=self.collision_list.yview)
        self.collision_list.configure(yscrollcommand=scrollbar.set)
        self.collision_list.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Label(collision_page, text='Raw placements in ROM order. Macros are not expanded.\nWarps are listed separately and preserved when clearing.', wraplength=430).pack(anchor='w')
        self.create_collision_controls(collision_page)
        ttk.Button(collision_page,text='Recalculate collisions',command=self.recalculate_collisions).pack(anchor='w',pady=(8,0))
        self.clear_collision_button = ttk.Button(collision_page, text='Clear all objects…', command=self.clear_collision_objects)
        self.clear_collision_button.pack(anchor='w', pady=8)
        ttk.Button(collision_page, text='Add Collisions…', command=self.open_add_collisions).pack(anchor='w')
        self.create_warp_controls(tabs)
        palette_page = ttk.Frame(tabs, padding=12)
        tabs.add(palette_page, text='Palettes')
        sprites_page = ttk.Frame(tabs, padding=8)
        tabs.add(sprites_page, text='Sprites')
        ttk.Label(sprites_page, text='Overworld sprite placements — experimental editing').pack(anchor='w')
        self.sprite_list = tk.Listbox(sprites_page, font=('Consolas', 10), exportselection=False)
        self.sprite_list.pack(fill='both', expand=True, pady=6)
        self.sprite_detail = tk.StringVar(value='Open a ROM to inspect sprites')
        ttk.Label(sprites_page, textvariable=self.sprite_detail, justify='left', wraplength=400).pack(anchor='w')
        self.sprite_list.bind('<<ListboxSelect>>', self.select_sprite_from_list)
        ttk.Label(sprites_page, text='Static sprite preview (decoded from opened ROM)', font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(10, 2))
        self.sprite_preview_label = ttk.Label(sprites_page)
        self.sprite_preview_label.pack(anchor='w')
        self.sprite_preview_status = tk.StringVar(value='Select a sprite to preview its graphics.')
        ttk.Label(sprites_page, textvariable=self.sprite_preview_status, wraplength=400, justify='left').pack(anchor='w', pady=(2, 6))
        self.sprite_preview_photo = None
        sprite_tiles_page = ttk.Frame(tabs, padding=8)
        tabs.add(sprite_tiles_page, text='Sprite Tileset')
        ttk.Label(sprite_tiles_page, text='Room sprite graphics (raw 8x8 tiles; read-only)').pack(anchor='w', pady=(8,0))
        self.sprite_sheet_label = ttk.Label(sprite_tiles_page)
        self.sprite_sheet_label.pack(anchor='w', pady=4)
        self.sprite_bank_detail = tk.StringVar(value='')
        ttk.Label(sprite_tiles_page, textvariable=self.sprite_bank_detail, justify='left').pack(anchor='w')
        ttk.Label(sprite_tiles_page, text='Read-only sprite graphics. Tiles are not yet assembled into sprite images.', wraplength=420).pack(anchor='w', pady=(8,0))
        from windfish.app.windfish_music_page import MusicPage
        self.music_page = MusicPage(self, tabs)
        from windfish.rendering.windfish_animation_editor import AnimationPage
        self.animation_page = AnimationPage(self, tabs)
        from windfish.app.windfish_property_palettes import build_palette_view
        self.palette_canvas=build_palette_view(palette_page,self.update_inspector)
        self.update_inspector()

    def close_inspector(self):
        self.show_inspector.set(False)
        self.toggle_inspector()

    def refresh_chest_contents(self):
        item = read_chest_item(self.data, self.room)
        labels = [chest_item_label(value) for value in CHEST_ITEMS]
        if item not in CHEST_ITEMS:
            labels.append(chest_item_label(item))
        self.chest_item_combo.configure(values=labels)
        self.chest_item_var.set(chest_item_label(item))
        self.chest_room_label.configure(text=f'Room {self.room:02X} chest')

    def change_chest_item(self, event=None):
        if self.document is None:
            return
        item = int(self.chest_item_var.get().split(' — ', 1)[0], 16)
        if item not in CHEST_ITEMS:
            return  # An unknown existing value is displayed and preserved.
        self.end_stroke()
        change = set_chest_item(self.data, self.room, item)
        if change:
            self.history.record(*change, self.room, False)
            self.history.commit()
            self.refresh_title()
            self.show_room()

    def change_room_animation(self,event=None):
        target=getattr(self,'_animation_target',None)
        if self.data is None or target is None:return
        try:
            identity,room,alternate,start,header=target
            special=self.alternate.get() and self.room in SPECIAL_MAP
            if (identity,room,alternate)!=(id(self.data),self.room,bool(special)):raise ValueError('Selected room changed. Reload Room Properties.')
            from windfish.rendering.windfish_room_animation import animation_changes
            changes=animation_changes(self.data,room,alternate,int(self.room_animation_var.get(),16),(start,header))
            self.commit_tile_definition_changes(changes)
        except (ValueError,IndexError) as exc:messagebox.showwarning('Room animation',str(exc),parent=self.inspector_window)

    def update_inspector(self):
        if self.data is None or self.inspector_window is None or not self.inspector_window.winfo_exists():
            return
        special = self.alternate.get() and self.room in SPECIAL_MAP
        from windfish.overworld.windfish_collision_objects import read_room_objects
        try:
            record=read_room_objects(self.data,self.room,bool(special))
            self._animation_target=(id(self.data),self.room,bool(special),record.start,record.header)
            value=record.header[0];self.room_animation_var.set(f'{value:02X}')
            self.room_animation_combo.configure(state='readonly',values=[f'{v:02X}' for v in sorted(set(range(0x12))|{value})])
        except (ValueError,IndexError):
            self._animation_target=None;self.room_animation_var.set('');self.room_animation_combo.configure(state='disabled')
        page = getattr(self, 'music_page', None)
        if page is not None:
            page.refresh()
        self.animation_page.refresh()
        self.refresh_chest_contents()
        self.refresh_warps()
        self.refresh_collision_objects()
        try:
            self.refresh_sprite_list()
            pal_id, bg_offset, _ = palette(self.data, self.room)
            from windfish.app.windfish_property_palettes import draw_palette_view
            draw_palette_view(self.palette_canvas,self.data,bg_offset,object_palette_offsets(self.data,self.room),
                f'BG palettes  •  Room palette ID {pal_id:02X}  •  ROM 0x{bg_offset:05X}',
                'OBJ palettes  •  Shared 0–5 + room 6–7 (room overrides applied)')
        except Exception as exc:
            self.sprite_preview_status.set(f'Unable to read room: {exc}')

    def refresh_collision_objects(self):
        self.collision_list.delete(0, 'end')
        try:
            stream = read_room_objects(self.data, self.room, self.alternate.get())
            count = sum(e.kind == 'object' for e in stream.entries)
            self.collision_summary.set(f'Room {self.room:02X}' + (' alternate' if self.alternate.get() and self.room in SPECIAL_MAP else '') +
                f' • {count} objects • floor {stream.header[1]:02X} • ROM {stream.start:05X}')
            self.collision_list.insert('end', f'Floor fill: ID {stream.header[1]:02X}')
            for entry in stream.entries:
                self.collision_list.insert('end', f'{entry.offset:05X}  {entry.describe()}')
            selected=getattr(self,'collision_selected',None)
            if selected and selected[:2]==(self.room,bool(self.alternate.get() and self.room in SPECIAL_MAP)) and selected[2] is not None and selected[2]<len(stream.entries):
                self.collision_list.selection_set(selected[2]+1)
                self.collision_list.see(selected[2]+1)
            self.load_collision_controls()
            self.clear_collision_button.configure(state='normal')
        except ValueError as exc:
            self.collision_summary.set(f'Unable to read collision objects: {exc}')
            self.clear_collision_button.configure(state='disabled')

    def clear_collision_objects(self):
        if self.document is None:
            return
        room, alternate = self.room, self.alternate.get()
        if not messagebox.askyesno('Clear collision objects',
                f'Clear all collision object placements in room {room:02X}' +
                (' (alternate)' if alternate and room in SPECIAL_MAP else '') +
                '?\n\nThe room will use pass-through floor object 01. Warps and the visual map are preserved. '
                'Sprites are unchanged.\n\nThis cannot be undone. Undo/Redo history will also be cleared. '
                'Proceed with caution. Save As a separate ROM to keep your original.',
                icon='warning', default='no', parent=self.inspector_window):
            return
        try:
            clear_room_objects(self.data, room, alternate)
        except ValueError as exc:
            messagebox.showerror('Cannot clear collision objects', str(exc), parent=self.inspector_window)
            return
        self.history.clear()
        self.collision_selected = None
        self.collision_target = None
        self.update_edit_menu()
        self.refresh_title()
        self.refresh_collision_objects()
        self.show_room()

