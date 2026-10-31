"""Overworld warp destinations and count, with storage-aware atomic editing."""
from windfish.overworld.windfish_collision_objects import read_room_objects, ALTERNATE_POINTERS
from windfish.rom.windfish_collision_storage import enabled, replacement_changes

WARP_TYPES = ('00 — Overworld', '01 — Indoor', '02 — Side-view', '03 — Reserved')


def room_warps(data, room, alternate=False):
    return tuple(e for e in read_room_objects(data, room, alternate).entries if e.kind == 'warp')


def warp_changes(data, room, alternate, index, category, map_id, destination, x, y, expected=None):
    values = (category, map_id, destination, x, y)
    if any(not isinstance(v, int) or not 0 <= v <= 255 for v in values) or category > 3:
        raise ValueError('Type must be 00–03; map, room, X and Y must be hex bytes 00–FF.')
    alternate = bool(alternate and room in ALTERNATE_POINTERS)
    stream = read_room_objects(data, room, alternate)
    warps = tuple(e for e in stream.entries if e.kind == 'warp')
    if not isinstance(index, int) or not 0 <= index < len(warps):
        raise ValueError('Select an existing warp.')
    target = warps[index]
    if category == 3 and target.raw[0] != 0xE3:
        raise ValueError('Reserved warp type 03 can only be preserved in existing records.')
    if expected is not None and target.raw != expected:
        raise ValueError('Warp data changed. Select the warp again before applying.')
    raw = bytes((0xE0 | category, map_id, destination, x, y))
    if raw == target.raw:
        return []
    if enabled(data):
        payload = bytearray(data[stream.start:stream.end])
        at = target.offset-stream.start
        payload[at:at+5] = raw
        return replacement_changes(data, room, alternate, payload)
    # Legacy pointers can share streams. A destination edit must not silently
    # change another room or an alternate layout using the same record.
    for other in range(256):
        for alt in ((False, True) if other in ALTERNATE_POINTERS else (False,)):
            if (other, alt) == (room, alternate):
                continue
            candidate = read_room_objects(data, other, alt)
            if target.offset < candidate.end and candidate.start < target.offset+5:
                raise ValueError(f'Warp storage overlaps room {other:02X}. Install expanded collision storage to separate it.')
    return [(target.offset+i, old, new) for i,(old,new) in enumerate(zip(target.raw,raw)) if old != new]


def resize_warps(data,room,alternate,capacities,*,remove=None,expected=None,arrival=None):
    """Append a default destination or remove an unused warp, atomically."""
    from windfish.overworld.windfish_collision_definitions import entrance_count
    alternate=bool(alternate and room in ALTERNATE_POINTERS)
    stream=read_room_objects(data,room,alternate)
    warps=tuple(e for e in stream.entries if e.kind=='warp')
    if expected is not None and tuple(e.raw for e in warps)!=expected:
        raise ValueError('Warp data changed. Select the room again before editing.')
    if remove is None:
        if len(warps)>=4:raise ValueError('A room layout supports at most four warps.')
        x,y=(0x50,0x70) if arrival is None else arrival
        if any(type(v) is not int or not 0<=v<=255 for v in (x,y)):
            raise ValueError('Arrival X and Y must be pixel coordinates 00–FF.')
        # Append before the terminator without changing existing record order.
        payload=bytes(data[stream.start:stream.end-1])+bytes((0xE0,0,room,x,y,0xFE))
    else:
        if not isinstance(remove,int) or not 0<=remove<len(warps):raise ValueError('Select a warp to remove.')
        entrances=sum(entrance_count(e.raw[-1]) for e in stream.entries if e.kind=='object')
        if remove<entrances:
            raise ValueError('This warp is used by an entrance. Remove that entrance and any later entrances first.')
        target=warps[remove]
        payload=bytes(data[stream.start:target.offset])+bytes(data[target.offset+5:stream.end])
    if enabled(data):return replacement_changes(data,room,alternate,payload)
    original=capacities.get((room,alternate))
    if original is None or original.start!=stream.start:raise ValueError('Room storage changed; reopen the ROM.')
    for key,other in capacities.items():
        if key!=(room,alternate) and stream.start<other.end and other.start<original.end:
            raise ValueError('Warp storage overlaps another room. Install expanded collision storage first.')
    if stream.start+len(payload)>original.end:
        raise ValueError('No verified room space for another warp. Install expanded collision storage first.')
    return [(stream.start+i,data[stream.start+i],value) for i,value in enumerate(payload) if data[stream.start+i]!=value]


class WarpEditorMixin:
    def create_warp_controls(self, tabs):
        import tkinter as tk
        from tkinter import ttk
        page = ttk.Frame(tabs, padding=8)
        tabs.add(page, text='Warps')
        self.warp_page=page
        self.warp_summary = tk.StringVar()
        ttk.Label(page, textvariable=self.warp_summary, wraplength=430).pack(anchor='w')
        self.warp_list = tk.Listbox(page, exportselection=False, height=7, font=('Consolas',9))
        self.warp_list.pack(fill='both', expand=True, pady=8)
        self.warp_list.bind('<<ListboxSelect>>', self.select_warp)
        fields = ttk.Frame(page)
        fields.pack(fill='x')
        self.warp_type = tk.StringVar()
        self.warp_fields = {key:tk.StringVar() for key in ('map','room','x','y')}
        self.warp_inputs = []
        ttk.Label(fields, text='Type').grid(row=0,column=0,sticky='w',pady=3)
        combo = ttk.Combobox(fields, textvariable=self.warp_type, values=WARP_TYPES[:3], state='readonly', width=22)
        combo.grid(row=0,column=1,sticky='w'); self.warp_inputs.append(combo)
        for row,(key,label) in enumerate((('map','Destination map'),('room','Destination room'),
                                           ('x','Arrival X (pixels)'),('y','Arrival Y (pixels)')),1):
            ttk.Label(fields,text=label).grid(row=row,column=0,sticky='w',padx=(0,12),pady=3)
            entry = ttk.Entry(fields,textvariable=self.warp_fields[key],width=8)
            entry.grid(row=row,column=1,sticky='w'); self.warp_inputs.append(entry)
        ttk.Label(page,text='All values are hexadecimal. X/Y are pixel positions.\n'
                  'Warp order follows entrance order. Interior return warps are separate.',wraplength=430).pack(anchor='w',pady=8)
        self.warp_apply = ttk.Button(page,text='Apply warp changes',command=self.apply_warp)
        self.warp_apply.pack(anchor='w')
        buttons=ttk.Frame(page)
        buttons.pack(anchor='w',pady=(8,0))
        self.warp_add=ttk.Button(buttons,text='Add warp',command=self.add_warp)
        self.warp_add.pack(side='left')
        self.warp_remove=ttk.Button(buttons,text='Remove warp',command=self.remove_warp)
        self.warp_remove.pack(side='left',padx=(8,0))
        self.warp_status = tk.StringVar()
        ttk.Label(page,textvariable=self.warp_status,wraplength=430).pack(anchor='w',pady=6)
        self._warp_signature = None
        self._warp_index = 0
        self._warp_context = None

    def refresh_warps(self):
        key = (self.room, bool(self.alternate.get() and self.room in ALTERNATE_POINTERS))
        try:
            records = room_warps(self.data, *key)
        except ValueError as exc:
            self.warp_status.set(str(exc)); records = ()
        signature = (key, tuple(e.raw for e in records))
        if signature == self._warp_signature:
            return
        if key != self._warp_context:
            self._warp_index = 0
        self._warp_context = key
        self._warp_signature = signature
        self._warp_records = records
        self.warp_list.delete(0,'end')
        for i,entry in enumerate(records):
            tag,map_id,room,x,y = entry.raw
            self.warp_list.insert('end',f'{i+1}: {WARP_TYPES[tag&3].split(" — ")[1]}  Map {map_id:02X} Room {room:02X}  X {x:02X} Y {y:02X}')
        self.warp_summary.set(f'Room {self.room:02X}' + (' alternate' if key[1] else '') + f' — {len(records)}/4 warp(s)')
        self.warp_status.set('Edit destinations here; place entrance objects using Add Collisions.' if records else 'This layout has no warp records.')
        if records:
            self._warp_index = min(self._warp_index,len(records)-1)
            self.warp_list.selection_set(self._warp_index)
        self.select_warp()

    def select_warp(self, event=None):
        selection = self.warp_list.curselection()
        active = bool(selection and self._warp_records)
        for widget in self.warp_inputs:
            widget.configure(state=('readonly' if widget is self.warp_inputs[0] else 'normal') if active else 'disabled')
        self.warp_apply.configure(state='normal' if active else 'disabled')
        if hasattr(self,'warp_add'):
            self.warp_add.configure(state='normal' if self.data is not None and len(self._warp_records)<4 else 'disabled')
            self.warp_remove.configure(state='normal' if active else 'disabled')
        if not active:
            self.warp_type.set('')
            for value in self.warp_fields.values(): value.set('')
            return
        self._warp_index = selection[0]
        tag,map_id,room,x,y = self._warp_records[self._warp_index].raw
        self.warp_inputs[0].configure(values=WARP_TYPES if tag&3 == 3 else WARP_TYPES[:3])
        self.warp_type.set(WARP_TYPES[tag&3])
        for key,value in zip(('map','room','x','y'),(map_id,room,x,y)):
            self.warp_fields[key].set(f'{value:02X}')

    def apply_warp(self):
        if self.document is None or not self.warp_list.curselection(): return
        key = (self.room,bool(self.alternate.get() and self.room in ALTERNATE_POINTERS))
        if key != self._warp_context:
            self.refresh_warps(); return
        try:
            category = int(self.warp_type.get().split(' — ')[0],16)
            fields = [int(self.warp_fields[k].get(),16) for k in ('map','room','x','y')]
            changes = warp_changes(self.data,*key,self._warp_index,category,*fields,
                                   expected=self._warp_records[self._warp_index].raw)
        except ValueError as exc:
            self.warp_status.set(f'Cannot apply: {exc}'); return
        self.end_stroke()
        for at,before,after in changes:
            self.data[at] = after
            self.history.record(at,before,after,*key)
        self.history.commit()
        self.show_room()
        self.warp_status.set('Warp destination updated.' if changes else 'No changes.')

    def add_warp(self):
        self.change_warp_count()

    def remove_warp(self):
        if self.warp_list.curselection():self.change_warp_count(remove=self.warp_list.curselection()[0])

    def change_warp_count(self,remove=None):
        if self.document is None:return
        key=(self.room,bool(self.alternate.get() and self.room in ALTERNATE_POINTERS))
        if key!=self._warp_context:
            self.refresh_warps();return
        try:
            changes=resize_warps(self.data,*key,self.collision_capacities,remove=remove,
                                 expected=tuple(e.raw for e in self._warp_records))
        except ValueError as exc:
            self.warp_status.set(f'Cannot '+('add' if remove is None else 'remove')+f' warp: {exc}');return
        self.end_stroke()
        for at,before,after in changes:
            self.data[at]=after;self.history.record(at,before,after,*key)
        self.history.commit()
        self._warp_index=len(self._warp_records) if remove is None else max(0,remove-1)
        self.show_room()
        self.warp_status.set('Warp added. Set its destination and click Apply warp changes.' if remove is None else 'Warp removed.')
