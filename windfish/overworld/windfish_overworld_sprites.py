"""Overworld sprite selection, placement, previews and map overlays."""
from tkinter import messagebox
from windfish.rom.windfish_sprite_limits import SpriteLimitError, LIMIT_TITLE
from PIL import Image, ImageTk, ImageDraw, ImageFont
from windfish.rendering.windfish_overworld_render import SPECIAL_MAP
from windfish.overworld.windfish_sprites import read_room_sprites
from windfish.rendering.windfish_sprite_names import sprite_name
from windfish.rendering.windfish_sprite_graphics import render_sheet
from windfish.rendering.windfish_sprite_render import render_sprite, sprite_draw_offset
from windfish.rendering.windfish_sprite_definitions import sprite_placement_frame

class OverworldSpriteMixin:
    def _sprite_cell(self, event, full):
        if self.data is None: return None
        z = self.zoom.get()
        px = (self.map_x + event.x) // z if full else event.x // z
        py = (self.map_y + event.y) // z if full else event.y // z
        if full:
            if not (0 <= px < 2560 and 0 <= py < 2048): return None
            room = (py // 128) * 16 + px // 160
            if not self.room_in_overworld_area(room):return None
            x, y = (px % 160)//16, (py % 128)//16
        else:
            room = self.room
            x, y = px//16, py//16
        return (room, x, y) if 0 <= x < 10 and 0 <= y < 8 else None

    def _commit_sprite_bytes(self, changes, room):
        if not changes: return
        self.end_stroke()
        for offset, before, after in changes:
            self.history.record(offset, before, after, room, False)
        self.history.commit()
        self.room = room
        self.show_room()

    def delete_selected_sprite(self, event=None):
        if self.collision_mode.get() and self.data is not None:
            focused=self.focus_get()
            if focused is not None and focused.winfo_class() in ('Entry','TEntry','Text','TCombobox','Spinbox','TSpinbox'):
                return
            if focused is None or focused.winfo_toplevel() is self:
                self.delete_collision_selection()
                return 'break'
            return
        if not self.sprite_mode.get() or self.data is None or self.selected_sprite is None:
            return
        if self.focus_get() is not None and self.focus_get().winfo_toplevel() is not self:
            return
        room, index = self.selected_sprite
        try:
            from windfish.overworld.windfish_sprite_edit import replace_room_sprites
            sprites = read_room_sprites(self.data, room)['sprites']
            if not 0 <= index < len(sprites):
                return 'break'
            records = [(sp.x,sp.y,sp.id) for i,sp in enumerate(sprites) if i != index]
            changes = replace_room_sprites(self.data,room,records,self.sprite_capacities,self.sprite_shared_streams)
        except ValueError as exc:
            messagebox.showwarning('Cannot delete sprite', str(exc), parent=self)
            return 'break'
        self.selected_sprite = None
        self._commit_sprite_bytes(changes,room)
        return 'break'

    def add_sprite_to_slot(self, room, x, y):
        if not self.extended_sprites_enabled:
            messagebox.showinfo('Extended sprites required',
                'Reopen the ROM and accept the expanded editing capabilities upgrade to add sprites.', parent=self)
            return
        if self.sprite_brush is not None and self.sprite_brush >= 0xFB:
            messagebox.showwarning('Unsupported sprite ID',
                'FB–FE are unsupported custom sprite IDs; FF is reserved. Choose 00–FA.', parent=self)
            return
        if self.sprite_brush is None:
            messagebox.showinfo('Select a sprite', 'Choose a sprite in Editors → Add Sprites Window first.', parent=self)
            return
        try:
            from windfish.overworld.windfish_sprite_edit import replace_room_sprites
            sprites = read_room_sprites(self.data,room)['sprites']
            records = [(sp.x,sp.y,sp.id) for sp in sprites]
            records.append((x,y,self.sprite_brush))
            changes = replace_room_sprites(self.data,room,records,self.sprite_capacities,self.sprite_shared_streams)
        except SpriteLimitError as exc:
            messagebox.showwarning(LIMIT_TITLE, str(exc), parent=self)
            return
        except ValueError as exc:
            messagebox.showwarning('Cannot add sprite',str(exc),parent=self)
            return
        self.selected_sprite = (room,len(records)-1)
        self._commit_sprite_bytes(changes,room)

    def _select_sprite_brush(self, sprite_id):
        """Use a placed sprite as the current placement brush and catalog selection."""
        if not 0 <= sprite_id < 0xFF:
            return
        self.sprite_brush = sprite_id
        if self._sprite_catalog_select is not None:
            self._sprite_catalog_select(sprite_id)

    def _sprite_left_press(self, event, full):
        """Select a placed sprite, or clear selection when clicking empty ground."""
        self._sprite_drag = None
        self._sprite_drag_changed = False
        self._sprite_pending_cell = None
        self._sprite_drag_background = None
        cell = self._sprite_cell(event, full)
        if cell is None:
            self.selected_sprite = None
            self.show_room()
            return
        room, x, y = cell
        sprites = read_room_sprites(self.data, room)['sprites']
        hits = [i for i, sp in enumerate(sprites) if (sp.x, sp.y) == (x, y)]
        if hits:
            index = hits[-1]
            self._sprite_drag = (room, index)
            self.selected_sprite = (room, index)
            self._select_sprite_brush(sprites[index].id)
            record = sprites[index]
            frame = sprite_placement_frame(record.id, record.x, record.y)
            self._sprite_drag_image = (self.sprite_image(room, record.id) if frame is None
                                       else self.sprite_image(room, record.id, frame=frame))
            self.room = room
        else:
            self.selected_sprite = None
            if full:
                self.room = room
        if getattr(event,'state',0)&4:
            self._sprite_drag=None
            if hasattr(event.widget,'focus_set'):event.widget.focus_set()
            self.delete_selected_sprite();return 'break'
        self.show_room()
        if self._sprite_drag is not None and not full:
            z=self.zoom.get()
            alt=self.alternate.get() and room in SPECIAL_MAP
            base=self._room_image_cache.get((room,alt,z))
            if base is not None:
                self._sprite_drag_background=self.draw_sprite_positions_on_image(base,room,z,skip_index=index)

    def sprite_double_click_single(self, event):
        return self._sprite_double_click(event, False)

    def sprite_double_click_full(self, event):
        return self._sprite_double_click(event, True)

    def _sprite_double_click(self, event, full):
        if getattr(event,'state',0)&4:return 'break'
        """Edit only the ID byte of an existing placed sprite in a modal dialog."""
        if not self.sprite_mode.get() or self.data is None:
            return
        cell = self._sprite_cell(event, full)
        if cell is None:
            return 'break'
        room, x, y = cell
        sprites = read_room_sprites(self.data, room)['sprites']
        hits = [i for i, sp in enumerate(sprites) if (sp.x, sp.y) == (x, y)]
        if not hits:
            return 'break'
        index = hits[-1]
        self._sprite_drag = None
        self._sprite_drag_changed = False
        self.room = room
        self.selected_sprite = (room, index)
        self.show_room()
        self.open_sprite_id_dialog(room, index)
        return 'break'

    def open_sprite_id_dialog(self, room, index):
        sprites = read_room_sprites(self.data, room)['sprites']
        if not (0 <= index < len(sprites)):
            return
        spr = sprites[index]
        from windfish.app.windfish_sprite_display import build_sprite_id_dialog,bind_sprite_id_dialog
        choices=[f'{i:02X} — {sprite_name(i)}' for i in range(256)]
        dialog,choice,combo,buttons=build_sprite_id_dialog(self,room,spr.x,spr.y,choices,choices[spr.id],
            'Warning: Changing a sprite ID may cause unexpected\nbehavior in-game. Some sprites require specific rooms\nor game conditions.')

        def accept():
            new_id = int(choice.get()[:2], 16)
            if new_id == 0xFF:
                messagebox.showwarning('Reserved ID', 'FF is SPRITE_NONE and cannot be placed.', parent=dialog)
                return
            if new_id >= 0xFB:
                messagebox.showwarning('Unsupported sprite ID',
                    'FB–FE are unsupported custom sprite IDs; FF is reserved.', parent=dialog)
                return
            if new_id != spr.id:
                try:
                    from windfish.overworld.windfish_sprite_edit import replace_room_sprites
                    sprites_now = read_room_sprites(self.data, room)['sprites']
                    records = [(sp.x, sp.y, new_id if i == index else sp.id)
                               for i, sp in enumerate(sprites_now)]
                    changes = replace_room_sprites(self.data, room, records,
                                                    self.sprite_capacities, self.sprite_shared_streams)
                except ValueError as exc:
                    messagebox.showwarning('Cannot change sprite', str(exc), parent=dialog)
                    return
                self._commit_sprite_bytes(changes, room)
            self._select_sprite_brush(new_id)
            dialog.destroy()
            self.show_room()

        bind_sprite_id_dialog(dialog,combo,buttons,accept)
        self.wait_window(dialog)

    def sprite_left_drag_single(self, event):
        if self.collision_mode.get():return self.collision_drag_motion(event,False)
        if self.sprite_mode.get():
            self._sprite_right_drag(event, False)
        elif self.paint_mode.get():
            return self._tile_left_motion(event,False)

    def sprite_left_drag_full(self, event):
        if self.collision_mode.get():return self.collision_drag_motion(event,True)
        if self.sprite_mode.get():
            self._sprite_right_drag(event, True)
        elif self.paint_mode.get():
            return self._tile_left_motion(event,True)

    def sprite_left_release_single(self, event):
        if self.collision_mode.get():return self.collision_drag_release(event,False)
        if self.sprite_mode.get():
            self._sprite_right_release()
        elif self.paint_mode.get():
            return self._tile_left_release(event,False)
        else:
            self.end_stroke()

    def sprite_left_release_full(self, event):
        if self.collision_mode.get():return self.collision_drag_release(event,True)
        if self.sprite_mode.get():
            self._sprite_right_release()
        elif self.paint_mode.get():
            return self._tile_left_release(event,True)
        else:
            self.end_stroke()

    @staticmethod
    def _highlight_sprite(sprite):
        """Invert RGB colors of a selected sprite while retaining its alpha mask."""
        from windfish.app.windfish_sprite_display import highlight_sprite
        return highlight_sprite(sprite)

    def _sprite_right_press(self, event, full):
        if self.collision_mode.get():
            self._collision_delete_stroke=bool(getattr(event,'state',0)&4)
            if self._collision_delete_stroke:
                self.collision_click(event,full)
                self.delete_collision_selection()
                return 'break'
            self._collision_paint_seen=set()
            return self.collision_paint_drag(event,full)
        # Placement is right-click only, and only with the expansion enabled.
        if self.sprite_mode.get():
            if self.data is None or not self.extended_sprites_enabled:
                return 'break'
            cell = self._sprite_cell(event, full)
            if cell is not None:
                room, x, y = cell
                if self.sprite_brush is not None:
                    self.add_sprite_to_slot(room, x, y)
                else:
                    messagebox.showinfo('Select a sprite',
                        'Select a sprite on the map or in Editors → Add Sprites Window first.', parent=self)
            return 'break'
        if self.paint_mode.get():return self._tile_right_press(event,full)
        return self.pick_full_map_tile(event) if full else self.pick_single_room_tile(event)

    def _sprite_right_drag(self, event, full):
        """Move only the selected sprite's sprite on screen; write ROM on release."""
        if not self.sprite_mode.get() or self._sprite_drag is None:return
        cell=self._sprite_cell(event,full)
        if cell is None:return
        room,x,y=cell
        source_room,index=self._sprite_drag
        if room!=source_room:return
        if getattr(self,'_sprite_pending_cell',None)==cell:return
        self._sprite_pending_cell=cell
        if full:self.map_canvas.itemconfigure(f'sprite-{room}-{index}',state='hidden')
        z=self.zoom.get()
        sprite=getattr(self,'_sprite_drag_image',None)
        if sprite is None:return
        sprite_id = read_room_sprites(self.data, source_room)['sprites'][index].id
        frame = sprite_placement_frame(sprite_id, x, y)
        if frame is not None:
            sprite = self.sprite_image(room, sprite_id, frame=frame)
            if sprite is None:return
        sprite=self._highlight_sprite(sprite).resize((sprite.width*z,sprite.height*z),Image.Resampling.NEAREST)
        dx, dy = sprite_draw_offset(sprite_id, room=room)
        if full:
            canvas=self.map_canvas
            canvas.delete('sprite-drag-preview')
            px=((room%16)*160+x*16)*z-self.map_x
            py=((room//16)*128+y*16)*z-self.map_y
            self._sprite_drag_photo=ImageTk.PhotoImage(sprite)
            canvas.create_image(px+dx*z,py+dy*z,image=self._sprite_drag_photo,anchor='nw',tags='sprite-drag-preview')
            canvas.tag_raise('sprite-drag-preview')
        else:
            base=getattr(self,'_sprite_drag_background',None)
            if base is None:return
            preview=base.convert('RGBA')
            preview.alpha_composite(sprite.convert('RGBA'),(x*16*z+dx*z,y*16*z+dy*z))
            self._sprite_preview_photo=ImageTk.PhotoImage(preview)
            self.preview.configure(image=self._sprite_preview_photo)

    def sprite_right_press_single(self, event): self._sprite_right_press(event, False)

    def sprite_right_press_full(self, event): self._sprite_right_press(event, True)

    def sprite_right_drag_single(self, event):
        if self.collision_mode.get():return self.collision_paint_drag(event,False)
        if self.paint_mode.get():return self._tile_right_drag(event,False)
        if self.sprite_mode.get():return self._sprite_right_drag(event, False)

    def sprite_right_drag_full(self, event):
        if self.collision_mode.get():return self.collision_paint_drag(event,True)
        if self.paint_mode.get():return self._tile_right_drag(event,True)
        if self.sprite_mode.get():return self._sprite_right_drag(event, True)

    def _sprite_right_release(self):
        pending=getattr(self,'_sprite_pending_cell',None)
        self._sprite_pending_cell=None
        self.map_canvas.delete('sprite-drag-preview')
        self._sprite_drag_background=None
        self._sprite_drag_photo=None
        drag=self._sprite_drag
        self._sprite_drag=None
        self._sprite_drag_changed=False
        if drag is None or pending is None:return
        room,index=drag
        dest_room,x,y=pending
        if dest_room!=room:return
        from windfish.overworld.windfish_sprite_edit import replace_room_sprites
        sprites=read_room_sprites(self.data,room)['sprites']
        if not 0<=index<len(sprites):return
        if (sprites[index].x,sprites[index].y)==(x,y):
            self.show_room()
            return
        records=[(x,y,sp.id) if i==index else (sp.x,sp.y,sp.id)
                 for i,sp in enumerate(sprites)]
        try:
            changes=replace_room_sprites(self.data,room,records,
                                         self.sprite_capacities,self.sprite_shared_streams)
        except ValueError as exc:
            messagebox.showwarning('Cannot move sprite',str(exc),parent=self)
            self.show_room()
            return
        if changes:
            for offset,before,after in changes:
                self.history.record(offset,before,after,room,False)
            self.history.commit()
        self.room=room
        self.show_room()

    def sprite_right_release_single(self, event):
        if self.paint_mode.get():return self._tile_right_release()
        self._sprite_right_release()

    def sprite_right_release_full(self, event):
        if self.paint_mode.get():return self._tile_right_release()
        self._sprite_right_release()

    def refresh_sprite_list(self):
        if not hasattr(self, 'sprite_list') or self.data is None:
            return
        self.sprite_list.delete(0, 'end')
        try:
            info = read_room_sprites(self.data, self.room)
            for i, sprite in enumerate(info['sprites']):
                self.sprite_list.insert('end', f'{i:02X}  ({sprite.x},{sprite.y})  ID {sprite.id:02X} — {sprite_name(sprite.id)}  @ {sprite.offset:05X}')
            self.sprite_detail.set(f'Room {self.room:02X}: {len(info["sprites"])} sprite placements\n'
                                   f'Stream: 0x{info["start"]:05X} — 0x{info["end"]:05X}\n'
                                   'Read-only; alternate overlays share the same sprite room index.')
            sheet, bank, selectors, offsets = render_sheet(self.data, self.room, scale=2)
            self.sprite_sheet_image = ImageTk.PhotoImage(sheet)
            self.sprite_sheet_label.configure(image=self.sprite_sheet_image)
            self.sprite_bank_detail.set(f'Room {self.room:02X}  |  Configuration {bank:02X}\n' + '\n'.join(f'Slot {i}: {v:02X}  |  ' + (f'ROM 0x{off:05X}' if off is not None else 'Empty') for i, (v, off) in enumerate(zip(selectors, offsets))))
            if self.selected_sprite and self.selected_sprite[0] == self.room and self.selected_sprite[1] < len(info['sprites']):
                self.sprite_list.selection_set(self.selected_sprite[1])
                self.sprite_list.see(self.selected_sprite[1])
            self.update_sprite_preview()
        except ValueError as exc:
            self.sprite_detail.set(f'Sprite decode error: {exc}')
            self.sprite_preview_status.set(f'Preview unavailable: {exc}')

    def select_sprite_from_list(self, event=None):
        if not self.sprite_list.curselection() or self.data is None: return
        self.selected_sprite = (self.room, self.sprite_list.curselection()[0])
        sprites = read_room_sprites(self.data, self.room)['sprites']
        if self.selected_sprite[1] < len(sprites):
            self._select_sprite_brush(sprites[self.selected_sprite[1]].id)
        self.show_sprite_ids.set(True)
        self.update_sprite_preview()
        self.show_room()

    def update_sprite_preview(self):
        """Read-only static preview; independent of the Show Sprites toggle."""
        if not hasattr(self, 'sprite_preview_label'): return
        self.sprite_preview_label.configure(image='')
        self.sprite_preview_photo = None
        if self.data is None or not self.selected_sprite or self.selected_sprite[0] != self.room:
            self.sprite_preview_status.set('Select a sprite to preview its graphics.')
            return
        index = self.selected_sprite[1]
        sprites = read_room_sprites(self.data, self.room)['sprites']
        if not 0 <= index < len(sprites):
            self.sprite_preview_status.set('No sprite selected.')
            return
        spr = sprites[index]
        try:
            preview = render_sprite(self.data, self.room, spr.id, frame=sprite_placement_frame(spr.id, spr.x, spr.y))
        except (ValueError, IndexError) as exc:
            self.sprite_preview_status.set(f'Preview error: {exc}')
            return
        if preview is None:
            self.sprite_preview_status.set(f'{sprite_name(spr.id)} (ID {spr.id:02X}): verified static image not available yet.')
            return
        scale = max(1, min(96 // preview.width, 96 // preview.height))
        preview = preview.convert('RGBA').resize((preview.width * scale, preview.height * scale),
                                                  Image.Resampling.NEAREST)
        self.sprite_preview_photo = ImageTk.PhotoImage(preview)
        self.sprite_preview_label.configure(image=self.sprite_preview_photo)
        self.sprite_preview_status.set(f'{sprite_name(spr.id)}  |  ID {spr.id:02X}  |  Room {self.room:02X}  |  ({spr.x}, {spr.y})\nROM graphics (placeholder where needed); {scale}× preview.')

    def sprite_image(self, room, sprite_id, frame=None):
        if not self.show_sprites.get() or self.data is None: return None
        try:
            return render_sprite(self.data, room, sprite_id, frame=frame)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _sprite_id_font(zoom):
        """Use the same scalable hex label sizing in both map views."""
        size = max(8, 8 * zoom)
        for face in ('DejaVuSansMono-Bold.ttf', 'DejaVuSans-Bold.ttf', 'arialbd.ttf'):
            try:
                return ImageFont.truetype(face, size)
            except OSError:
                pass
        return ImageFont.load_default()

    def draw_sprite_positions_on_image(self, image, room, zoom, skip_index=None):
        if not (self.show_sprite_ids.get() or self.show_sprites.get()):
            return image
        image = image.copy().convert('RGBA')
        for i, spr in enumerate(read_room_sprites(self.data, room)['sprites']):
            if i == skip_index: continue
            if not (0 <= spr.x < 10 and 0 <= spr.y < 8):
                continue
            x, y = spr.x * 16 * zoom, spr.y * 16 * zoom
            frame = sprite_placement_frame(spr.id, spr.x, spr.y)
            sprite = (self.sprite_image(room, spr.id) if frame is None
                      else self.sprite_image(room, spr.id, frame=frame))
            if sprite is not None:
                if self.sprite_mode.get() and self.selected_sprite == (room, i):
                    sprite = self._highlight_sprite(sprite)
                sprite = sprite.resize((sprite.width*zoom, sprite.height*zoom), Image.Resampling.NEAREST)
                dx, dy = sprite_draw_offset(spr.id, room=room)
                image.alpha_composite(sprite, (x + dx*zoom, y + dy*zoom))
            if not self.show_sprite_ids.get(): continue
            draw = ImageDraw.Draw(image)
            draw.rectangle((x, y, x+16*zoom-1, y+16*zoom-1), fill='#000000', outline='#ffffff', width=max(1,zoom))
            label = f'{spr.id:02X}'
            font = self._sprite_id_font(zoom)
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            draw.text((x+(16*zoom-tw)/2-bbox[0], y+(16*zoom-th)/2-bbox[1]), label, fill='#ffffff', font=font)
            if self.sprite_mode.get() and self.selected_sprite == (room, i):
                draw.rectangle((x, y, x+16*zoom-1, y+16*zoom-1), outline='#ffff33', width=max(1,zoom))
        return image.convert('RGB')

    def draw_sprite_positions_on_canvas(self, *, revision=None):
        self._sprite_photo_refs = []
        if not (self.show_sprite_ids.get() or self.show_sprites.get()) or self.data is None:
            return
        from windfish.app.windfish_sprite_display import SpriteDisplayCache
        if getattr(self,'_sprite_display_cache',None) is None:
            self._sprite_display_cache=SpriteDisplayCache()
        cache=self._sprite_display_cache
        z = self.zoom.get()
        # Draw all visible overworld rooms, not just the selected room.
        w, h = self.map_canvas.winfo_width(), self.map_canvas.winfo_height()
        left = max(0, self.map_x // (160*z))
        right = min(15, (self.map_x + w) // (160*z))
        top = max(0, self.map_y // (128*z))
        bottom = min(15, (self.map_y + h) // (128*z))
        for ry in range(top, bottom+1):
            for rx in range(left, right+1):
                room = ry*16 + rx
                if not self.room_in_overworld_area(room):continue
                ox, oy = rx*160*z-self.map_x, ry*128*z-self.map_y
                for i, spr in enumerate(read_room_sprites(self.data, room)['sprites']):
                    if not (0 <= spr.x < 10 and 0 <= spr.y < 8):
                        continue
                    x, y = ox+spr.x*16*z, oy+spr.y*16*z
                    frame = sprite_placement_frame(spr.id, spr.x, spr.y)
                    selected=(self.sprite_mode.get() and self.selected_sprite==(room,i))
                    key=(room,spr.id,frame,z,selected,bool(self.show_sprites.get()))
                    def create_photo():
                        sprite=(self.sprite_image(room,spr.id) if frame is None
                                else self.sprite_image(room,spr.id,frame=frame))
                        if sprite is None:return None
                        if selected:sprite=self._highlight_sprite(sprite)
                        return ImageTk.PhotoImage(sprite.resize(
                            (sprite.width*z,sprite.height*z),Image.Resampling.NEAREST))
                    photo=cache.get(self.data,revision,key,create_photo)
                    if photo is not None:
                        self._sprite_photo_refs.append(photo)
                        dx,dy=sprite_draw_offset(spr.id,room=room)
                        self.map_canvas.create_image(x+dx*z,y+dy*z,image=photo,anchor='nw',
                            tags=('sprite-marker',f'sprite-{room}-{i}'))
                    if not self.show_sprite_ids.get(): continue
                    from windfish.app.windfish_sprite_display import draw_sprite_hex
                    draw_sprite_hex(self.map_canvas,x,y,spr.id,z,
                        self.sprite_mode.get() and self.selected_sprite==(room,i),
                        tags=('sprite-marker',f'sprite-{room}-{i}'))

