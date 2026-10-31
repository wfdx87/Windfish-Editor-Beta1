"""Dungeon collision placement, selection and room-local overlays."""
from tkinter import messagebox
import tkinter as tk
from PIL import ImageTk,Image
import windfish.rendering.windfish_dungeon_render as dungeon
import windfish.dungeon.windfish_dungeon_storage as storage
import windfish.dungeon.windfish_dungeon_visuals as visuals
from windfish.dungeon.windfish_dungeon_properties import room_details,object_changes


def footprint(data,obj):
    xy,tile,length,vertical=obj
    if tile>=0xEC:return tuple((xy+offset,value) for offset,value in dungeon.doors(data)[tile])
    return tuple((xy+i*(16 if vertical else 1),tile) for i in range(length))


def placement_changes(data,map_id,room,cells,combined=False):
    """Prepare a whole placement atomically; retain header, macros and warps."""
    cells=list(cells)
    if not cells:return []
    if not storage.enabled(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    for x,y,tile in cells:
        if not (0<=x<10 and 0<=y<8 and 0<=tile<=253):raise ValueError('Collision coordinates or ID are invalid.')
        if combined and tile>=0xEC:raise ValueError('EC–FF are special IDs. Place dungeon door presets from Add Collisions instead.')
    record,objects,warps=room_details(data,map_id,room)
    targets={y*16+x for x,y,tile in cells}
    payload=bytearray(data[record.start:record.start+2])
    # Split existing ordinary runs around painted cells. Presets remain intact.
    for row in objects:
        raw=bytes.fromhex(row[-1]);xy,tile=raw[-2:]
        if tile>=0xEC:payload.extend(raw);continue
        length=(raw[0]&15) if len(raw)==3 else 1
        vertical=len(raw)==3 and bool(raw[0]&0x40)
        parts=footprint(data,(xy,tile,length,vertical))
        if not any(pos in targets for pos,value in parts):payload.extend(raw);continue
        step=16 if vertical else 1;remaining=[pos for pos,value in parts if pos not in targets];j=0
        while j<len(remaining):
            n=1
            while j+n<len(remaining) and remaining[j+n]==remaining[j]+n*step:n+=1
            payload.extend(((0xC0 if vertical else 0x80)|n,remaining[j],tile) if n>1 else (remaining[j],tile));j+=n
    # Last occurrence wins; horizontal runs use the native three-byte encoding.
    stamps={y*16+x:tile for x,y,tile in cells}
    positions=sorted(stamps);i=0
    while i<len(positions):
        pos=positions[i];tile=stamps[pos];n=1
        if tile<0xEC:
            while i+n<len(positions) and positions[i+n]==pos+n and (pos+n)//16==pos//16 and stamps[pos+n]==tile:n+=1
        payload.extend((0x80|n,pos,tile) if n>1 else (pos,tile));i+=n
    for row in warps:payload.extend(bytes.fromhex(row[-1]))
    payload.append(254)
    changes=storage.replacement_changes(data,map_id,room,bytes(payload))
    if not combined:return changes
    trial=bytearray(data)
    for at,old,new in changes:trial[at]=new
    visual_changes=visuals.paint_cells_changes(trial,map_id,room,cells)
    for at,old,new in visual_changes:trial[at]=new
    offsets={at for at,old,new in changes}|{at for at,old,new in visual_changes}
    return [(at,data[at],trial[at]) for at in sorted(offsets) if data[at]!=trial[at]]


DUNGEON_PRESET_NAMES=dict(zip(range(0xEC,0xFE),(
    'Closed door: top','Closed door: bottom','Closed door: left','Closed door: right',
    'Shutter: top','Shutter: bottom','Shutter: left','Shutter: right',
    'Open door: top','Open door: bottom','Open door: left','Open door: right',
    'Boss door','Stairs door','Revolving door','One-way arrow','Dungeon entrance','Indoor entrance')))


class DungeonCollisionSelector(tk.Toplevel):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self._key=None
        self.transient(owner);self.protocol('WM_DELETE_WINDOW',self.close)
        from windfish.overworld.windfish_collision_palette import build_collision_palette
        self.ui=build_collision_palette(self,owner.collision_direction,owner.collision_length,owner.collision_combined,
            [DUNGEON_PRESET_NAMES.get(obj,'Tile') for obj in range(254)])
        self.ui.items.bind('<<ListboxSelect>>',self.pick)
        self.ui.preview.bind('<Configure>',lambda event:self.refresh())
        self.bind('<FocusIn>',lambda event:self.refresh())
        self.traces=[(var,var.trace_add('write',self.refresh)) for var in (owner.collision_direction,owner.collision_length)]
        owner.bind_history_shortcuts(self)
        self.select(owner.collision_brush if owner.collision_brush is not None else 0)
        owner.collision_mode.set(True);owner.toggle_collision_mode()
    def close(self):
        for var,token in self.traces:var.trace_remove('write',token)
        self.owner.collision_selector=None;self.destroy()
    def select(self,tile):
        self.owner.collision_brush=tile
        self.ui.items.selection_clear(0,'end');self.ui.items.selection_set(tile);self.ui.items.see(tile);self.refresh()
    def pick(self,event=None):
        selected=self.ui.items.curselection()
        if not selected:return
        self.owner.collision_brush=selected[0];self.owner.collision_mode.set(True)
        self.owner.toggle_collision_mode();self.refresh()
    def refresh(self,*args):
        o=self.owner;ui=self.ui
        if o.data is None:ui.preview.delete('all');return
        tile=o.collision_brush if o.collision_brush is not None else 0
        fixed=tile>=0xEC
        if fixed:
            if o.collision_direction.get()!='Single':o.collision_direction.set('Single')
            if o.collision_length.get()!=1:o.collision_length.set(1)
        ui.direction.configure(state='disabled' if fixed else 'readonly')
        ui.length.configure(state='normal' if not fixed and o.collision_direction.get()!='Single' else 'disabled')
        try:
            context,side=o.render_context(o.room);record=dungeon.read_room(o.data,context,o.room)
            raw,selector,warnings=dungeon.graphics(o.data,record,side)
            key=(context,o.room,side,raw,dungeon.attributes(o.data,context,o.room),dungeon.palette(o.data,context,side,o.room))
            if key!=self._key:self.sheet,_=dungeon.tile_sheet(o.data,context,o.room,side);self._key=key
            cells=brush_cells(o.data,tile,o.collision_direction.get(),o.collision_length.get())
            w=max(x for x,y,t in cells)+1;h=max(y for x,y,t in cells)+1
            image=Image.new('RGB',(w*16,h*16),'#dddddd')
            for x,y,t in cells:image.paste(self.sheet.crop((t%16*16,t//16*16,t%16*16+16,t//16*16+16)),(x*16,y*16))
            scale=max(.1,min(3,(max(20,ui.preview.winfo_width())-12)/image.width,(max(20,ui.preview.winfo_height())-8)/image.height))
            self.photo=ImageTk.PhotoImage(image.resize((max(1,int(image.width*scale)),max(1,int(image.height*scale))),Image.Resampling.NEAREST))
            ui.preview.delete('all');ui.preview.create_image(ui.preview.winfo_width()/2,ui.preview.winfo_height()/2,image=self.photo)
            free='Install expanded storage to place'
            if storage.enabled(o.data):
                used,capacity=storage.used_space(o.data,context,o.room);free=f'{capacity-used} bytes free (room group)'
            ui.availability.set(f'{tile:02X} • {w}×{h} cells • Ready to place'+(' • Door/stair preset' if fixed else ''))
            ui.help_text.set(f'Room {o.room:02X} • {free} | Left: select/drag • Right: place • Ctrl+Right: remove • Del: remove • Esc: clear brush')
        except (ValueError,IndexError,tk.TclError) as exc:ui.availability.set(str(exc))


class DungeonCollisionMixin:
    def toggle_collision_mode(self):
        self.finish_draw();self.selected_collision=None;self._collision_drag=None;self.tile_map_selection=None;self._tile_anchor=None
        if self.collision_mode.get():self.direct_draw.set(False);self.view_collisions.set(True)
        else:self.collision_brush=None
        if hasattr(self,"sprite_mode"):self.sprite_mode.set(False);self.selected_sprite=None;self._sprite_drag=None
        self.canvas.configure(cursor='crosshair' if self.collision_mode.get() or self.direct_draw.get() else '')
        self.draw()
    def open_collision_selector(self):
        if self.collision_selector is None:self.collision_selector=DungeonCollisionSelector(self)
        else:self.collision_selector.deiconify();self.collision_selector.lift()
    def collision_click(self,event,select=True):
        self.finish_draw();self._collision_drag=None;self.selected_collision=None
        cell=self.draw_cell(event)
        if cell is None:self.draw();return 'break'
        room,x,y=cell
        if room!=self.room:self.select_room(room,center=False)
        context,_=self.render_context(room)
        try:
            record=dungeon.read_room(self.data,context,room)
            for index,obj in reversed(list(enumerate(record.objects))):
                if any(pos==y*16+x for pos,tile in footprint(self.data,obj)):
                    self.selected_collision=(context,room,index,record.start,bytes(self.data[record.start:record.end]))
                    xy,tile,length,vertical=obj
                    if select:
                        self.collision_brush=tile;self.collision_direction.set('Vertical' if vertical else 'Horizontal' if length>1 else 'Single');self.collision_length.set(length)
                        self._collision_drag=(cell,obj,self.selected_collision)
                        if self.collision_selector is not None:self.collision_selector.select(tile)
                    break
            self.canvas.focus_set()
            if not select:
                self._collision_drag=None;self.delete_collision();return 'break'
            self.draw()
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
    def collision_paint_press(self,event):
        self._collision_delete_stroke=bool(getattr(event,'state',0)&4)
        if self._collision_delete_stroke:return self.collision_click(event,select=False)
        self._collision_paint_seen=set()
        return self.collision_paint_drag(event)

    def collision_paint_drag(self,event):
        if getattr(self,'_collision_delete_stroke',False):return 'break'
        cell=self.draw_cell(event);seen=getattr(self,'_collision_paint_seen',set())
        if cell is not None and cell not in seen:
            seen.add(cell);self._collision_paint_seen=seen
            return self.collision_place(event)
        return 'break'

    def collision_place(self,event):
        if not self.collision_mode.get() or self.collision_brush is None:return 'break'
        cell=self.draw_cell(event)
        if cell is None:return 'break'
        room,x,y=cell;context,_=self.render_context(room)
        try:
            changes=prepare_brush(self.data,context,room,x,y,self.collision_brush,self.collision_direction.get(),self.collision_length.get(),self.collision_combined.get())
            self.apply_room_changes(changes)
            if room!=self.room:self.select_room(room,center=False)
        except (ValueError,IndexError,tk.TclError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
    def collision_motion(self,event):
        if not self.collision_mode.get():return
        cell=self.draw_cell(event);drag=self._collision_drag
        if not cell:return
        if drag:
            start,obj,selected=drag
            if cell[0]!=start[0]:return
            xy,tile,length,vertical=obj
            x=xy%16+cell[1]-start[1];y=xy//16+cell[2]-start[2]
            self.collision_preview(cell[0],x,y,tile,'Vertical' if vertical else 'Horizontal' if length>1 else 'Single',length)
        return 'break'
    def collision_release(self,event):
        drag=self._collision_drag;self._collision_drag=None;self.canvas.delete('tool-ghost')
        if not drag:return 'break'
        cell=self.draw_cell(event);start,obj,selected=drag
        if cell is None or cell[0]!=start[0] or cell==start:return 'break'
        xy,tile,length,vertical=obj;x=xy%16+cell[1]-start[1];y=xy//16+cell[2]-start[2]
        context,room,index,at,raw=selected
        try:
            changes=prepare_brush(self.data,context,room,x,y,tile,'Vertical' if vertical else 'Horizontal' if length>1 else 'Single',length,self.collision_combined.get(),index=index,expected=(at,raw))
            self.apply_room_changes(changes);self.selected_collision=None;self.draw()
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'
    def collision_hover(self,event):
        if not self.collision_mode.get() or self._collision_drag or self.collision_brush is None:return
        cell=self.draw_cell(event)
        if cell is None:self.canvas.delete('tool-ghost');return
        try:self.collision_preview(*cell,self.collision_brush,self.collision_direction.get(),self.collision_length.get())
        except (ValueError,IndexError,tk.TclError):self.canvas.delete('tool-ghost')
    def room_origin(self,room):
        index=next((i for i,r in enumerate(self._layout) if r==room),None) if self.map_view() else 0
        if index is None:return None
        z=self.zoom.get()
        return 16+(index%self._cols*160*z if self.map_view() else 0),16+(index//self._cols*128*z if self.map_view() else 0)
    def brush_sheet(self,room):
        context,side=self.render_context(room);record=dungeon.read_room(self.data,context,room)
        raw,selector,warnings=dungeon.graphics(self.data,record,side)
        key=(context,room,side,raw,dungeon.attributes(self.data,context,room),dungeon.palette(self.data,context,side,room))
        if getattr(self,'_ghost_sheet_key',None)!=key:
            self._ghost_sheet,_=dungeon.tile_sheet(self.data,context,room,side);self._ghost_sheet_key=key
        return self._ghost_sheet

    def collision_preview(self,room,x,y,tile,direction,length):
        self.canvas.delete('tool-ghost');origin=self.room_origin(room)
        if origin is None:return
        sheet=self.brush_sheet(room)
        cells=[(x+dx,y+dy,t) for dx,dy,t in brush_cells(self.data,tile,direction,length) if 0<=x+dx<10 and 0<=y+dy<8]
        if not cells:return
        z=self.zoom.get();image=Image.new('RGBA',(160,128))
        for cx,cy,t in cells:image.paste(sheet.crop((t%16*16,t//16*16,t%16*16+16,t//16*16+16)).convert('RGBA'),(cx*16,cy*16))
        image.putalpha(image.getchannel('A').point(lambda value:value*150//255))
        self._ghost=ImageTk.PhotoImage(image.resize((160*z,128*z),Image.Resampling.NEAREST))
        self.canvas.create_image(*origin,image=self._ghost,anchor='nw',tags='tool-ghost')
        for cx,cy,t in cells:self.canvas.create_rectangle(origin[0]+cx*16*z,origin[1]+cy*16*z,origin[0]+(cx+1)*16*z,origin[1]+(cy+1)*16*z,outline='yellow',tags='tool-ghost')
    def collision_escape(self,event=None):
        self.selected_sprite=None;self._sprite_drag=None
        self.finish_draw();self._collision_drag=None;self.collision_brush=None;self.selected_collision=None
        self._tile_anchor=None;self.tile_map_selection=None;self.canvas.delete('tool-ghost');self.draw();return 'break'
    def delete_collision(self,event=None):
        if not self.collision_mode.get() or self.selected_collision is None:return
        self.finish_draw();context,room,index,start,raw=self.selected_collision
        try:
            changes=object_changes(self.data,context,room,index,delete=True,expected=(start,raw))
            self.apply_room_changes(changes)
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
        self.selected_collision=None;self._collision_drag=None;self.draw();return 'break'
    def calculate_collisions(self):
        if self.data is None:return
        self.finish_draw()
        try:
            context,_=self.render_context(self.room)
            from windfish.app.windfish_collision_settings import allowed_types
            changes,_=recalculate_changes(self.data,context,self.room,allowed_types(self, 'dungeon'))
            self.apply_room_changes(changes);self.selected_collision=None
        except (ValueError,IndexError) as exc:messagebox.showerror('Room editing', str(exc), parent=self)
    def draw_collision_overlay(self):
        if not self.view_collisions.get():return
        context,_=self.render_context(self.room)
        try:record=dungeon.read_room(self.data,context,self.room)
        except (ValueError,IndexError):return
        index=next((i for i,r in enumerate(self._layout) if r==self.room),None) if self.map_view() else 0
        if index is None:return
        z=self.zoom.get();ox=16+(index%self._cols*160*z if self.map_view() else 0);oy=16+(index//self._cols*128*z if self.map_view() else 0)
        selected=self.selected_collision[2] if self.selected_collision and self.selected_collision[:2]==(context,self.room) else None
        for i,obj in enumerate(record.objects):
            for pos,tile in footprint(self.data,obj):
                x=pos%16;y=pos//16
                if x<10 and y<8:
                    self.canvas.create_rectangle(ox+x*16*z+1,oy+y*16*z+1,ox+(x+1)*16*z-1,oy+(y+1)*16*z-1,outline='yellow' if i==selected else '#00ffff',width=2)
                    # Label the placed collision ID, including a door preset's own ID.
                    cx=ox+(x*16+8)*z;cy=oy+(y*16+8)*z
                    label=f'{obj[1]:02X}';font=('Consolas',max(7,4*z),'bold')
                    self.canvas.create_text(cx+1,cy+1,text=label,fill='black',font=font)
                    self.canvas.create_text(cx,cy,text=label,fill='yellow' if i==selected else 'white',font=font)


def brush_cells(data,tile,direction='Single',length=1):
    if direction not in ('Single','Horizontal','Vertical') or not isinstance(length,int) or not 1<=length<=15:
        raise ValueError('Length must be 1–15.')
    if not 0<=tile<254:raise ValueError('Collision ID must be 00–FD.')
    if tile>=0xEC:return [(pos%16,pos//16,value) for pos,value in dungeon.doors(data)[tile]]
    return [(0 if direction=='Vertical' else n,n if direction=='Vertical' else 0,tile) for n in range(1 if direction=='Single' else length)]


def encode_ordinary(x,y,tile,direction='Single',length=1):
    if not 0<=x<10 or not 0<=y<8 or not 0<=tile<0xEC or not 1<=length<=15:raise ValueError('Invalid ordinary dungeon collision.')
    return bytes((y*16+x,tile)) if direction=='Single' else bytes(((0xC0 if direction=='Vertical' else 0x80)|length,y*16+x,tile))


def encode_brush(data,x,y,tile,direction='Single',length=1):
    if not 0<=x<10 or not 0<=y<8:raise ValueError('Place the collision inside the room.')
    cells=brush_cells(data,tile,direction,length)
    if tile>=0xEC and all(0<=x+dx<10 and 0<=y+dy<8 for dx,dy,t in cells):return bytes((y*16+x,tile))
    from windfish.overworld.windfish_collision_recalculate import minimum_records
    return b''.join(minimum_records({(x+dx,y+dy):t for dx,dy,t in cells if 0<=x+dx<10 and 0<=y+dy<8},single_only=frozenset(),encoder=encode_ordinary))


def prepare_brush(data,map_id,room,x,y,tile,direction='Single',length=1,combined=False,index=None,delete=False,expected=None):
    if not storage.enabled(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    record,objects,warps=room_details(data,map_id,room);raw=bytes(data[record.start:record.end])
    if expected is not None and expected!=(record.start,raw):raise ValueError('Room objects changed. Select the collision again.')
    payload=bytearray(raw);affected=set()
    if index is not None:
        if not 0<=index<len(objects):raise ValueError('Select a collision.')
        row=objects[index];offset=int(row[1],16)-record.start;old=bytes.fromhex(row[-1])
        affected.update(pos for pos,value in footprint(data,record.objects[index]) if pos%16<10 and pos//16<8)
    else:offset=len(raw)-1;old=b''
    new=b'' if delete else encode_brush(data,x,y,tile,direction,length)
    payload[offset:offset+len(old)]=new
    changes=storage.replacement_changes(data,map_id,room,bytes(payload))
    if not combined:return changes
    if not delete:affected.update((y+dy)*16+x+dx for dx,dy,t in brush_cells(data,tile,direction,length) if 0<=x+dx<10 and 0<=y+dy<8)
    trial=bytearray(data)
    for at,before,after in changes:trial[at]=after
    cells=dungeon.layout(trial,dungeon.read_room(trial,map_id,room))
    vc=visuals.paint_cells_changes(trial,map_id,room,[(pos%16,pos//16,cells[pos//16*10+pos%16]) for pos in affected])
    for at,before,after in vc:trial[at]=after
    return [(at,data[at],trial[at]) for at in sorted({c[0] for c in changes+vc}) if data[at]!=trial[at]]


def detect_door_presets(data,desired,existing,event,allowed=None):
    """Recognize complete native door footprints; shutter intent follows event."""
    desired=list(desired);macros=[];covered=set();erase=set()
    table=dungeon.doors(data)
    for obj in existing:
        if obj[1]<0xEC:continue
        cells=footprint(data,obj);positions=[pos for pos,value in cells]
        covered.update(positions)
        if any(not 0<=pos//16<8 or not 0<=pos%16<10 for pos in positions):continue
        drawn=tuple(desired[pos//16*10+pos%16] for pos in positions)
        initial=tuple(value for pos,value in cells)
        closed=tuple(0x35+(obj[1]-0xF0)*2+i for i in range(2)) if 0xF0<=obj[1]<=0xF3 else ()
        if drawn==initial or drawn==closed:
            erase.update(positions)
            for pos,value in cells:desired[pos//16*10+pos%16]=value
    shutter=event&0xE0 in (0x20,0xC0)
    patterns=[]
    for direction in range(4):
        closed=((0,0x35+direction*2),(1 if direction<2 else 16,0x36+direction*2))
        patterns.append((0xF0+direction,closed))
        patterns.append(((0xF0 if shutter else 0xF4)+direction,table[0xF4+direction]))
    patterns.extend((tile,table[tile]) for tile in range(0xEC,0xF0))
    patterns.extend((tile,table[tile]) for tile in range(0xF8,0xFE))
    # Match the full entrance before any smaller pattern it might contain.
    patterns.sort(key=lambda item:-len(item[1]))
    for y in range(8):
        for x in range(10):
            xy=y*16+x
            for tile,pattern in patterns:
                if allowed is not None and tile not in allowed:continue
                positions=[xy+offset for offset,value in pattern]
                if any(pos in covered or not 0<=pos//16<8 or not 0<=pos%16<10 for pos in positions):continue
                if not all(desired[pos//16*10+pos%16]==value for pos,(_,value) in zip(positions,pattern)):continue
                macros.append((xy,tile,1,False));covered.update(positions);erase.update(positions)
                # Shutter loaders initially produce open tiles. The event closes
                # them at runtime; drawing the closed tiles must not override it.
                for offset,value in table[tile]:
                    pos=xy+offset;desired[pos//16*10+pos%16]=value
                break
    return tuple(macros),tuple(desired),erase


def recalculate_changes(data,map_id,room,allowed=None):
    """Rebuild ordinary tiles from artwork, retaining indoor presets and templates."""
    from dataclasses import replace
    from windfish.overworld.windfish_collision_recalculate import minimum_records
    if not storage.enabled(data):raise ValueError('Reopen the ROM and accept the expanded editing capabilities upgrade.')
    record,objects,warps=room_details(data,map_id,room)
    physical=dungeon.layout(data,record);desired=visuals.apply_to_cells(data,map_id,room,physical)
    # These ordinary IDs also register engine state while the stream loads.
    # Retain surviving registrations in order, rather than sorting them by ID.
    stateful={0x8E,0xA0,0xAA,0xAB,0xCF,0xD0,0xD1,0xD2,0xDB,0xDC}
    retained=[i for i,obj in enumerate(record.objects) if obj[1]>=0xEC or
        obj[1] in stateful and all(desired[pos//16*10+pos%16]==tile for pos,tile in footprint(data,obj) if pos%16<10 and pos//16<8)]
    macros=tuple(record.objects[i] for i in retained)
    from windfish.dungeon.windfish_dungeon_events import event_offset
    detected,desired,erase=detect_door_presets(data,desired,macros,data[event_offset(data,map_id,room)],allowed)
    macros+=detected
    base=dungeon.layout(data,replace(record,objects=macros))
    if allowed is not None:
        # Existing special registrations stay intact; unchecked ordinary IDs
        # fall back to the room template instead of generating new objects.
        desired=tuple(tile if tile in allowed else base[i] for i,tile in enumerate(desired))
        erase={pos for pos in erase if desired[pos//16*10+pos%16]!=physical[pos//16*10+pos%16]}
    tiles={(i%10,i//10):tile for i,tile in enumerate(desired) if tile!=base[i]}
    records=minimum_records(tiles,single_only=frozenset(),encoder=encode_ordinary)
    # Newly exposed stateful tiles belong with retained registrations, so a
    # second calculation produces the same stream rather than reordering it.
    records=[raw for raw in records if raw[-1] in stateful]+[raw for raw in records if raw[-1] not in stateful]
    # Keep the door/shutter/stair handlers in their original order.
    macro_raw=[bytes.fromhex(objects[i][-1]) for i in retained]+[bytes((xy,tile)) for xy,tile,length,vertical in detected]
    payload=bytes(data[record.start:record.start+2])+b''.join(macro_raw+records+[bytes.fromhex(row[-1]) for row in warps])+b'\xfe'
    changes=storage.replacement_changes(data,map_id,room,payload)
    trial=bytearray(data)
    for at,old,new in changes:trial[at]=new
    if dungeon.layout(trial,dungeon.read_room(trial,map_id,room))!=tuple(desired):raise ValueError('Calculated collision layout did not match the drawn tiles; no changes were made.')
    if erase and visuals.enabled(trial):
        vc=visuals.paint_cells_changes(trial,map_id,room,[(pos%16,pos//16,0) for pos in erase],erase=True)
        for at,old,new in vc:trial[at]=new
        changes=[(at,data[at],trial[at]) for at in sorted({c[0] for c in changes+vc}) if data[at]!=trial[at]]
    return changes,(record.end-record.start,len(payload))
