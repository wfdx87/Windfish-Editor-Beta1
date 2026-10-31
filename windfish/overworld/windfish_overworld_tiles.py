"""Overworld tile selection, direct painting and tile-move previews.

Methods keep the Viewer interface and call the existing guarded backends.
The application composes this mixin; it must not import Viewer.
"""
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps
from windfish.rendering.windfish_overworld_render import SPECIAL_MAP, direct_map


class OverworldTilesMixin:
    def update_edit_mode(self):
        self.set_editing_mode('tiles' if self.paint_mode.get() else None)


    def toggle_sprite_mode(self):
        self.set_editing_mode('sprites' if self.sprite_mode.get() else None)


    def _selection_cell(self, event, full):
        return self._sprite_cell(event, full)


    def _read_tile_selection(self, room, x0, y0, x1, y1):
        alt = self.alternate.get() and room in SPECIAL_MAP
        from windfish.rom.windfish_shared_map16 import cells
        data = cells(self.data,room,alt)
        return (room, alt, x0, y0, x1-x0+1, y1-y0+1,
                tuple(data[y*10+x] for y in range(y0,y1+1) for x in range(x0,x1+1)))


    def _tile_left_press(self, event, full):
        cell = self._selection_cell(event, full)
        if cell is None:return 'break'
        room,x,y=cell
        sel=self.tile_selection
        if sel and sel[2]>=0 and room==sel[0] and sel[2]<=x<sel[2]+sel[4] and sel[3]<=y<sel[3]+sel[5]:
            self._tile_select_action='move'
        else:
            self._tile_select_action='select'
            self.tile_selection=self._read_tile_selection(room,x,y,x,y)
        self._tile_select_start=cell
        self._tile_select_target=cell
        room_changed = self.room != room
        self.room = room
        if room_changed:
            self.refresh_selected_room_context()
        self._refresh_selection_only()
        return 'break'


    def _tile_left_motion(self, event, full):
        if self._tile_select_start is None:return 'break'
        cell=self._selection_cell(event,full)
        if cell is None:return 'break'
        room,x,y=cell
        sr,sx,sy=self._tile_select_start
        if room!=sr:return 'break'
        if cell==self._tile_select_target:return 'break'
        self._tile_select_target=cell
        if self._tile_select_action=='move':
            self._preview_tile_move(cell,full)
            return 'break'
        if self._tile_select_action=='select':
            self.tile_selection=self._read_tile_selection(room,min(sx,x),min(sy,y),max(sx,x),max(sy,y))
        self._refresh_selection_only()
        return 'break'


    def _write_tile_block(self, sel, room, x0, y0, move=False):
        if self.document is None:return
        srcroom, alt, sx, sy, width, height, values=sel
        target_alt=self.alternate.get() and room in SPECIAL_MAP
        if move and (srcroom!=room or alt!=target_alt):return
        changes=[]
        if move:
            for j in range(height):
                for i in range(width):
                    changes.append((srcroom,sx+i,sy+j,0,alt))
        world_x=(room%16)*10+x0
        world_y=(room//16)*8+y0
        for j in range(height):
            for i in range(width):
                # Single-room view clips the stamp to the displayed room.
                # Only entire-overworld view permits painting into neighbors.
                local_x,local_y=x0+i,y0+j
                if not self.full_map.get() and not (0<=local_x<10 and 0<=local_y<8):
                    continue
                gx,gy=world_x+i,world_y+j
                if not (0<=gx<160 and 0<=gy<128):continue
                r=(gy//8)*16+gx//10
                a=self.alternate.get() and r in SPECIAL_MAP
                changes.append((r,gx%10,gy%8,values[j*width+i],a))
        if not changes:return
        from windfish.rom import windfish_shared_map16 as shared
        if shared.enabled(self.data):
            previous_selection=self.tile_selection
            if sx>=0 or move:
                self.tile_selection=(room,target_alt,x0,y0,width,height,values)
            if not self.apply_shared_tile_draw(changes,room):self.tile_selection=previous_selection
            return
        if self.direct_add_collisions.get():
            if self.apply_direct_collision_draw(changes,room) and (sx >= 0 or move):
                self.tile_selection=(room,target_alt,x0,y0,width,height,values)
                self._refresh_selection_only()
            return
        self.end_stroke()
        for r,x,y,t,a in changes:
            offset,before,after=self.document.set_direct_tile(r,x,y,t,alternate=a)
            if before!=after:self.history.record(offset,before,after,r,a)
        self.history.commit()
        # Update cached preview tiles rather than rerendering the whole room.
        for r,cx,cy,t,a in changes:
            for (cached_room,cached_alt,scale), base in list(self._room_image_cache.items()):
                if cached_room==r and cached_alt==a:
                    tile=self._tile_image(r,a,t).resize((16*scale,16*scale),Image.Resampling.NEAREST)
                    base.paste(tile,(cx*16*scale,cy*16*scale))
        # The graphics sheets are keyed by room graphics, not map contents.
        # Update only changed 16px cells in each cached overworld atlas.
        for r,cx,cy,t,a in changes:
            for atlas,alternate_atlas in ((self.atlas_default,False),(self.atlas_alt,True)):
                if atlas is None: continue
                use_special=alternate_atlas and r in SPECIAL_MAP
                if r in SPECIAL_MAP and use_special!=a: continue
                atlas.paste(self._tile_image(r,use_special,t),
                            ((r%16)*160+cx*16,(r//16)*128+cy*16))
        if sx >= 0 or move:
            self.tile_selection=(room,target_alt,x0,y0,width,height,values)
        room_changed=self.room!=room
        self.room=room
        if room_changed:
            self.show_room()
        else:
            self._refresh_selection_only()
            self.refresh_title()


    def _clear_tile_move_preview(self):
        if hasattr(self,'map_canvas'):
            self.map_canvas.delete('tile-move-ghost')
        self._tile_move_ghost_ref=None


    def _preview_tile_move(self,cell,full):
        """Show a cheap, non-destructive moving tile stamp while dragging."""
        sel=self.tile_selection
        if not sel or sel[2]<0:return
        room,x,y=cell
        if room!=sel[0]:return
        _,sx,sy=self._tile_select_start
        _,alt,ox,oy,w,h,values=sel
        nx,ny=ox+x-sx,oy+y-sy
        z=self.zoom.get()
        if full:
            canvas=self.map_canvas
            canvas.delete('tile-move-ghost')
            # Reuse decoded 16x16 tile artwork, avoiding full overworld redraw.
            sheet=Image.new('RGB',(w*16,h*16))
            for j in range(h):
                for i in range(w):
                    sheet.paste(self._tile_image(room,alt,values[j*w+i]),(i*16,j*16))
            if z!=1:sheet=sheet.resize((w*16*z,h*16*z),Image.Resampling.NEAREST)
            self._tile_move_ghost_ref=ImageTk.PhotoImage(sheet)
            px=((room%16)*160+nx*16)*z-self.map_x
            py=((room//16)*128+ny*16)*z-self.map_y
            canvas.create_image(px,py,image=self._tile_move_ghost_ref,anchor='nw',tags='tile-move-ghost')
        else:
            key=(room,alt,z)
            base=self._room_image_cache.get(key)
            if base is None:return
            preview=base.copy()
            # Preview the cleared source and moved tiles without writing to ROM.
            blank=self._tile_image(room,alt,0).resize((16*z,16*z),Image.Resampling.NEAREST)
            for j in range(h):
                for i in range(w):
                    if 0<=ox+i<10 and 0<=oy+j<8:
                        preview.paste(blank,((ox+i)*16*z,(oy+j)*16*z))
            for j in range(h):
                for i in range(w):
                    if 0<=nx+i<10 and 0<=ny+j<8:
                        tile=self._tile_image(room,alt,values[j*w+i]).resize((16*z,16*z),Image.Resampling.NEAREST)
                        preview.paste(tile,((nx+i)*16*z,(ny+j)*16*z))
            preview=self.draw_sprite_positions_on_image(preview,room,z)
            self.image_ref=ImageTk.PhotoImage(preview)
            self.preview.configure(image=self.image_ref,text='')


    def _tile_left_release(self,event,full):
        if self._tile_select_start is None:return
        cell=self._selection_cell(event,full) or self._tile_select_target
        if self._tile_select_action=='move' and cell is not None and self.tile_selection:
            _,x,y=cell
            _,sx,sy=self._tile_select_start
            sel=self.tile_selection
            if (x,y)!=(sx,sy):self._write_tile_block(sel,sel[0],sel[2]+x-sx,sel[3]+y-sy,move=True)
        self._clear_tile_move_preview()
        self._tile_select_start=None
        self._tile_select_action=None
        self._tile_select_target=None
        self._refresh_selection_only()


    def _tile_right_press(self,event,full):
        cell=self._selection_cell(event,full)
        if cell is None:return 'break'
        room,x,y=cell
        self._tile_last_paint_cell=cell
        if self.tile_selection:
            self._write_tile_block(self.tile_selection,room,x,y)
        else:
            self.paint_at(room,x,y)
            self.end_stroke()
        return 'break'


    def _tile_right_drag(self,event,full):
        if not self.paint_mode.get():return
        cell=self._selection_cell(event,full)
        if cell is None or cell==getattr(self,'_tile_last_paint_cell',None):return 'break'
        self._tile_last_paint_cell=cell
        room,x,y=cell
        if self.tile_selection:self._write_tile_block(self.tile_selection,room,x,y)
        else:self.paint_at(room,x,y)
        return 'break'


    def _tile_right_release(self):
        self._tile_last_paint_cell=None
        self.end_stroke()


    def _draw_tile_selection(self,image,room,scale):
        sel=self.tile_selection
        if not self.paint_mode.get() or not sel or sel[0]!=room or sel[2]<0:return image
        _,alt,x,y,w,h,_=sel
        if alt!=(self.alternate.get() and room in SPECIAL_MAP):return image
        box=(x*16*scale,y*16*scale,(x+w)*16*scale,(y+h)*16*scale)
        image=image.copy()
        image.paste(ImageOps.invert(image.crop(box).convert('RGB')),box[:2])
        return image


    def _draw_full_tile_selection(self,canvas,z):
        sel=self.tile_selection
        if not self.paint_mode.get() or not sel or sel[2]<0:return
        room,alt,x,y,w,h,_=sel
        if alt!=(self.alternate.get() and room in SPECIAL_MAP):return
        left=((room%16)*160+x*16)*z-self.map_x
        top=((room//16)*128+y*16)*z-self.map_y
        if not self.room_in_overworld_area(room):return
        if left+w*16*z<=0 or top+h*16*z<=0 or left>=canvas.winfo_width() or top>=canvas.winfo_height():return
        crop=self.cached_room_render(room,special=alt,scale=1)[0].crop((x*16,y*16,(x+w)*16,(y+h)*16))
        crop=ImageOps.invert(crop.convert('RGB'))
        if z!=1:crop=crop.resize((w*16*z,h*16*z),Image.Resampling.NEAREST)
        self._full_selection_photo=ImageTk.PhotoImage(crop)
        canvas.create_image(left,top,image=self._full_selection_photo,anchor='nw',tags='tile-selection')


    def pick_tile_at(self, room, x, y):
        """Eyedropper: read the displayed overlay byte without modifying ROM."""
        if self.data is None or not (0 <= room < 256 and 0 <= x < 10 and 0 <= y < 8):
            return
        special = self.alternate.get() and room in SPECIAL_MAP
        from windfish.rom.windfish_shared_map16 import cells
        tiles = cells(self.data,room,special)
        self.selected_tile.set(tiles[y * 10 + x])
        if hasattr(self,'map16_page'):self.map16_page.set('01 — Shared tiles' if tiles[y*10+x]>=256 else '00 — Room tiles')
        # In full-map mode also select the room the sampled tile belongs to.
        self.room = room
        self.show_room()
        self.update_inspector()


    def pick_single_room_tile(self, event):
        if self.data is None or self.full_map.get():
            return
        z = self.zoom.get()
        self.pick_tile_at(self.room, event.x // (16*z), event.y // (16*z))


    def pick_full_map_tile(self, event):
        if self.data is None or not self.full_map.get():
            return
        z = self.zoom.get()
        px, py = self.map_x + event.x, self.map_y + event.y
        if not (0 <= px < 2560*z and 0 <= py < 2048*z):
            return
        col, row = px // (160*z), py // (128*z)
        x, y = (px // (16*z)) % 10, (py // (16*z)) % 8
        self.pick_tile_at(int(row*16+col), int(x), int(y))


    def _tile_image(self, room, special, tile):
        """Look up a rendered 16px tile; graphics do not change during overlay painting."""
        key = (room, special)
        sheet = self._tile_sheets.get(key)
        if sheet is None:
            _, sheet, _ = self.cached_room_render( room, special=special, scale=1)
            self._tile_sheets[key] = sheet
        return sheet.crop(((tile % 16)*16, (tile // 16)*16,
                           (tile % 16 + 1)*16, (tile // 16 + 1)*16))


    def apply_direct_collision_draw(self, cells, room):
        from windfish.overworld.windfish_direct_collisions import direct_collision_changes
        try:
            changes = direct_collision_changes(self.data,cells,self.collision_capacities)
        except ValueError as exc:
            messagebox.showerror('Room editing', f'Cannot draw with collisions: {exc}', parent=self)
            return False
        self.end_stroke()
        for at,before,after,r,alt in changes:
            self.data[at]=after
            self.history.record(at,before,after,r,alt)
        self.history.commit()
        self.room=room
        self.collision_selected=None
        self.collision_target=None
        if changes:self.refresh_changed_rooms(changes)
        else:self.show_room()
        return True


    def apply_shared_tile_draw(self,cells,room):
        from windfish.rom.windfish_shared_map16 import drawing_changes
        if self.direct_add_collisions.get():
            return self.apply_direct_collision_draw(cells,room)
        try:changes=drawing_changes(self.data,cells)
        except ValueError as exc:
            messagebox.showerror('Room editing', str(exc), parent=self);return False
        self.end_stroke()
        if not changes:
            if self.room!=room:self.room=room;self.show_room()
            else:self._refresh_selection_only()
            return True
        self.refresh_visual_cache()
        before=self._local_render_revision
        for at,old,new,r,alt in changes:
            self.data[at]=new;self.history.record(at,old,new,r,alt)
        self.history.commit()
        affected={(r,bool(a)) for at,old,new,r,a in changes}
        after=self._visual_revision()
        self._visual_cache.advance_map_revision(self.data,before,after,affected)
        self._local_render_revision=after
        # Placements do not alter graphics, palettes, definitions or properties.
        # Keep the tile sheets and drop only scaled images of affected rooms.
        for key in list(self._room_image_cache):
            if key[:2] in affected:del self._room_image_cache[key]
        changed_room=self.room!=room;self.room=room
        if changed_room:self.show_room()
        else:
            self._refresh_selection_only()
            self.refresh_title()
        return True


    def paint_at(self, room, x, y):
        if not self.paint_mode.get() or self.document is None:
            return
        special = self.alternate.get() and room in SPECIAL_MAP
        from windfish.rom import windfish_shared_map16 as shared
        if shared.enabled(self.data):
            self.apply_shared_tile_draw([(room,x,y,self.selected_tile.get(),special)],room)
            return
        if self.direct_add_collisions.get():
            self.apply_direct_collision_draw([(room,x,y,self.selected_tile.get(),special)],room)
            return
        offset, before, after = self.document.set_direct_tile(room, x, y, self.selected_tile.get(), alternate=special)
        if before == after:
            return
        self.history.record(offset, before, after, room, special)
        # Patch only the 16x16 pixel tile in cached atlases; avoid re-rendering
        # an entire room (and re-building the 256-tile sheet) on each mouse move.
        for atlas, alt in ((self.atlas_default, False), (self.atlas_alt, True)):
            if atlas is not None:
                use_special = alt and room in SPECIAL_MAP
                if special == use_special or room not in SPECIAL_MAP:
                    atlas.paste(self._tile_image(room, use_special, after),
                                ((room % 16)*160 + x*16, (room // 16)*128 + y*16))
        self._room_image_cache.clear()
        room_changed = self.room != room
        self.room = room
        if self.full_map.get():
            self.draw_full_map()
            self.refresh_title()
            if room_changed:
                self.refresh_selected_room_context()
        else:
            # The small single-room preview is inexpensive to refresh.
            self.show_room()


    def click_full_map(self, event):
        if getattr(self,'warp_mode',None) is not None and self.warp_mode.get():
            return self.place_warp(event,True)
        if self.collision_mode.get():
            return self.collision_left_press(event, True)
        if self.sprite_mode.get():
            return self._sprite_left_press(event, True)
        elif self.paint_mode.get():
            return self._tile_left_press(event,True)
        else:
            self.select_full_map_room(event)


    def click_single_room(self, event):
        if getattr(self,'warp_mode',None) is not None and self.warp_mode.get():
            return self.place_warp(event,False)
        if self.collision_mode.get():
            return self.collision_left_press(event, False)
        if self.sprite_mode.get():
            return self._sprite_left_press(event, False)
        elif self.paint_mode.get():
            return self._tile_left_press(event,False)


