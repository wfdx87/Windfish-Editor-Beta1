"""ROM document lifecycle, save prompts and shared undo/redo dispatch.

Methods keep the Viewer interface and call the existing guarded backends.
The application composes this mixin; it must not import Viewer.
"""
from tkinter import filedialog, messagebox
from windfish.rendering.windfish_overworld_render import render
from windfish.rom.windfish_palette_patch import is_installed
from windfish.rom.windfish_sprite_storage import validate_mode, enabled as extended_enabled
from windfish.overworld.windfish_collision_objects import snapshot_capacities


class AppDocumentMixin:
    def confirm_discard_changes(self):
        """True if it is safe to replace/close the current document.

        Yes saves to the active file; No discards; Cancel leaves everything
        untouched. Failed saves also abort the requested operation.
        """
        self.end_stroke()
        if self.document is None or not self.document.dirty:
            return True
        answer = messagebox.askyesnocancel(
            'Unsaved ROM changes',
            f'Would you like to save changes to\n{self.document.path.name}\n'
            'before continuing?\n\nYes: Save ROM   No: Discard changes   Cancel: Stay here',
            parent=self)
        if answer is None:
            return False
        if answer is False:
            return True
        try:
            self.document.data[0x1D2BFC] = self.room
            self.document.save()
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc), parent=self)
            return False
        self.refresh_title()
        return True


    def request_close(self):
        if self.confirm_discard_changes():
            self.destroy()


    def open_rom(self):
        path=filedialog.askopenfilename(title='Open Link’s Awakening DX ROM',filetypes=[('Game Boy ROM','*.gbc *.gb'),('All files','*.*')])
        if not path:return
        if not self.confirm_discard_changes():return
        try:
            from windfish.rom.windfish_editing_patch import open_document
            def confirm_upgrade(missing,size):
                return messagebox.askyesno('Windfish ROM Compatibility',
                    'Windfish supports expanded 2 MiB English Link’s Awakening DX revision 2 ROMs. '
                    'Compatible 1 MiB ROMs will be expanded automatically, and custom code will be installed '
                    'to enable extended editing features.\n\n'
                    'Recent native Windfish ROMs are updated to the current format and runtime when needed. '
                    'HUD on Top and VWF ROMs are not currently supported.\n\n'
                    'Changes remain in memory until you save the ROM.\n\n'
                    'Do you want to continue?',parent=self)
            document = open_document(path,confirm_upgrade)
            if document is None:return
            data = document.data
            validate_mode(data)
            render(data,0,scale=1)
        except Exception as exc:
            messagebox.showerror('Cannot open ROM',str(exc));return
        from windfish.overworld.windfish_sprite_edit import snapshot_room_capacities
        capacities, shared = snapshot_room_capacities(data)
        self.sprite_capacities = capacities
        self.sprite_shared_streams = shared
        self.history.clear()
        if hasattr(self,'_bg_palette_undo'):self._bg_palette_undo.clear()
        self.document=document
        self.data=data
        self.collision_brush = None
        self._collision_drag = None
        self.collision_capacities = snapshot_capacities(data)
        self.collision_selected = None
        self.collision_target = None
        self.collision_mode.set(False)
        self.set_rom_menu_state(True)
        if not self.sidebar.winfo_manager():
            self.sidebar.pack(side='right', fill='y')
        self.palette_patch_installed = is_installed(data)
        self.extended_sprites_enabled = extended_enabled(data)
        self.warp_mode.set(False)
        self._warp_hover_key=None;self._warp_hover_source=None;self._warp_hover_background=None
        self.paint_mode.set(False)
        self.sprite_mode.set(False)
        self.selected_tile.set(0)
        self.map16_page.set('00 — Room tiles')
        self.room=data[0x1D2BFC]
        self.alternate.set(False)
        self.full_map.set(False)
        self._overworld_area=None
        self._tile_sheets.clear()
        self._inspector_last_key = None
        self.atlas_default = None
        self.atlas_alt = None
        self.map_x = self.map_y = 0
        self.change_map_mode()
        self.refresh_title()
        self.show_room()
        for window in self.catalog_windows.values():
            if window.winfo_exists():
                window.event_generate('<<WindfishRomChanged>>')
        self.update_inspector()
        self.update_room_settings()
        self.draw_nav()


    def refresh_title(self):
        if self.document is None:
            self.title('Windfish Editor — Overworld')
        else:
            mark = ' *' if self.document.dirty else ''
            from windfish.compatibility.api import is_vwf
            profile_label=' · VWF' if is_vwf(self.document.data) else ''
            self.title(f'Windfish Editor — {self.document.path.name}{mark}{profile_label}')


    def save_rom(self):
        if self.document is None:
            return
        try:
            self.document.data[0x1D2BFC] = self.room
            self.document.save()
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc))
            return
        self.refresh_title()
        self.show_room()


    def save_rom_as(self):
        if self.document is None:
            messagebox.showinfo('Save ROM As', 'Open a ROM first.')
            return
        source = self.document.path
        path = filedialog.asksaveasfilename(
            title='Save ROM As',
            initialdir=str(source.parent),
            initialfile=source.stem + '_windfish.gbc',
            defaultextension='.gbc',
            filetypes=[('Game Boy Color ROM', '*.gbc'), ('All files', '*.*')])
        if not path:
            return
        try:
            self.document.data[0x1D2BFC] = self.room
            target = self.document.save_as(path)
        except Exception as exc:
            messagebox.showerror('Save failed', str(exc))
            return
        self.refresh_title()
        self.show_room()
        messagebox.showinfo('ROM saved', f'Saved and verified:\n{target}\n\nThis is now the active ROM file.')


    def end_stroke(self, event=None):
        self._paint_drag_cell = None
        self.history.commit()


    def refresh_changed_rooms(self, changes):
        self.refresh_visual_cache()
        self.show_room()
        if self.dungeon_window is not None:self.dungeon_window.refresh_document()


    def undo(self):
        if self.document is None:
            return
        self.end_stroke()
        changes = self.history.undo(self.document.data)
        if changes:
            self.extended_sprites_enabled = extended_enabled(self.data)
            from windfish.overworld.windfish_sprite_edit import snapshot_room_capacities
            self.sprite_capacities,self.sprite_shared_streams = snapshot_room_capacities(self.data)
            self.refresh_changed_rooms(changes)


    def redo(self):
        if self.document is None:
            return
        self.end_stroke()
        changes = self.history.redo(self.document.data)
        if changes:
            self.extended_sprites_enabled = extended_enabled(self.data)
            from windfish.overworld.windfish_sprite_edit import snapshot_room_capacities
            self.sprite_capacities,self.sprite_shared_streams = snapshot_room_capacities(self.data)
            self.refresh_changed_rooms(changes)


