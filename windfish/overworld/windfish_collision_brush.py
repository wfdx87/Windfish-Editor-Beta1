"""Sprite-style collision catalog and map brush/drag interactions."""
import tkinter as tk
from tkinter import messagebox
from PIL import Image,ImageTk,ImageDraw
from windfish.overworld.windfish_collision_objects import COLLISION_TYPES, read_room_objects, expanded_cells, collision_changes, edit_collision_changes
from windfish.overworld.windfish_collision_catalog import MACRO_NAMES,TILE_NAMES,preset_tiles
from windfish.overworld.windfish_collision_definitions import SINGLE_ONLY, entrance_count, physics_description, placement_note
from windfish.rom.windfish_collision_storage import enabled as collision_expanded,free_bytes
from windfish.overworld.windfish_combined_placement import combined_placement_changes,combined_edit_changes


def footprint_cells(data,obj,direction,length):
    cells=preset_tiles(data,obj)
    count=1 if direction=='Single' else length
    if obj in SINGLE_ONLY:count=1
    step=2 if obj==0xF5 else 1
    return [(x+(0 if direction=='Vertical' else n*step),
             y+(n*step if direction=='Vertical' else 0),tile)
            for n in range(count) for x,y,tile in cells]


class CollisionBrushMixin:
    def open_collision_brush_window(self):
        if self.data is None:return
        old=getattr(self,'add_collision_window',None)
        if old is not None and old.winfo_exists():old.lift();return
        window=tk.Toplevel(self);self.add_collision_window=window
        from windfish.overworld.windfish_collision_palette import build_collision_palette
        window.transient(self)
        ui=build_collision_palette(window,self.collision_brush_direction,self.collision_brush_length,self.collision_combined,
            [MACRO_NAMES.get(obj,TILE_NAMES.get(obj,'Tile')) for obj in range(0xFE)])
        items,preview,availability,direction,length,help_text=(getattr(ui,name) for name in ('items','preview','availability','direction','length','help_text'))
        state={'obj':self.collision_brush if self.collision_brush is not None else 0}
        def refresh(*_):
            if not window.winfo_exists():return
            obj=state['obj'];supported=obj in COLLISION_TYPES.values()
            fixed=obj in SINGLE_ONLY
            if fixed:
                if self.collision_brush_direction.get()!='Single':self.collision_brush_direction.set('Single')
                if self.collision_brush_length.get()!=1:self.collision_brush_length.set(1)
            direction.configure(state='disabled' if fixed or not supported else 'readonly')
            length.configure(state='normal' if supported and not fixed and self.collision_brush_direction.get()!='Single' else 'disabled')
            try:
                count=self.collision_brush_length.get()
                if not 1<=count<=15:raise ValueError('Length must be 1–15')
                cells=footprint_cells(self.data,obj,self.collision_brush_direction.get() if supported else 'Single',count)
                minx=min(x for x,y,t in cells);miny=min(y for x,y,t in cells)
                w=max(x for x,y,t in cells)-minx+1;h=max(y for x,y,t in cells)-miny+1
                image=Image.new('RGB',(w*16,h*16),'#dddddd')
                alt=self.alternate.get() and self.room in self.collision_alternates
                for x,y,t in cells:image.paste(self._tile_image(self.room,alt,t),((x-minx)*16,(y-miny)*16))
                scale=max(0.1,min(3,(max(20,preview.winfo_width())-12)/image.width,(max(20,preview.winfo_height())-8)/image.height))
                image=image.resize((max(1,int(image.width*scale)),max(1,int(image.height*scale))),Image.Resampling.NEAREST)
                preview.photo=ImageTk.PhotoImage(image);preview.delete('all')
                preview.create_image(preview.winfo_width()/2,preview.winfo_height()/2,image=preview.photo)
                stream=read_room_objects(self.data,self.room,self.alternate.get())
                original=self.collision_capacities.get((self.room,bool(alt)))
                free=free_bytes(self.data) if collision_expanded(self.data) else (max(0,original.end-stream.end) if original else 0)
                budget='shared pool' if collision_expanded(self.data) else 'room'
                note=f'{obj:02X} • {w}×{h} cells • '+('Ready to place' if supported else 'Preview only — placement not verified yet')
                if obj==0xF5:note+=' • Length counts 2×2 trees'
                if entrance_count(obj):note+=f' • Registers {entrance_count(obj)} entrance(s)'
                if obj<0xF5:note+=' • '+physics_description(self.data,obj)
                note+='\n'+placement_note(obj)
                availability.set(note)
                help_text.set(f'Room {self.room:02X} • {free} bytes free ({budget}) | Left: select/drag • Right: place • Ctrl+Right: remove • Del: remove • Esc: clear brush')
            except (ValueError,tk.TclError) as exc:availability.set(str(exc))
        def select(event=None):
            rows=items.curselection()
            if not rows:return
            state['obj']=rows[0]
            self.collision_brush=rows[0] if rows[0] in COLLISION_TYPES.values() else None
            if self.collision_brush is not None:self.set_editing_mode('collisions')
            else:self.show_room()
            refresh()
        self._refresh_add_collisions=refresh
        self._collision_catalog_select=lambda obj: (items.selection_clear(0,'end'),items.selection_set(obj),items.see(obj),state.update(obj=obj),refresh())
        items.bind('<<ListboxSelect>>',select)
        preview.bind('<Configure>',refresh)
        window.bind('<FocusIn>',refresh)
        traces=[(self.collision_brush_direction,self.collision_brush_direction.trace_add('write',refresh)),(self.collision_brush_length,self.collision_brush_length.trace_add('write',refresh))]
        def close():
            for var,token in traces:var.trace_remove('write',token)
            self._refresh_add_collisions=None;self._collision_catalog_select=None
            window.destroy()
        window.protocol('WM_DELETE_WINDOW',close)
        items.selection_set(state['obj']);items.see(state['obj'])
        # Opening the catalog selects a brush just like Add Sprites.
        select();window.after_idle(refresh)

    def collision_place_at(self,event,full):
        if not self.collision_mode.get():return
        cell=self._sprite_cell(event,full)
        if cell is None or self.collision_brush is None:return 'break'
        room,x,y=cell
        try:
            direction=self.collision_brush_direction.get()
            length=1 if direction=='Single' else self.collision_brush_length.get()
            prepare=combined_placement_changes if self.collision_combined.get() else collision_changes
            changes=prepare(self.data,room,self.alternate.get(),x,y,self.collision_capacities,self.collision_brush,direction,length)
        except (ValueError,tk.TclError) as exc:
            messagebox.showerror('Cannot place collision',str(exc),parent=self);return 'break'
        self.commit_collision_changes(changes,room,self.alternate.get())
        _,sources=expanded_cells(self.data,room,self.alternate.get())
        owner=sources[y*10+x]
        self.collision_selected=(room,bool(self.alternate.get() and room in self.collision_alternates),owner) if owner is not None else None
        self.collision_target=cell
        self.show_room()
        return 'break'

    def commit_collision_changes(self,changes,room,alt):
        self.end_stroke()
        for at,old,new in changes:
            self.history.record(at,old,new,room,alt);self.data[at]=new
        self.history.commit();self.room=room
        self.refresh_changed_rooms([(at,old,new,room,alt) for at,old,new in changes])

    def collision_paint_drag(self,event,full):
        if getattr(self,'_collision_delete_stroke',False):return 'break'
        cell=self._sprite_cell(event,full)
        seen=getattr(self,'_collision_paint_seen',set())
        if cell is not None and cell not in seen:
            seen.add(cell);self._collision_paint_seen=seen
            return self.collision_place_at(event,full)
        return 'break'

    def collision_left_press(self,event,full):
        widget = getattr(event,'widget',None)
        if hasattr(widget,'focus_set'): widget.focus_set()
        self.collision_click(event,full)
        self._collision_drag=None
        selected=self.collision_selected
        cell=self._sprite_cell(event,full)
        if selected and cell:
            entry=read_room_objects(self.data,self.room,self.alternate.get()).entries[selected[2]]
            if entry.kind=='object' and entry.raw[-1] in COLLISION_TYPES.values():
                pos=entry.raw[-2];direction=('Vertical' if entry.raw[0]&64 else 'Horizontal') if len(entry.raw)==3 else 'Single'
                length=entry.raw[0]&15 if len(entry.raw)==3 else 1
                self.collision_brush=entry.raw[-1]
                callback=getattr(self,'_collision_catalog_select',None)
                if callback:callback(entry.raw[-1])
                self.collision_brush_direction.set(direction);self.collision_brush_length.set(length)
                self._collision_drag=(selected,cell,pos&15,pos>>4,direction,length,entry.raw[-1])
        return 'break'

    def collision_drag_motion(self,event,full):
        drag=getattr(self,'_collision_drag',None)
        cell=self._sprite_cell(event,full)
        if not drag or not cell or cell[0]!=drag[0][0]:return
        selected,start,x,y,direction,length,obj=drag
        self.collision_preview_at((cell[0],x+cell[1]-start[1],y+cell[2]-start[2]),full,obj,direction,length)
        return 'break'

    def collision_drag_release(self,event,full):
        drag=getattr(self,'_collision_drag',None);self._collision_drag=None
        cell=self._sprite_cell(event,full)
        if not drag or not cell or cell[0]!=drag[0][0]:self.show_room();return
        selected,start,x,y,direction,length,obj=drag
        nx,ny=x+cell[1]-start[1],y+cell[2]-start[2]
        if (nx,ny)==(x,y):self.show_room();return
        try:
            prepare=combined_edit_changes if self.collision_combined.get() else edit_collision_changes
            changes=prepare(self.data,selected[0],selected[1],selected[2],self.collision_capacities,x=nx,y=ny,direction=direction,length=length)
            self.commit_collision_changes(changes,selected[0],selected[1])
        except ValueError as exc:messagebox.showerror('Cannot move collision',str(exc),parent=self);self.show_room()
        return 'break'

    def collision_hover(self,event,full):
        if not self.collision_mode.get() or getattr(self,'_collision_drag',None) or self.collision_brush is None:return
        cell=self._sprite_cell(event,full)
        if cell is None:return
        try:self.collision_preview_at(cell,full,self.collision_brush,self.collision_brush_direction.get(),1 if self.collision_brush_direction.get()=='Single' else self.collision_brush_length.get())
        except (ValueError,tk.TclError):pass

    def collision_preview_at(self,cell,full,obj,direction,length):
        room,x,y=cell
        # A selected-room-only overlay is retained during full-map hover.
        cells=footprint_cells(self.data,obj,direction,length)
        cells=[(a,b,t) for a,b,t in cells if 0<=x+a<10 and 0<=y+b<8]
        if not cells:return
        minx=min(a for a,b,t in cells);miny=min(b for a,b,t in cells)
        w=max(a for a,b,t in cells)-minx+1;h=max(b for a,b,t in cells)-miny+1
        valid=True
        try:
            from windfish.overworld.windfish_collision_objects import clipped_placement_records
            clipped_placement_records(self.data,room,self.alternate.get(),x,y,obj,direction,length)
        except ValueError:valid=False
        image=Image.new('RGBA',(w*16,h*16))
        alt=self.alternate.get() and room in self.collision_alternates
        for a,b,t in cells:image.paste(self._tile_image(room,alt,t).convert('RGBA'),((a-minx)*16,(b-miny)*16))
        image.putalpha(image.getchannel('A').point(lambda value:value*150//255))
        z=self.zoom.get();image=image.resize((w*16*z,h*16*z),Image.Resampling.NEAREST)
        ImageDraw.Draw(image).rectangle((0,0,image.width-1,image.height-1),outline='yellow' if valid else 'red',width=max(2,z))
        if full:
            self.map_canvas.delete('collision-ghost')
            self._collision_ghost_photo=ImageTk.PhotoImage(image)
            self.map_canvas.create_image(((room%16)*160+(x+minx)*16)*z-self.map_x,((room//16)*128+(y+miny)*16)*z-self.map_y,image=self._collision_ghost_photo,anchor='nw',tags='collision-ghost')
        else:
            base=getattr(self,'_collision_hover_background',None)
            if base is None:
                base=self._room_image_cache.get((room,bool(alt),z))
                if base is None:return
                base=self.collision_overlay(base,room,z)
                base=self.draw_sprite_positions_on_image(base,room,z)
                self._collision_hover_background=base
            result=base.convert('RGBA');result.alpha_composite(image,((x+minx)*16*z,(y+miny)*16*z))
            self._collision_ghost_photo=ImageTk.PhotoImage(result)
            self.preview.configure(image=self._collision_ghost_photo)

    def collision_leave(self,event=None,full=False):
        if self.collision_mode.get() and not getattr(self,'_collision_drag',None):
            if full:self.map_canvas.delete('collision-ghost')
            else:self.show_room()

    def collision_escape(self,event=None):
        if self.collision_mode.get():
            self.collision_brush=None;self._collision_drag=None;self.collision_selected=None;self.collision_target=None
            self.show_room();return 'break'
