"""Fixed-size dungeon title and native 8x8 layout editing."""
import hashlib
import tkinter as tk
from tkinter import ttk
import windfish.rendering.windfish_dungeon_render as dungeon

NAME_ENTRIES=((0x53393,30),(0x533B2,32),(0x533D3,32),(0x533F4,32),
              (0x53415,32),(0x53436,32),(0x53457,32),(0x53478,32),(0x53499,16))
LAYOUT_IDS=tuple(range(11))+(255,12)


def name_record(data,map_id):
    if not isinstance(map_id,int) or not 0<=map_id<9:raise ValueError('This title block has no editable Color Dungeon name.')
    at,size=NAME_ENTRIES[map_id]
    raw=dungeon.chunk(data,at,size)
    if dungeon.chunk(data,at+size,1)!=b'\xff' or b'\xff' in raw:raise ValueError('Dungeon title boundaries differ from the supported fixed-size ROM entries.')
    return at,raw


def display_title(raw):return raw.decode('ascii',errors='replace').replace('^',"'")


def name_changes(data,map_id,text,expected=None):
    at,raw=name_record(data,map_id)
    if expected is not None and expected!=(at,raw):raise ValueError('The ROM title changed. Select the dungeon again to reload it.')
    normalized=text.replace('\u2019',"'").replace('\u2018',"'").replace("'",'^')
    try:encoded=normalized.encode('ascii')
    except UnicodeEncodeError:raise ValueError('Use printable English characters; apostrophes are supported.') from None
    if any(v<32 or v>126 for v in encoded):raise ValueError('Use a single line of printable text.')
    if len(encoded)>len(raw):raise ValueError(f'This ROM entry holds at most {len(raw)} characters, including the Level prefix and spaces.')
    replacement=encoded.ljust(len(raw),b' ')
    return [(at+i,old,new) for i,(old,new) in enumerate(zip(raw,replacement)) if old!=new]


def layout_index(layout_id):
    if not isinstance(layout_id,int) or layout_id not in LAYOUT_IDS:raise ValueError('Select a native dungeon layout.')
    return 11 if layout_id==255 else layout_id


def layout_record(data,layout_id):
    at=dungeon.MAP_LAYOUT+layout_index(layout_id)*64
    return at,dungeon.chunk(data,at,64)


def layout_owner(layout_id):return 6 if layout_id==12 else layout_id


def room_assignments(data):
    """Known native layout and incoming-warp ownership, keyed by room bank/ID."""
    contexts,_=dungeon.room_contexts(data)
    owners={key:set(values) for key,values in contexts.items()}
    for layout_id in LAYOUT_IDS:
        context=layout_owner(layout_id);bank=dungeon.room_bank(context)
        for room in layout_record(data,layout_id)[1]:
            if room:owners.setdefault((bank,room),set()).add(context)
    return owners


def unused_rooms(data,layout_id,assignments=None):
    layout_index(layout_id);context=layout_owner(layout_id);bank=dungeon.room_bank(context)
    owners=room_assignments(data) if assignments is None else assignments
    available=[]
    for room in range(1,22 if context==255 else 256):
        if owners.get((bank,room)):continue
        try:dungeon.read_room(data,context,room)
        except (ValueError,IndexError):continue
        available.append(room)
    return tuple(available)


def assignment_names(data,owners):
    names=dungeon.dungeon_names(data)
    return ', '.join(f'{m:02X} — '+(names.get(m,{9:'Unused layout 09',10:'Caves'}.get(m,f'Interior {m:02X}')) or 'Unnamed dungeon') for m in sorted(owners))


def layout_changes(data,layout_id,values,expected=None):
    at,raw=layout_record(data,layout_id)
    if expected is not None and expected!=(at,raw):raise ValueError('The ROM layout changed. Select the dungeon again to reload it.')
    values=tuple(values)
    if len(values)!=64:raise ValueError('The layout must contain exactly 64 room numbers.')
    seen={}
    for i,value in enumerate(values):
        if not isinstance(value,int) or not 0<=value<=255:raise ValueError(f'Row {i//8+1}, column {i%8+1}: enter a hex room number 00–FF.')
        if layout_id==255 and value>21:raise ValueError(f'Row {i//8+1}, column {i%8+1}: Color rooms are 00–15.')
        if value:
            if value in seen:
                first=seen[value]
                raise ValueError(f'Room {value:02X} is already in row {first//8+1}, column {first%8+1}. Each room can appear only once in the Dungeon Map Table.')
            seen[value]=i
            context=6 if layout_id==12 else layout_id
            try:dungeon.read_room(data,context,value)
            except (ValueError,IndexError):raise ValueError(f'Row {i//8+1}, column {i%8+1}: room {value:02X} has no valid data in this layout\'s room bank.') from None
    owners=room_assignments(data);bank=dungeon.room_bank(layout_owner(layout_id));existing=set(raw)
    target=layout_owner(layout_id)
    for i,value in enumerate(values):
        other=owners.get((bank,value),set())-{target}
        if value and value not in existing and other:
            raise ValueError(f'Row {i//8+1}, column {i%8+1}: room {value:02X} is assigned to {assignment_names(data,other)}. Choose an unused room or one already in this layout.')
    return [(at+i,old,new) for i,(old,new) in enumerate(zip(raw,values)) if old!=new]


def layout_options(data):
    names=dungeon.dungeon_names(data) if data is not None else dict(dungeon.DUNGEONS)
    return tuple((m,names.get(m,{9:'Unused layout',10:'Caves layout',12:names[6]+' (collapsed)'}.get(m,''))) for m in LAYOUT_IDS)


class MetadataWindow(tk.Toplevel):
    def __init__(self,owner,title,geometry):
        super().__init__(owner);self.owner=owner;self._key=None;self._expected=None;self._loaded=None
        self.title(title);self.geometry(geometry);self.resizable(False,False);self.transient(owner)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.frame=ttk.Frame(self,padding=12);self.frame.pack(fill='both',expand=True)
        self.choice=tk.StringVar();self.combo=ttk.Combobox(self.frame,textvariable=self.choice,state='readonly',width=52)
        self.combo.pack(fill='x',pady=(0,8));self.combo.bind('<<ComboboxSelected>>',self.choose)
        self.status=tk.StringVar()
        self.bind('<FocusIn>',self.focus_refresh);owner.bind_history_shortcuts(self)
    def focus_refresh(self,event):
        if event.widget==self:self.owner.refresh_document();self.refresh()
    def choose(self,event=None):
        self.selected=int(self.choice.get().split(' — ',1)[0],16);self.refresh(force=True)
    def labels(self,options):
        labels=[f'{m:02X} — {name or "(blank)"}' for m,name in options]
        self.combo.configure(values=labels)
        self.choice.set(next(label for label,(m,name) in zip(labels,options) if m==self.selected))
    def close(self):setattr(self.owner,self.owner_field,None);self.destroy()


class DungeonNamesWindow(MetadataWindow):
    owner_field='names_window'
    def __init__(self,owner):
        super().__init__(owner,'Edit Dungeon Names','560x220')
        self.selected=owner.map_id if owner.map_id in tuple(range(9))+(255,) else 0
        self.text=tk.StringVar();self.entry=ttk.Entry(self.frame,textvariable=self.text);self.entry.pack(fill='x')
        self.limit=tk.StringVar();ttk.Label(self.frame,textvariable=self.limit,wraplength=530).pack(anchor='w',pady=5)
        self.save_button=ttk.Button(self.frame,text='Save',command=self.save);self.save_button.pack(anchor='w')
        ttk.Label(self.frame,textvariable=self.status,wraplength=510).pack(anchor='w',pady=(5,0));self.refresh(force=True)
    def refresh(self,force=False):
        data=self.owner.data;names=dungeon.dungeon_names(data) if data is not None else dict(dungeon.DUNGEONS)
        self.labels(tuple((m,names[m]) for m in tuple(range(9))+(255,)))
        if data is None or self.selected==255:
            self._expected=None;self._key=None;self.text.set('');self.entry.configure(state='disabled');self.save_button.configure(state='disabled');self.status.set('')
            self.limit.set('Color Dungeon has no title entry in this ROM block.' if data is not None else 'Open a ROM first.');return
        try:at,raw=name_record(data,self.selected)
        except (ValueError,IndexError) as exc:
            self._expected=None;self.entry.configure(state='disabled');self.status.set(str(exc));self.save_button.configure(state='disabled');return
        key=(id(data),self.selected,raw)
        if not force and key==self._key:return
        if not force and self._key is not None and self._key[:2]==key[:2] and self.text.get()!=self._loaded:
            self.status.set('ROM title changed; select the dungeon again to reload before saving.');return
        self._key=key;self._expected=(at,raw);self._loaded=display_title(raw);self.text.set(self._loaded)
        self.entry.configure(state='normal');self.save_button.configure(state='normal');self.limit.set(f'Maximum {len(raw)} characters, including Level prefix and spacing. Shorter text is padded with spaces.');self.status.set('')
    def save(self):
        if self._expected is None or self.owner.data is None:return
        try:
            changes=name_changes(self.owner.data,self.selected,self.text.get(),self._expected)
            self.owner.apply_room_changes(changes);self.refresh(force=True);self.status.set('Saved to ROM buffer. File → Save ROM writes the file.')
        except (ValueError,IndexError) as exc:self.status.set(str(exc))


from windfish.dungeon.windfish_dungeon_layout_grid import LayoutGridMixin


class DungeonLayoutWindow(LayoutGridMixin,MetadataWindow):
    owner_field='layout_window'
    def __init__(self,owner):
        super().__init__(owner,'Dungeon Map Table Editor','790x790')
        self.frame.configure(padding=16)
        self.combo.destroy()
        ttk.Label(self.frame,text='Dungeon level').pack(anchor='w')
        self.combo=ttk.Combobox(self.frame,textvariable=self.choice,state='readonly',width=52)
        self.combo.pack(fill='x',pady=(2,12))
        self.combo.bind('<<ComboboxSelected>>',self.choose)
        self.selected=12 if owner.map_id==6 and owner.collapsed.get() else owner.map_id
        if self.selected not in LAYOUT_IDS:self.selected=0
        body=ttk.Frame(self.frame);body.pack(fill='x')
        grid=ttk.Frame(body);grid.pack(side='left',anchor='n')
        self._focused_cell=0;self.build_layout_grid(grid)
        right=ttk.Frame(body);right.pack(side='left',anchor='n',padx=(24,0))
        self.completed_preview=tk.BooleanVar(value=False)
        self.preview=tk.Canvas(right,width=320,height=320,highlightthickness=0)
        self.preview.pack(anchor='w')
        ttk.Checkbutton(right,text='Show Completed Map',variable=self.completed_preview,command=self.draw_layout_grid).pack(anchor='w',pady=(8,0))
        marker_controls = ttk.Frame(right)
        marker_controls.pack(anchor='w', pady=(8, 0))
        self.boss_marker = tk.BooleanVar(value=False)
        self.chest_marker = tk.BooleanVar(value=False)
        self.boss_check = ttk.Checkbutton(marker_controls, text='Boss Room', variable=self.boss_marker,
                                          command=lambda: self.change_marker('boss'))
        self.chest_check = ttk.Checkbutton(marker_controls, text='Chest Room', variable=self.chest_marker,
                                           command=lambda: self.change_marker('chest'))
        self.boss_check.pack(side='left')
        self.chest_check.pack(side='left', padx=(12, 0))
        self._marker_overrides = {}
        self._marker_loaded = {}
        self.preview_info=tk.StringVar()
        ttk.Label(right,textvariable=self.preview_info,wraplength=350).pack(anchor='w',pady=6)
        self.unused_heading=tk.StringVar();ttk.Label(grid,textvariable=self.unused_heading).pack(anchor='w')
        holder=ttk.Frame(grid);holder.pack(fill='x',pady=(5,0))
        self.unused_list=tk.Listbox(holder,font=('Consolas',10),height=5,exportselection=False)
        scroll=ttk.Scrollbar(holder,command=self.unused_list.yview);self.unused_list.configure(yscrollcommand=scroll.set)
        self.unused_list.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.unused_list.bind('<Double-Button-1>',self.add_available_room)
        self.assignment_info=tk.StringVar();ttk.Label(self.frame,textvariable=self.assignment_info,wraplength=750).pack(anchor='w',pady=(8,0))
        self._usage_key=None;self._owners={};self._focused_cell=0
        self._map_expected=None
        self.note=tk.StringVar();ttk.Label(self.frame,textvariable=self.note,wraplength=750).pack(anchor='w',pady=7)
        self.save_button=ttk.Button(self.frame,text='Save Layout and Map',command=self.save);self.save_button.pack(anchor='w')
        ttk.Label(self.frame,textvariable=self.status,wraplength=750).pack(anchor='w',pady=(5,0));self.refresh(force=True)

    def map_tiles(self, rooms):
        from windfish.dungeon.windfish_dungeon_map_auto import generate, with_markers
        automatic = generate(self.owner.data, self.selected, rooms)
        return with_markers(self.selected, rooms, automatic, self._marker_overrides)

    def refresh_marker_controls(self):
        from windfish.dungeon.windfish_dungeon_minimap import SUPPORTED
        index = self._focused_cell
        room = int(self.cells[index].get(), 16)
        enabled = (self.owner.data is not None and self._expected is not None
                   and self.selected in SUPPORTED and self._map_expected is not None
                   and (room != 0 or self.selected == 255 and index == 25))
        tile = 0xEF
        if enabled:
            try:
                tile = self.map_tiles([int(v.get(), 16) for v in self.cells])[index]
            except (ValueError, IndexError):
                enabled = False
        self.boss_marker.set(enabled and tile == 0xEE)
        self.chest_marker.set(enabled and tile == 0xED)
        for control in (self.boss_check, self.chest_check):
            control.configure(state='normal' if enabled else 'disabled')

    def change_marker(self, kind):
        if self._map_expected is None or self.owner.data is None:
            return
        index = self._focused_cell
        room = int(self.cells[index].get(), 16)
        if room == 0 and not (self.selected == 255 and index == 25):
            return
        selected = self.boss_marker.get() if kind == 'boss' else self.chest_marker.get()
        self._marker_overrides[room] = (0xEE if kind == 'boss' else 0xED) if selected else 0xEF
        self.refresh_marker_controls()
        self.draw_layout_grid()
        self.status.set('Marker updated in draft. Save applies it with the layout. Room contents are unchanged.')

    def refresh_map_preview(self):
        from PIL import Image,ImageTk
        from windfish.dungeon.windfish_dungeon_minimap import SUPPORTED,tile_image
        from windfish.dungeon.windfish_dungeon_map_auto import completed
        self.preview.delete('all')
        if self.selected not in SUPPORTED:
            self.preview_info.set('This layout has no native inventory map. Only room placement is saved.')
            return None
        try:
            rooms = [int(v.get(), 16) for v in self.cells]
            tiles = self.map_tiles(rooms)
            shown=completed(self.owner.data,self.selected,rooms,tiles=tiles) if self.completed_preview.get() else tiles
            image=Image.new('RGB',(64,64))
            for i,tile in enumerate(shown):image.paste(tile_image(self.owner.data,tile),(i%8*8,i//8*8))
            self.preview_photo=ImageTk.PhotoImage(image.resize((320,320),Image.Resampling.NEAREST))
            self.preview.create_image(0,0,image=self.preview_photo,anchor='nw')
            self.preview_info.set('Completed preview: all rooms visited; chests/bosses cleared; doors and bomb walls opened. Custom entity-driven changes are not simulated. Preview only.' if self.completed_preview.get() else 'Map + compass preview: room, chest and Nightmare markers. Checkboxes change map markers only, not room contents. Neutral colors.')
            return tiles
        except (ValueError,IndexError) as exc:
            self.preview_info.set(str(exc));return None

    def refresh(self,force=False):
        data=self.owner.data;self.labels(layout_options(data));self.refresh_usage(data)
        if data is None:
            self._expected=None;self._key=None
            self.preview.delete('all');self.preview_info.set('Open a ROM first.')
            self.refresh_cell_selectors()
            self.refresh_marker_controls()
            self.save_button.configure(state='disabled');self.status.set('Open a ROM first.');return
        at,raw=layout_record(data,self.selected);key=(id(data),self.selected,raw)
        if not force and key==self._key:
            self.refresh_cell_selectors();self.draw_layout_grid();return
        if not force and self._key is not None and self._key[:2]==key[:2] and (tuple(v.get() for v in self.cells)!=self._loaded or self._marker_overrides != self._marker_loaded):
            self.status.set('ROM layout changed; select the dungeon again to reload before saving.');return
        from windfish.dungeon.windfish_dungeon_minimap import record as map_record, SUPPORTED
        try:self._map_expected=map_record(data,self.selected) if self.selected in SUPPORTED else None
        except ValueError:self._map_expected=None
        self._key=key;self._expected=(at,raw);self._loaded=tuple(f'{v:02X}' for v in raw)
        # Existing native artwork is authoritative, including ordinary rooms
        # explicitly cleared of automatic boss/chest detection in an earlier edit.
        self._marker_overrides = {}
        if self._map_expected is not None:
            self._marker_overrides = {
                room: tile for i, (room, tile) in enumerate(zip(raw, self._map_expected[1]))
                if (room or self.selected == 255 and i == 25) and tile in (0x7D, 0xEF, 0xED, 0xEE)
            }
        self._marker_loaded = dict(self._marker_overrides)
        for var,value in zip(self.cells,self._loaded):var.set(value)
        self.refresh_cell_selectors();self.draw_layout_grid()
        self.save_button.configure(state='normal')
        self.show_assignment(self._focused_cell)
        self.note.set('Click a cell, then choose its room or double-click an available room to add it. Each native layout uses one bank. Save applies the room layout and automatically generated map together. 00 = filler. Each room can appear only once.'+(' Color rooms: 00–15; the native boss room 00 is shown at row 4, column 2.' if self.selected==255 else ''))
        self.status.set('')
    def refresh_usage(self,data):
        key=(id(data),hashlib.sha256(data).digest() if data is not None else None,self.selected)
        if key==self._usage_key:return
        self._usage_key=key;self.unused_list.delete(0,'end')
        if data is None:
            self._owners={};self.unused_heading.set('Available rooms to add');self.assignment_info.set('');return
        self._owners=room_assignments(data)

    def refresh_available_rooms(self):
        self.unused_list.delete(0,'end')
        used={int(var.get(),16) for var in self.cells}
        available=[value for value in self.cell_room_combo.cget('values') if int(value,16) and int(value,16) not in used]
        self.unused_heading.set(f'Available rooms to add ({len(available)})')
        for value in available:self.unused_list.insert('end',value)
        if not available:self.unused_list.insert('end','(none)')

    def add_available_room(self,event=None):
        if self.owner.data is None or self._expected is None:return
        selection=self.unused_list.curselection()
        if not selection:return
        value=self.unused_list.get(selection[0])
        if value=='(none)':return
        self.cell_room.set(value)
        self.assign_layout_cell()
        return 'break'

    def show_assignment(self,index):
        self._focused_cell=index
        self.refresh_cell_selectors()
        self.refresh_marker_controls()
        if self.owner.data is None:return
        self.refresh_available_rooms()
        try:room=int(self.cells[index].get().strip(),16)
        except ValueError:self.assignment_info.set('Enter a hexadecimal room ID.');return
        if not room:self.assignment_info.set('00 is the native filler value (with the Color boss-room convention).');return
        context=layout_owner(self.selected);bank=dungeon.room_bank(context)
        try:dungeon.read_room(self.owner.data,context,room)
        except (ValueError,IndexError):self.assignment_info.set(f'{room:02X}: no valid room data in bank {bank}.');return
        owners=self._owners.get((bank,room),set())
        self.assignment_info.set(f'{room:02X}: '+('Assigned to '+assignment_names(self.owner.data,owners) if owners else 'No known layout or warp assignment.'))

    def save(self):
        if self._expected is None or self.owner.data is None:return
        try:
            values=[]
            for i,var in enumerate(self.cells):
                text=var.get().strip()
                if text and (len(text)>2 or any(c not in '0123456789abcdefABCDEF' for c in text)):raise ValueError(f'Row {i//8+1}, column {i%8+1}: enter a hex room number 00–FF.')
                values.append(int(text,16) if text else 0)
            changes=layout_changes(self.owner.data,self.selected,values,self._expected)
            from windfish.dungeon.windfish_dungeon_minimap import changes as map_changes, SUPPORTED
            if self.selected in SUPPORTED:
                if self._map_expected is None:raise ValueError('Inventory map loader is unsupported; cannot save this map.')
                changes+=map_changes(self.owner.data,self.selected,self.map_tiles(values),self._map_expected)
            self.owner.apply_room_changes(changes);self.refresh(force=True);self.status.set('Saved to ROM buffer. File → Save ROM writes the file.')
        except (ValueError,IndexError) as exc:self.status.set(str(exc))


class DungeonMetadataMixin:
    def open_dungeon_names(self):
        if self.names_window is None:self.names_window=DungeonNamesWindow(self)
        else:self.names_window.deiconify();self.names_window.lift()
    def open_dungeon_layout(self):
        if self.layout_window is None:self.layout_window=DungeonLayoutWindow(self)
        else:self.layout_window.deiconify();self.layout_window.lift()
    def refresh_metadata_windows(self):
        for window in (self.names_window,self.layout_window):
            if window is not None:window.refresh()
