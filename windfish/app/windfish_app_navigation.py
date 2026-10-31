"""Room navigation, viewport rendering and auxiliary-window restoration.

Methods keep the Viewer interface and call the existing guarded backends.
The application composes this mixin; it must not import Viewer.
"""
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
from windfish.rendering.windfish_overworld_render import SPECIAL_MAP
from windfish.app.windfish_room_grid import centered_geometry, room_at, room_rect


class AppNavigationMixin:
    def move_room(self, dx, dy):
        if self.data is None:
            return
        x, y = self.room % 16, self.room // 16
        nx, ny = x + dx, y + dy
        # Do not wrap around at any edge of the 16 x 16 overworld.
        if not (0 <= nx < 16 and 0 <= ny < 16):
            return
        self.end_stroke()
        area=getattr(self,'_overworld_area',None)
        if self.full_map.get() and area and not (area[0]<=nx<=area[2] and area[1]<=ny<=area[3]):return
        self.room = ny * 16 + nx
        if self.full_map.get():self.center_full_map_room(self.room)
        self.show_room()


    def change_zoom(self, delta):
        if self.data is None:
            return
        new_zoom = max(1, min(4, self.zoom.get() + delta))
        if new_zoom != self.zoom.get():
            self.zoom.set(new_zoom)
            self.show_room()


    def toggle_alternate_rooms(self):
        """Show all six alternate overlays wherever they exist, independent of selection."""
        if self.data is None:
            self.alternate.set(False)
            return
        self.show_room()


    def toggle_alternate_map(self):
        # Keyboard shortcut controls the same global option as the sidebar.
        if self.data is None:
            return
        self.alternate.set(not self.alternate.get())
        self.toggle_alternate_rooms()


    def toggle_navigator(self):
        if self.show_navigator.get():
            self.nav.pack(side='top', fill='x')
        else:
            self.nav.pack_forget()
        self.draw_nav()


    def _set_render_padding(self):
        # Always use exactly 16 GUI pixels, regardless of room size or zoom.
        self.render_area.configure(padding=(16, 16, 0, 0))


    def center_full_map_room(self, room):
        """Center the selected room in the visible map viewport, clamped at edges."""
        z = self.zoom.get()
        width = max(1, self.map_canvas.winfo_width())
        height = max(1, self.map_canvas.winfo_height())
        col, row = room % 16, room // 16
        x0,y0,x1,y1=self.overworld_pixel_bounds()
        self.map_x = max(x0*z,min(int((col+0.5)*160*z-width/2),max(x0*z,x1*z-width)))
        self.map_y = max(y0*z,min(int((row+0.5)*128*z-height/2),max(y0*z,y1*z-height)))


    def on_main_unmap(self, event):
        if event.widget is self and self.nav_window is not None and self.nav_window.winfo_exists():
            if self.state() in ('iconic', 'withdrawn'):
                self.nav_window.withdraw()
        if event.widget is self and self.inspector_window is not None and self.inspector_window.winfo_exists():
            if self.state() in ('iconic', 'withdrawn'):
                self.inspector_window.withdraw()


    def on_main_map(self, event):
        if event.widget is self:
            self.queue_auxiliary_restore()


    def on_main_focus(self, event):
        # On Windows, a transient tool window may finish hiding after <Map>,
        # especially when a combo box held focus during minimization.
        if event.widget.winfo_toplevel() is self:
            self.queue_auxiliary_restore()


    def queue_auxiliary_restore(self):
        pending = getattr(self, '_auxiliary_restore_job', None)
        if pending is not None:
            self.after_cancel(pending)
        self._auxiliary_restore_job = self.after(100, self.restore_auxiliary_windows)


    def restore_auxiliary_windows(self):
        self._auxiliary_restore_job = None
        if self.state() in ('iconic', 'withdrawn') or not self.winfo_viewable():
            return
        for window, requested in ((self.nav_window, self.show_navigator),
                                  (self.inspector_window, self.show_inspector)):
            if not requested.get():
                continue
            if window is None or not window.winfo_exists():
                if requested is self.show_inspector:
                    requested.set(False)
                continue
            if window.state() in ('iconic', 'withdrawn') or not window.winfo_viewable():
                window.deiconify()
                window.lift(self)


    def draw_nav(self):
        if self.nav is None or not self.nav.winfo_exists():
            return
        self.nav.delete('all')
        w, h = max(1,self.nav.winfo_width()), max(1,self.nav.winfo_height())
        ox,oy,cell = centered_geometry(w, h)
        self.nav_rect = (ox,oy,cell)
        for r in range(256):
            x0,y0,_,_ = room_rect(r, self.nav_rect)
            fill='#587f65' if self.alternate.get() and r in SPECIAL_MAP else '#39495c'
            if r==self.room: fill='#e0a84b'
            area=getattr(self,'_overworld_area',None)
            if area and area[0]<=r%16<=area[2] and area[1]<=r//16<=area[3] and r!=self.room:fill='#567dad'
            self.nav.create_rectangle(x0,y0,x0+cell,y0+cell,fill=fill,outline='#89929b',width=0.5)
            if cell>=16:
                self.nav.create_text(x0+cell/2,y0+cell/2,text=f'{r:02X}',fill='#fff' if r!=self.room else '#151515',font=('Consolas',max(6,int(cell*.32))))


    def overworld_pixel_bounds(self):
        x0,y0,x1,y1=getattr(self,'_overworld_area',None) or (0,0,15,15)
        return x0*160,y0*128,(x1+1)*160,(y1+1)*128

    def room_in_overworld_area(self,room):
        area=getattr(self,'_overworld_area',None)
        return area is None or area[0]<=room%16<=area[2] and area[1]<=room//16<=area[3]

    def begin_nav_area(self,event):
        if self.data is None or not self.full_map.get():return
        self._nav_area_start=room_at(event.x,event.y,self.nav_rect)
        if self._nav_area_start is not None:self.drag_nav_area(event)
        return 'break'

    def drag_nav_area(self,event):
        start=getattr(self,'_nav_area_start',None)
        if start is None or not self.full_map.get():return
        ox,oy,cell=self.nav_rect
        x=max(0,min(15,int((event.x-ox)//cell)));y=max(0,min(15,int((event.y-oy)//cell)))
        sx,sy=start%16,start//16
        self._overworld_area=(min(sx,x),min(sy,y),max(sx,x),max(sy,y))
        if not self.room_in_overworld_area(self.room):self.room=start
        self.center_full_map_room(self.room);self.draw_nav();self.draw_full_map()
        return 'break'

    def end_nav_area(self,event):
        self.drag_nav_area(event);self._nav_area_start=None
        if self.full_map.get():self.show_room()
        return 'break'

    def select_from_map(self,event):
        room = room_at(event.x, event.y, self.nav_rect)
        if room is not None:
            if self.full_map.get() and not self.room_in_overworld_area(room):return
            self.room=room
            if self.full_map.get():
                self.center_full_map_room(self.room)
            self.show_room()


    def change_map_mode(self):
        if not self.full_map.get():self._overworld_area=None
        self._set_render_padding()
        if self.data is None:
            self.full_map.set(False)
        if self.full_map.get():
            self.preview.pack_forget()
            self.map_canvas.pack(fill='both', expand=True)
            self.center_full_map_room(self.room)
        else:
            self.map_canvas.pack_forget()
            self.preview.pack(anchor='nw')
        self.show_room()


    def _draw_room_border_on_image(self, image, zoom):
        if not self.room_borders.get():
            return image
        image = image.copy()
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, image.width - 1, image.height - 1),
                       outline='#ffffff', width=max(2, zoom))
        return image


    def draw_full_map(self):
        if not self.full_map.get() or self.data is None:
            return
        canvas = self.map_canvas
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w < 2 or h < 2:
            return
        z = self.zoom.get()
        x0,y0,x1,y1=self.overworld_pixel_bounds()
        world_w,world_h=x1*z,y1*z
        self.map_x=max(x0*z,min(self.map_x,max(x0*z,world_w-w)))
        self.map_y=max(y0*z,min(self.map_y,max(y0*z,world_h-h)))
        draw_w=min(w,world_w-self.map_x);draw_h=min(h,world_h-self.map_y)
        left,top=self.map_x//z,self.map_y//z
        right=min(x1,(self.map_x+draw_w+z-1)//z);bottom=min(y1,(self.map_y+draw_h+z-1)//z)
        from windfish.rendering.windfish_viewport import compose
        # The ROM cannot change during this synchronous draw. Hash it once,
        # and retain enough native-size room entries for the visible viewport.
        revision=self._visual_revision()
        room_count=((right+159)//160-left//160)*((bottom+127)//128-top//128)
        self._visual_cache.reserve_visible(room_count)
        piece=compose(16,16,(left,top,right,bottom),lambda room:self.cached_room_render(
            room,special=self.alternate.get() and room in SPECIAL_MAP,scale=1,revision=revision)[0])
        if z != 1:
            piece = piece.resize((piece.width * z, piece.height * z), Image.Resampling.NEAREST)
        canvas.delete('all')
        self.image_ref = ImageTk.PhotoImage(piece)
        canvas.create_image(left * z - self.map_x, top * z - self.map_y,
                            image=self.image_ref, anchor='nw')
        self.draw_full_collisions()
        if self.room_borders.get():
            for col in range(17):
                x = col * 160 * z - self.map_x
                if x0<=col*160<=x1 and 0 <= x <= w:
                    canvas.create_line(x, 0, x, min(h, world_h-self.map_y), fill='#ffffff', width=max(2,z))
            for row in range(17):
                y = row * 128 * z - self.map_y
                if y0<=row*128<=y1 and 0 <= y <= h:
                    canvas.create_line(0, y, min(w, world_w-self.map_x), y, fill='#ffffff', width=max(2,z))
        self.draw_sprite_positions_on_canvas(revision=revision)
        self._draw_full_tile_selection(canvas,z)


    def pan_start(self, event):
        self.drag_start = (event.x, event.y, self.map_x, self.map_y)


    def pan_move(self, event):
        if self.drag_start is None:
            return
        x, y, ox, oy = self.drag_start
        self.map_x = ox + x - event.x
        self.map_y = oy + y - event.y
        self.draw_full_map()


    def pan_end(self, event):
        self.drag_start = None


    def select_full_map_room(self, event):
        if self.data is None:
            return
        x = (self.map_x + event.x) // (160 * self.zoom.get())
        y = (self.map_y + event.y) // (128 * self.zoom.get())
        if 0 <= x < 16 and 0 <= y < 16 and self.room_in_overworld_area(int(y*16+x)):
            self.room = int(y * 16 + x)
            self.show_room()


    def refresh_selected_room_context(self):
        """Update room-bound controls without invalidating or rebuilding atlases.

        Tile-mode clicks use the lightweight selection redraw, so they must
        explicitly notify floating editors when the active room changes. Keep
        this separate from show_room, which also handles document-wide refresh.
        """
        self.refresh_title()
        self.draw_nav()
        self.update_room_settings()
        self.update_inspector()
        self.update_bg_palette_editor()
        self.refresh_tile_definition_editor()
        self._collision_hover_background = None
        window = getattr(self, 'add_collision_window', None)
        if window is not None and window.winfo_exists():
            refresh = getattr(self, '_refresh_add_collisions', None)
            if refresh is not None:
                refresh()
        for catalog in self.catalog_windows.values():
            if catalog.winfo_exists():
                catalog.event_generate('<<WindfishRoomChanged>>', when='tail')

    def show_room(self):
        text_editor = getattr(self, 'text_editor_window', None)
        if text_editor is not None and text_editor.winfo_exists():
            text_editor.refresh()
        self.refresh_visual_cache()
        dungeon=getattr(self,'dungeon_window',None)
        if dungeon is not None and dungeon.winfo_exists():dungeon.sync_if_new_document()
        self.refresh_tile_definition_editor()
        self._collision_hover_background = None
        window = getattr(self,'add_collision_window',None)
        if self.data is not None and window is not None and window.winfo_exists():
            refresh = getattr(self,'_refresh_add_collisions',None)
            if refresh is not None:refresh()
        self._set_render_padding()
        for catalog in self.catalog_windows.values():
            if catalog.winfo_exists():
                catalog.event_generate('<<WindfishRoomChanged>>', when='tail')
        self.refresh_title()
        self.draw_nav()
        self.update_room_settings()
        self.update_inspector()
        self.update_bg_palette_editor()
        if self.data is None:return
        try:
            if self.full_map.get():
                self.draw_full_map()
                return
            scale=self.zoom.get()
            img,_,_=self.cached_room_render(self.room,special=(self.alternate.get() and self.room in SPECIAL_MAP),scale=scale)
            self._room_image_cache[(self.room,self.alternate.get() and self.room in SPECIAL_MAP,scale)] = img
            while len(self._room_image_cache)>8:self._room_image_cache.pop(next(iter(self._room_image_cache)))
            img = self.collision_overlay(img,self.room,scale)
            img = self._draw_tile_selection(img,self.room,scale)
            img = self.draw_sprite_positions_on_image(img, self.room, scale)
            img = self._draw_room_border_on_image(img, scale)
            self.image_ref=ImageTk.PhotoImage(img)
            self.preview.configure(image=self.image_ref,text='')
        except Exception as exc:
            self.preview.configure(image='',text='Rendering failed')
            messagebox.showerror('Rendering error',str(exc))


