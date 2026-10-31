"""Map-click tool for adding an overworld warp destination record.

The clicked tile supplies an initial arrival position, converted to Link's
pixel-coordinate convention. Entrance objects still determine activation.
"""
from tkinter import messagebox
from PIL import ImageDraw, ImageTk
from windfish.overworld.windfish_warps import room_warps, resize_warps
from windfish.overworld.windfish_collision_objects import ALTERNATE_POINTERS


class WarpPlacementMixin:
    def toggle_warp_mode(self):
        self.set_editing_mode('warps' if self.warp_mode.get() else None)

    def open_warp_properties(self,index=None):
        self.show_inspector.set(True)
        self.toggle_inspector()
        self.update_inspector()
        self.property_tabs.select(self.warp_page)
        if index is not None and self._warp_records:
            index=min(index,len(self._warp_records)-1)
            self.warp_list.selection_clear(0,'end')
            self.warp_list.selection_set(index)
            self.warp_list.activate(index)
            self.warp_list.see(index)
            self.select_warp()

    def place_warp(self,event,full):
        if self.document is None or not self.warp_mode.get():return 'break'
        cell=self._sprite_cell(event,full)
        if cell is None:return 'break'
        room,x,y=cell
        alternate=bool(self.alternate.get() and room in ALTERNATE_POINTERS)
        self.end_stroke()
        self.room=room
        try:
            records=room_warps(self.data,room,alternate)
            if len(records)>=4:
                self.show_room()
                self.open_warp_properties()
                messagebox.showwarning('Too many warps',
                    'There are too many warps in this room. A room supports at most 4 warps.',
                    parent=self.inspector_window)
                return 'break'
            changes=resize_warps(self.data,room,alternate,self.collision_capacities,
                expected=tuple(record.raw for record in records),
                arrival=(x*16+8,y*16+16))
        except ValueError as exc:
            self.show_room()
            self.open_warp_properties()
            messagebox.showerror('Cannot add warp',str(exc),parent=self.inspector_window)
            return 'break'
        for at,before,after in changes:
            self.data[at]=after
            self.history.record(at,before,after,room,alternate)
        self.history.commit()
        self.show_room()
        self.open_warp_properties(index=len(records))
        self.warp_status.set('Warp added. Set its destination and click Apply warp changes.')
        return 'break'

    def warp_hover(self,event,full):
        if not self.warp_mode.get() or self.data is None:return
        cell=self._sprite_cell(event,full)
        if cell is None:
            self.clear_warp_hover(full=full)
            return
        room,x,y=cell;z=self.zoom.get()
        # Motion within one cell needs no work. Include the displayed image and
        # viewport origin so zooms, room edits and panning invalidate the ghost.
        key=(full,cell,z,id(self.image_ref),self.map_x,self.map_y)
        if key==getattr(self,'_warp_hover_key',None):return
        self._warp_hover_key=key
        if full:
            self.map_canvas.delete('warp-ghost')
            px=((room%16)*160+x*16)*z-self.map_x
            py=((room//16)*128+y*16)*z-self.map_y
            self.map_canvas.create_rectangle(px,py,px+16*z-1,py+16*z-1,
                outline='#ffff00',width=max(2,z),tags='warp-ghost')
        elif self.image_ref is not None:
            # Reuse the already displayed room, including sprite/collision
            # overlays. No ROM decoding or full-map redraw occurs on hover.
            if getattr(self,'_warp_hover_source',None) is not self.image_ref:
                self._warp_hover_source=self.image_ref
                self._warp_hover_background=ImageTk.getimage(self.image_ref)
            image=self._warp_hover_background.copy()
            ImageDraw.Draw(image).rectangle((x*16*z,y*16*z,(x+1)*16*z-1,(y+1)*16*z-1),
                outline='#ffff00',width=max(2,z))
            self._warp_hover_photo=ImageTk.PhotoImage(image)
            self.preview.configure(image=self._warp_hover_photo)

    def clear_warp_hover(self,event=None,full=None):
        self._warp_hover_key=None
        self._warp_hover_background=None
        self._warp_hover_source=None
        if full is not False:self.map_canvas.delete('warp-ghost')
        if full is not True and self.image_ref is not None:
            self.preview.configure(image=self.image_ref)
        self._warp_hover_photo=None

    def warp_escape(self,event=None):
        if self.warp_mode.get():
            self.set_editing_mode(None)
            return 'break'
