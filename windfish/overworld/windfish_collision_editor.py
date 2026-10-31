"""Collision overlays, placement selection, and editing controls."""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageDraw
from windfish.overworld.windfish_combined_placement import combined_edit_changes
from windfish.overworld.windfish_collision_brush import CollisionBrushMixin
from windfish.overworld.windfish_collision_definitions import fine_collision_mask
from windfish.overworld.windfish_collision_objects import expanded_cells, read_room_objects, COLLISION_TYPES, edit_collision_changes

COLORS = {0: '#777777', 1: '#E64C4C', 5: '#46C9DB', 6: '#55C95A', 7: '#3984F2'}

class CollisionEditorMixin(CollisionBrushMixin):
    def set_editing_mode(self, mode):
        self.end_stroke()
        self._collision_drag = None
        if hasattr(self,'warp_mode'):
            self.clear_warp_hover()
            self.warp_mode.set(mode=='warps')
        if mode=='warps':
            self._sprite_drag=None;self._sprite_drag_changed=False
            self._tile_select_start=None;self._tile_select_action=None;self._tile_select_target=None
            self._paint_drag_cell=None;self.tile_selection=None
        for name, flag in (('tiles', self.paint_mode), ('sprites', self.sprite_mode),
                           ('collisions', self.collision_mode)):
            flag.set(name == mode)
        self.collision_target = None
        self.collision_selected = None
        if mode == 'collisions':
            self.show_collisions.set(True)
        elif mode == 'sprites':
            self.show_sprites.set(True)
        self.show_room()

    def toggle_collision_mode(self):
        self.set_editing_mode('collisions' if self.collision_mode.get() else None)

    def collision_click(self, event, full):
        cell = self._sprite_cell(event, full)
        self.collision_target = None
        self.collision_selected = None
        if cell is None:
            self.show_room()
            return 'break'
        self.room, x, y = cell
        try:
            cells, sources = expanded_cells(self.data, self.room, self.alternate.get())
            obj = cells[y*10+x]
            if self.data[0x20AD4 + obj] == 0 and sources[y*10+x] is None:
                self.show_room()
                if self.inspector_window is not None and self.inspector_window.winfo_exists():
                    self.collision_list.selection_clear(0, 'end')
                return 'break'
            self.collision_target = cell
            source = sources[y*10+x]
            self.collision_selected = (self.room, bool(self.alternate.get() and self.room in self.collision_alternates), source) if source is not None else None
            self.show_room()
            if self.inspector_window is not None and self.inspector_window.winfo_exists():
                self.load_collision_controls()
                row = 0 if source is None else source+1
                self.collision_list.selection_clear(0, 'end')
                self.collision_list.selection_set(row)
                self.collision_list.see(row)
        except ValueError as exc:
            self.show_room()
            messagebox.showerror('Room editing', str(exc), parent=self)
        return 'break'

    def collision_overlay(self, image, room, zoom):
        if not self.show_collisions.get() or room != self.room:
            return image
        image = image.convert('RGBA')
        layer = Image.new('RGBA', image.size)
        draw = ImageDraw.Draw(layer)
        try:
            from windfish.rom.windfish_shared_map16 import physical_cells
            cells, sources = physical_cells(self.data, room, self.alternate.get())
            for i, obj in enumerate(cells):
                physics = self.data[0x20AD4 + obj]
                # Empty floor stays unobscured. Explicit pass-through placements
                # are outlined so they remain visible/selectable.
                if physics == 0 and sources[i] is None:
                    continue
                color = COLORS.get(physics, '#DA9F39')
                x, y = i % 10 * 16 * zoom, i // 10 * 16 * zoom
                box = (x, y, x+16*zoom-1, y+16*zoom-1)
                rgb = tuple(bytes.fromhex(color[1:]))
                mask=fine_collision_mask(self.data,obj)
                if mask is None:
                    draw.rectangle(box, fill=rgb+(65,), outline=rgb+(220,), width=max(1,zoom))
                else:
                    for q,solid in enumerate(mask):
                        if solid:
                            qx=x+(q%2)*8*zoom;qy=y+(q//2)*8*zoom
                            draw.rectangle((qx,qy,qx+8*zoom-1,qy+8*zoom-1),fill=rgb+(95,),outline=rgb+(220,))
                if zoom >= 2:
                    draw.text((x+2,y+2), f'{obj:02X}', fill='white', stroke_width=1, stroke_fill='black')
            selected = getattr(self,'collision_selected',None)
            target = self.collision_target
            if self.collision_mode.get() and selected and selected[:2] == (room, bool(self.alternate.get() and room in self.collision_alternates)):
                stream = read_room_objects(self.data,room,self.alternate.get())
                if selected[2] is not None and selected[2] < len(stream.entries):
                    entry = stream.entries[selected[2]]
                    if entry.kind == 'object' and (entry.raw[-1] < 0xF5 or entry.raw[-1] in (0xF5,0xFD)):
                        pos = entry.raw[-2]
                        count = entry.raw[0]&15 if len(entry.raw)==3 else 1
                        vertical = len(entry.raw)==3 and entry.raw[0]&64
                        x,y = pos&15,pos>>4
                        w,h = (3,2) if entry.raw[-1]==0xFD else (((2,2*count) if vertical else (2*count,2)) if entry.raw[-1]==0xF5 else ((1,count) if vertical else (count,1)))
                        draw.rectangle((x*16*zoom,y*16*zoom,(x+w)*16*zoom-1,(y+h)*16*zoom-1),outline='yellow',width=max(2,zoom))
                    else:
                        for i,source in enumerate(sources):
                            if source == selected[2]:
                                x,y=i%10,i//10
                                draw.rectangle((x*16*zoom,y*16*zoom,(x+1)*16*zoom-1,(y+1)*16*zoom-1),outline='yellow',width=max(2,zoom))
            elif self.collision_mode.get() and target and target[0] == room and self.data[0x20AD4 + cells[target[2]*10+target[1]]] != 0:
                _,x,y=target
                draw.rectangle((x*16*zoom,y*16*zoom,(x+1)*16*zoom-1,(y+1)*16*zoom-1),outline='yellow',width=max(2,zoom))
        except ValueError:
            draw.text((4,4), 'Collision decode unavailable', fill='yellow')
        return Image.alpha_composite(image,layer).convert('RGB')

    def draw_full_collisions(self):
        if not self.show_collisions.get():
            return
        from PIL import ImageTk
        canvas = self.map_canvas
        z = self.zoom.get()
        self._collision_photos = []
        room = self.room
        rx,ry=room%16,room//16
        px,py=rx*160*z-self.map_x,ry*128*z-self.map_y
        if px+160*z <= 0 or py+128*z <= 0 or px >= canvas.winfo_width() or py >= canvas.winfo_height():
            return
        if not self.room_in_overworld_area(room):return
        base=self.cached_room_render(room,special=self.alternate.get(),scale=1)[0]
        base=base.resize((160*z,128*z),Image.Resampling.NEAREST)
        photo=ImageTk.PhotoImage(self.collision_overlay(base,room,z))
        self._collision_photos.append(photo)
        canvas.create_image(px,py,image=photo,anchor='nw',tags='collisions')

    def create_collision_controls(self, page):
        fields=ttk.Frame(page)
        fields.pack(fill='x',pady=4)
        self.collision_x=tk.IntVar(value=0)
        self.collision_y=tk.IntVar(value=0)
        self.collision_length=tk.IntVar(value=1)
        self.collision_direction=tk.StringVar(value='Single')
        for column,(label,var,maximum) in enumerate((('X',self.collision_x,9),('Y',self.collision_y,7),('Length',self.collision_length,15))):
            ttk.Label(fields,text=label).grid(row=0,column=column)
            ttk.Spinbox(fields,from_=1 if label=='Length' else 0,to=maximum,textvariable=var,width=5).grid(row=1,column=column)
        ttk.Combobox(fields,textvariable=self.collision_direction,values=('Single','Horizontal','Vertical'),state='readonly',width=12).grid(row=1,column=3,padx=4)
        buttons=ttk.Frame(page)
        buttons.pack(fill='x')
        self.collision_apply=ttk.Button(buttons,text='Apply move / resize',command=self.apply_collision_edit)
        self.collision_apply.pack(side='left')
        self.collision_delete=ttk.Button(buttons,text='Delete placement',command=lambda:self.apply_collision_edit(delete=True))
        self.collision_delete.pack(side='left',padx=6)
        self.collision_edit_hint=tk.StringVar()
        ttk.Label(page,textvariable=self.collision_edit_hint,wraplength=430).pack(anchor='w',pady=4)
        self.collision_list.bind('<<ListboxSelect>>',self.select_collision_from_list)
        self.load_collision_controls()

    def select_collision_from_list(self,event=None):
        rows=self.collision_list.curselection()
        if not rows:return
        if not self.collision_mode.get():self.set_editing_mode('collisions')
        self.collision_selected=(self.room,bool(self.alternate.get() and self.room in self.collision_alternates),rows[0]-1) if rows[0] else None
        self.collision_target=None
        self.load_collision_controls()
        if self.collision_mode.get():self.show_room()

    def load_collision_controls(self):
        if not hasattr(self,'collision_apply'):return
        self.collision_apply.configure(state='disabled')
        self.collision_delete.configure(state='disabled')
        self.collision_edit_hint.set('Select a supported collision placement to move, resize or delete.')
        selected=getattr(self,'collision_selected',None)
        if not selected or selected[:2]!=(self.room,bool(self.alternate.get() and self.room in self.collision_alternates)):return
        try:
            stream=read_room_objects(self.data,self.room,self.alternate.get())
            entry=stream.entries[selected[2]]
        except (ValueError,IndexError):return
        if entry.kind!='object' or entry.raw[-1] not in COLLISION_TYPES.values():
            self.collision_edit_hint.set('Warp records and floor fill are read-only.')
            return
        pos=entry.raw[-2]
        self.collision_x.set(pos&15);self.collision_y.set(pos>>4)
        self.collision_length.set(entry.raw[0]&15 if len(entry.raw)==3 else 1)
        self.collision_direction.set(('Vertical' if entry.raw[0]&64 else 'Horizontal') if len(entry.raw)==3 else 'Single')
        self.collision_apply.configure(state='normal')
        self.collision_delete.configure(state='normal')
        self.collision_edit_hint.set('Tree length counts 2×2 trees. Graphics + collisions fills vacated cells with the floor tile.' if entry.raw[-1]==0xF5 else 'Move/resize fills vacated graphics when Graphics + collisions is enabled. Deletion always preserves artwork.')

    def apply_collision_edit(self,delete=False):
        selected=getattr(self,'collision_selected',None)
        if not selected:return
        try:
            room,alt,index=selected
            if (room,alt)!=(self.room,bool(self.alternate.get() and self.room in self.collision_alternates)):return
            prepare=combined_edit_changes if self.collision_combined.get() else edit_collision_changes
            changes=prepare(self.data,room,alt,index,self.collision_capacities,
                x=self.collision_x.get(),y=self.collision_y.get(),direction=self.collision_direction.get(),
                length=1 if self.collision_direction.get()=='Single' else self.collision_length.get(),delete=delete)
        except (ValueError,tk.TclError) as exc:
            messagebox.showerror('Cannot edit collision',str(exc),parent=self.inspector_window);return
        self.end_stroke()
        for offset,before,after in changes:
            self.history.record(offset,before,after,room,alt);self.data[offset]=after
        self.history.commit()
        self.collision_target=None
        if delete:self.collision_selected=None
        self.refresh_changed_rooms([(at,old,new,room,alt) for at,old,new in changes])

    def open_add_collisions(self):
        self.open_collision_brush_window()

    def delete_collision_selection(self):
        selected = self.collision_selected
        if not selected or self.document is None:
            return
        room,alt,index = selected
        if (room,alt) != (self.room,bool(self.alternate.get() and self.room in self.collision_alternates)):
            return
        try:
            prepare = combined_edit_changes if self.collision_combined.get() else edit_collision_changes
            changes = prepare(self.data,room,alt,index,self.collision_capacities,delete=True)
        except ValueError as exc:
            messagebox.showerror('Room editing', f'Cannot delete collision: {exc}', parent=self)
            return
        self.collision_selected = None
        self.collision_target = None
        self.commit_collision_changes(changes,room,alt)

    def recalculate_collisions(self):
        if self.document is None:return
        from windfish.overworld.windfish_collision_recalculate import recalculate_changes
        room=self.room;alt=bool(self.alternate.get() and room in self.collision_alternates)
        try:
            from windfish.app.windfish_collision_settings import allowed_types
            changes,(before,after,count)=recalculate_changes(self.data,room,alt,self.collision_capacities, allowed_types(self, 'overworld'))
        except ValueError as exc:
            messagebox.showerror('Room editing', f'Cannot recalculate collisions: {exc}', parent=self)
            self.collision_edit_hint.set(str(exc));return
        self.collision_selected=None;self.collision_target=None
        self.commit_collision_changes(changes,room,alt)
        text=f'Recalculated room {room:02X}: {before} → {after} bytes, {count} placements. Graphics and warps preserved.'
        self.collision_edit_hint.set(text)
