"""Additional dungeon Room Properties tabs and immediate-edit controls."""
from tkinter import messagebox
from PIL import ImageTk,Image
import windfish.dungeon.windfish_dungeon_room_data as data_ops
import windfish.rendering.windfish_dungeon_render as dungeon
from windfish.overworld.windfish_chests import CHEST_ITEMS,chest_item_label
from windfish.rendering.windfish_sprite_names import sprite_name


class RoomControlsMixin:
    def reset_extra(self):
        self.reset_events()
        self._extra_loading=True;self._warp_rows={};self._warp_key=None;self._sprite_rows={};self._sprite_expected=None
        self.chest_value.set('');self.chest_combo.configure(state='disabled')
        for widget in self.place_inputs+self.warp_inputs:widget.configure(state='disabled')
        for var in [*self.place_fields.values(),*self.warp_vars.values()]:var.set('')
        if hasattr(self,'warp_summary'):self.warp_summary.set('')
        if hasattr(self,'sprite_preview_label'):
            self.sprite_preview_label.configure(image='');self.sprite_preview_status.set('Select a sprite to preview its graphics.')
        self.warp_feedback.set('');self.sprite_feedback.set('');self.palette_canvas.delete('all');self.sprite_sheet.configure(image='');self.sprite_graphics_info.set('')
        for item in self.sprites_table.get_children():self.sprites_table.delete(item)

    def refresh_extra(self,context,record,warps):
        owner=self.owner
        self.refresh_events(context)
        value=owner.data[data_ops.chest_offset(owner.data,context,owner.room)]
        self.chest_combo.configure(state='readonly',values=[chest_item_label(v) for v in sorted(set(CHEST_ITEMS)|{value})]);self.chest_value.set(chest_item_label(value))
        self._warp_rows=dict(zip(self.warps.get_children(),warps))
        try:
            self._sprite_expected=data_ops.sprites(owner.data,context,owner.room)
            for i,(xy,tile) in enumerate(self._sprite_expected):
                item=self.sprites_table.insert('','end',values=(f'{i:02X}',f'{tile:02X}',sprite_name(tile),f'{xy&15:X}',f'{xy>>4:X}'));self._sprite_rows[item]=i
            self.sprite_feedback.set(f'Room {owner.room:02X}: {len(self._sprite_expected)} sprite placements. Select a sprite to preview; use the map to place or edit sprites.')
        except (ValueError,IndexError) as exc:self.sprite_feedback.set(str(exc))
        try:
            self.paint_palettes()
            image,group,selectors,sources=data_ops.sprite_graphics(owner.data,context,owner.room)
            self.sprite_sheet_photo=ImageTk.PhotoImage(image.resize((256,64),Image.Resampling.NEAREST));self.sprite_sheet.configure(image=self.sprite_sheet_photo)
            self.sprite_graphics_info.set(('Color room slots' if group is None else f'Configuration {group:02X}')+'\n'+'\n'.join(f'Slot {i}: '+(f'{selectors[i][0]:02X}/{selectors[i][1]:02X}' if isinstance(selectors[i],tuple) else f'{selectors[i]:02X}')+' | '+('Empty / inherited' if at is None else f'ROM {at:06X}') for i,at in enumerate(sources)))
        except (ValueError,IndexError) as exc:self.sprite_graphics_info.set(str(exc))
        self._extra_loading=False
        self.paint_sprite_preview()

    def change_chest(self,event=None):
        if self._extra_loading or self._target is None:return
        try:self.owner.apply_room_changes(data_ops.chest_changes(self.owner.data,*self._target,int(self.chest_value.get().split(' — ')[0],16)))
        except (ValueError,IndexError) as exc:self.feedback.set(str(exc))

    def load_placement_fields(self,row):
        self._extra_loading=True
        raw=bytes.fromhex(row[-1]) if row else None
        values=(str(int(row[3],16)),str(int(row[4],16)),row[6],row[5]) if row else ('','','','')
        for var,value in zip(self.place_fields.values(),values):var.set(value)
        for widget in self.place_inputs:widget.configure(state='normal' if row else 'disabled')
        self.place_inputs[-1].configure(state='readonly' if row else 'disabled')
        if row and int(row[2],16)>=0xEC:
            self.place_inputs[2].configure(state='disabled');self.place_inputs[3].configure(state='disabled')
        self._extra_loading=False

    def clear_objects(self):
        if self._target is None:return
        if not messagebox.askyesno('Clear collision objects',f'Clear all collision objects in room {self.owner.room:02X}?\n\nUses pass-through floor 00 and removes the wall template. CGB artwork, warps and sprites are preserved. Required dungeon patches are installed if needed.\n\nThis cannot be undone; Undo/Redo history will be cleared. Save As a separate ROM first. Proceed with caution.',icon='warning',default='no',parent=self):return
        try:
            self.owner.apply_room_changes(data_ops.clear_changes(self.owner.data,*self._target))
            self.owner.owner.history.clear();self.owner.selected_collision=None
            self.owner.owner.update_edit_menu();self.owner.draw()
        except (ValueError,IndexError) as exc:self.object_feedback.set(str(exc))

    def clear_room(self):
        if self._target is None:return
        if not messagebox.askyesno('Clear Room',f'Reset room {self.owner.room:02X} to blank floor 00 and wall template 00?\n\nRemoves objects, warps, sprites, Direct Draw overrides and the room event; resets chest contents. BG/sprite graphics assignments, palettes and dungeon map assignments are preserved.\n\nThis can be undone.',parent=self,icon='warning',default='no'):return
        try:
            self.owner.apply_room_changes(data_ops.clear_room_changes(self.owner.data,*self._target))
            self.owner.selected_collision=None;self.owner.selected_sprite=None;self.owner.draw()
        except (ValueError,IndexError) as exc:self.object_feedback.set(str(exc))

    def select_warp(self,event=None):
        selected=self.warps.selection();row=self._warp_rows.get(selected[0]) if selected else None
        self._warp_key=row;self._extra_loading=True
        raw=bytes.fromhex(row[-1]) if row else None
        for var,value in zip(self.warp_vars.values(),(raw[0]&3,*raw[1:]) if raw else ('',)*5):var.set(f'{value:02X}' if isinstance(value,int) else '')
        for i,widget in enumerate(self.warp_inputs):widget.configure(state=('readonly' if i==0 else 'normal') if row else 'disabled')
        self._extra_loading=False

    def edit_warp(self,event=None):
        if self._extra_loading or self._warp_key is None:return
        self.change_warp(int(self._warp_key[0],16))
    def add_warp(self):self.change_warp(None)
    def remove_warp(self):
        if self._warp_key is not None:self.change_warp(int(self._warp_key[0],16),True)
    def change_warp(self,index,remove=False):
        if self._target is None:return
        try:
            values=tuple(int(var.get(),16) for var in self.warp_vars.values()) if index is not None and not remove else None
            changes=data_ops.warp_changes(self.owner.data,*self._target,index,values,remove,expected=self._object_expected)
            self.owner.apply_room_changes(changes)
            items=self.warps.get_children()
            if items:
                target=items[-1] if index is None else items[min(index,len(items)-1)];self.warps.selection_set(target);self.select_warp()
        except (ValueError,IndexError) as exc:self.warp_feedback.set(str(exc))

    def paint_palettes(self):
        if self.owner.data is None:return
        from windfish.app.windfish_property_palettes import draw_palette_view
        try:
            m,side=self.owner.render_context(self.owner.room);data=self.owner.data
            at=dungeon.palette_offset(data,m,side,self.owner.room)
            offsets=tuple(range(0x85518,0x85548,2))+tuple(range(at+64,at+80,2))
            draw_palette_view(self.palette_canvas,data,at,offsets,
                f'BG palettes  •  Map context {m:02X}  •  ROM 0x{at:05X}',
                'OBJ palettes  •  Shared 0–5 + room 6–7')
        except (ValueError,IndexError) as exc:
            self.palette_canvas.delete('all');self.palette_canvas.create_text(8,8,anchor='nw',text=str(exc))

    def paint_sprite_preview(self):
        if not hasattr(self,'sprite_preview_label'):return
        owner=self.owner;self.sprite_preview_label.configure(image='');self.sprite_preview_photo=None
        selected=getattr(owner,'selected_sprite',None)
        if owner.data is None or selected is None or selected[1]!=owner.room:
            self.sprite_preview_status.set('Select a sprite to preview its graphics.');return
        m,room,index,expected=selected
        context,side=owner.render_context(room)
        if m!=context:return
        try:
            entries=data_ops.sprites(owner.data,m,room)
            if not 0<=index<len(entries):return
            from windfish.dungeon.windfish_dungeon_sprites import render_result
            xy,sid=entries[index];result=render_result(owner.data,m,room,sid,sideview=side)
            if result.image is not None:
                image=result.image;self.sprite_preview_photo=ImageTk.PhotoImage(image.resize((image.width*4,image.height*4),Image.Resampling.NEAREST));self.sprite_preview_label.configure(image=self.sprite_preview_photo)
            self.sprite_preview_status.set(f'ID {sid:02X} — {sprite_name(sid)}'+(' · '+result.message if result.message else ''))
            items=self.sprites_table.get_children()
            if index<len(items):self.sprites_table.selection_set(items[index]);self.sprites_table.see(items[index])
        except (ValueError,IndexError) as exc:self.sprite_preview_status.set(str(exc))

    def select_sprite(self,event=None):
        selected=self.sprites_table.selection();index=self._sprite_rows.get(selected[0]) if selected else None
        if index is None or self._sprite_expected is None or self._target is None:return
        xy,sid=self._sprite_expected[index];m,room=self._target
        self.owner.selected_sprite=(m,room,index,self._sprite_expected)
        self.owner.sprite_id.set(sid);self.owner.sprite_brush=sid;self.owner.show_sprite_ids.set(True)
        self.paint_sprite_preview();self.owner.draw()

