"""Dungeon header editing and lossless object/warp listings."""
import tkinter as tk
import windfish.rendering.windfish_dungeon_render as dungeon


def room_details(data,map_id,room):
    """List validated stream records in ROM order, retaining offsets and raw bytes."""
    record=dungeon.read_room(data,map_id,room)
    objects=[];warps=[];at=record.start+2
    while at<record.end-1:
        tag=data[at]
        size=5 if tag&0xFC==0xE0 else 3 if tag&0x90==0x80 else 2
        raw=bytes(data[at:at+size]);hexbytes=raw.hex(' ').upper()
        if size==5:
            kind=('Overworld','Indoor','Side-view','Reserved')[tag&3]
            warps.append((f'{len(warps):02X}',f'{at:06X}',kind,
                          *(f'{v:02X}' for v in raw[1:]),hexbytes))
        else:
            xy,obj=raw[-2:];length=(tag&15) if size==3 else 1
            kind=('Vertical' if tag&0x40 else 'Horizontal') if size==3 else 'Single'
            objects.append((f'{len(objects):02X}',f'{at:06X}',f'{obj:02X}',
                            f'{xy&15:X}',f'{xy>>4:X}',kind,str(length),str(size),hexbytes))
        at+=size
    return record,tuple(objects),tuple(warps)


def header_changes(data,map_id,room,floor,template,animation,expected=None):
    for value,limit,label in ((floor,15,'Floor'),(template,15,'Wall template'),(animation,17,'Animation')):
        if not isinstance(value,int) or not 0<=value<=limit:raise ValueError(f'{label} must be 00–{limit:02X}.')
    record=dungeon.read_room(data,map_id,room);at=record.start
    if expected is not None and expected!=(at,bytes(data[at:at+2])):
        raise ValueError('Room data changed. Reopen Room Properties before applying.')
    values=(animation,(template<<4)|floor)
    changes=[(at+i,data[at+i],v) for i,v in enumerate(values) if data[at+i]!=v]
    if not changes:return []
    from windfish.dungeon.windfish_dungeon_storage import enabled,replacement_changes
    if enabled(data):
        raw=bytes(values)+bytes(data[at+2:record.end])
        return replacement_changes(data,map_id,room,raw)
    guard_shared(data,map_id,room,changes)
    return changes


def guard_shared(data,map_id,room,changes):
    # A and Color have separate pointer tables in the same physical ROM bank.
    maps=(6,) if dungeon.room_bank(map_id)=='B' else (0,255)
    for m in maps:
        for r in range(22 if m==255 else 256):
            if r==room and dungeon.room_bank(m)==dungeon.room_bank(map_id):continue
            try:other=dungeon.read_room(data,m,r)
            except (ValueError,IndexError):continue
            if any(other.start<=offset<other.end for offset,old,new in changes):
                raise ValueError(f'Edit shares ROM storage with bank {dungeon.room_bank(m)} room {r:02X}; shared-stream editing is not supported yet.')


def object_changes(data,map_id,room,index,object_id=None,*,delete=False,expected=None):
    record,objects,warps=room_details(data,map_id,room)
    original=bytes(data[record.start:record.end])
    if expected is not None and expected!=(record.start,original):
        raise ValueError('Room objects changed. Select the collision again.')
    if not isinstance(index,int) or not 0<=index<len(objects):raise ValueError('Select a collision.')
    row=objects[index];at=int(row[1],16);raw=bytes.fromhex(row[-1])
    if delete:
        offset=at-record.start
        payload=original[:offset]+original[offset+len(raw):]+bytes([255])*len(raw)
        changes=[(record.start+i,old,new) for i,(old,new) in enumerate(zip(original,payload)) if old!=new]
    else:
        if not isinstance(object_id,int) or not 0<=object_id<=253:raise ValueError('Collision ID must be 00–FD; FE/FF are reserved.')
        changes=[] if raw[-1]==object_id else [(at+len(raw)-1,raw[-1],object_id)]
    from windfish.dungeon.windfish_dungeon_storage import enabled,replacement_changes
    if changes and enabled(data):
        offset=at-record.start
        payload=original[:offset]+original[offset+len(raw):] if delete else original[:offset+len(raw)-1]+bytes((object_id,))+original[offset+len(raw):]
        changes=replacement_changes(data,map_id,room,payload)
    elif changes:guard_shared(data,map_id,room,changes)
    if delete and changes:
        from windfish.dungeon import windfish_dungeon_visuals as visuals
        if not visuals.enabled(data):
            raise ValueError('Reopen the ROM to enable artwork-preserving collision deletion.')
        artwork=visuals.apply_to_cells(data,map_id,room,dungeon.layout(data,record))
        trial=bytearray(data)
        touched={at for at,old,new in changes}
        for at,old,new in changes:trial[at]=new
        for at,old,new in visuals.paint_cells_changes(trial,map_id,room,
                [(i%10,i//10,tile) for i,tile in enumerate(artwork)]):
            trial[at]=new;touched.add(at)
        changes=[(at,data[at],trial[at]) for at in sorted(touched) if data[at]!=trial[at]]
    return changes


from windfish.dungeon.windfish_dungeon_room_controls import RoomControlsMixin


from windfish.dungeon.windfish_dungeon_events import RoomEventsMixin


class DungeonProperties(RoomEventsMixin,RoomControlsMixin,tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner)
        self.owner=owner;self._key=None
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.heading=tk.StringVar();self.summary=tk.StringVar();self.feedback=tk.StringVar()
        self.fields={name:tk.StringVar() for name in ('Floor tile','Wall template','Animation')}
        self._expected=None;self._target=None;self.controls=[]
        self._object_rows={};self._object_expected=None;self._object_key=None
        self.object_id=tk.StringVar();self.object_feedback=tk.StringVar()
        from windfish.dungeon.windfish_dungeon_properties_ui import build_properties
        build_properties(self)
        self.bind('<FocusIn>',self.focus_refresh)
        owner.bind_history_shortcuts(self)
        self.refresh()

    def apply(self,event=None):
        if self._target is None:return
        try:
            floor,template,animation=(int(v.get(),16) for v in self.fields.values())
            changes=header_changes(self.owner.data,*self._target,floor,template,animation,expected=self._expected)
            self.owner.apply_room_changes(changes)
            self.feedback.set('')
        except (ValueError,IndexError,TypeError) as exc:self.feedback.set(str(exc))

    def select_object(self,event=None):
        selected=self.objects.selection()
        row=self._object_rows.get(selected[0]) if selected else None
        self._object_key=row
        self.object_combo.configure(state='readonly' if row else 'disabled')
        self.delete_button.configure(state='normal' if row else 'disabled')
        self.object_id.set(row[2] if row else '')
        self.object_feedback.set('');self.load_placement_fields(row)
        if row is not None and self._target is not None:
            owner=self.owner
            if not owner.collision_mode.get():owner.collision_mode.set(True);owner.toggle_collision_mode()
            m,room=self._target;start,raw=self._object_expected
            owner.selected_collision=(m,room,int(row[0],16),start,raw);owner.draw()

    def sync_map_selection(self):
        selected=getattr(self.owner,'selected_collision',None)
        index=selected[2] if selected is not None and self._target==selected[:2] else None
        row=next((row for row in self._object_rows.values() if int(row[0],16)==index),None)
        if row==self._object_key:return
        self._object_key=row
        self.objects.selection_clear()
        if row is not None:
            item=next(item for item,value in self._object_rows.items() if value==row)
            self.objects.selection_set(item);self.objects.see(item)
        self.object_combo.configure(state='readonly' if row else 'disabled')
        self.delete_button.configure(state='normal' if row else 'disabled')
        self.object_id.set(row[2] if row else '');self.load_placement_fields(row)

    def delete_object(self,event=None):
        self.edit_object(True);return 'break'

    def edit_object(self,delete):
        if self._extra_loading:return
        row=self._object_key
        if row is None or self._target is None:return
        try:
            index=int(row[0],16);tile=None if delete else int(self.object_id.get(),16)
            from windfish.dungeon.windfish_dungeon_storage import enabled as expanded
            from windfish.dungeon.windfish_dungeon_visuals import enabled as visual_enabled
            from windfish.dungeon.windfish_dungeon_collisions import prepare_brush
            combined=self.owner.collision_combined.get() and visual_enabled(self.owner.data)
            if delete:
                changes=prepare_brush(self.owner.data,*self._target,0,0,0,combined=True,index=index,delete=True,expected=self._object_expected) if combined and expanded(self.owner.data) else object_changes(self.owner.data,*self._target,index,delete=True,expected=self._object_expected)
            else:
                x=int(self.place_fields['X'].get());y=int(self.place_fields['Y'].get());length=int(self.place_fields['Length'].get());direction=self.place_fields['Direction'].get()
                if tile>=0xEC:direction='Single';length=1
                original=(int(row[3],16),int(row[4],16),int(row[6]),row[5])
                if (x,y,length,direction)==original and tile==int(row[2],16):changes=[]
                elif expanded(self.owner.data):changes=prepare_brush(self.owner.data,*self._target,x,y,tile,direction,length,combined,index=index,expected=self._object_expected)
                elif (x,y,length,direction)==original:changes=object_changes(self.owner.data,*self._target,index,tile,expected=self._object_expected)
                else:raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
            self.owner.apply_room_changes(changes)
            items=self.objects.get_children()
            if items:
                item=items[min(index,len(items)-1)];self.objects.selection_set(item);self.objects.see(item);self.select_object()
        except (ValueError,IndexError,TypeError) as exc:self.object_feedback.set(str(exc))

    def focus_refresh(self,event):
        if event.widget==self:
            self.owner.refresh_document();self.refresh()

    def close(self):
        self.owner.properties_window=None;self.owner.show_properties.set(False);self.destroy()

    def refresh(self):
        page = getattr(self, 'music_page', None)
        if page is not None:
            page.refresh()
        owner=self.owner
        context=owner.render_context(owner.room)[0] if owner.data is not None else None
        key=(id(owner.data),owner._digest,context,owner.room)
        if key==self._key:
            self.sync_map_selection();self.paint_sprite_preview();return
        self.animation_page.refresh()
        self._key=key;self._expected=None;self._target=None;self.feedback.set('');self.reset_extra()
        self._object_rows={};self._object_expected=None;self._object_key=None
        self.object_id.set('');self.object_feedback.set('')
        self.object_combo.configure(state='disabled');self.delete_button.configure(state='disabled')
        for control in self.controls:control.configure(state='disabled')
        for var in self.fields.values():var.set('')
        for tree in (self.objects,self.warps):
            for item in tree.get_children():tree.delete(item)
        if owner.data is None:
            self.heading.set('No ROM loaded');self.summary.set('Open a ROM in the main Windfish window.');return
        self.heading.set(f'Room {owner.room:02X} chest')
        try:record,objects,warps=room_details(owner.data,context,owner.room)
        except (ValueError,IndexError) as exc:
            self.summary.set(f'Room data unavailable: {exc}');return
        self._target=(context,owner.room);self._expected=(record.start,bytes(owner.data[record.start:record.start+2]))
        for var,value in zip(self.fields.values(),(record.floor,record.template,record.animation)):var.set(f'{value:02X}')
        for control in self.controls:control.configure(state='readonly')
        self.summary.set(f'Room {owner.room:02X} · Bank {dungeon.room_bank(context)} · {len(objects)} objects · floor {record.floor:02X} · ROM {record.start:06X}')
        self.warp_summary.set(f'Room {owner.room:02X} — {len(warps)}/4 warp(s)')
        self._object_expected=(record.start,bytes(owner.data[record.start:record.end]))
        for values in objects:
            item=self.objects.insert('','end',values=values);self._object_rows[item]=values
        for values in warps:self.warps.insert('','end',values=values)
        self.refresh_extra(context,record,warps)
        self.sync_map_selection()
