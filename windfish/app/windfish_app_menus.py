"""Main-window menus and focus-scoped keyboard shortcuts.

Methods keep the Viewer interface and call the existing guarded backends.
The application composes this mixin; it must not import Viewer.
"""
import tkinter as tk


from windfish.app.windfish_gui_shared import window_shortcut, bind_overlay_shortcuts, add_overlay_menu


class AppMenusMixin:
    def build_menus_and_shortcuts(self):
        menu = tk.Menu(self)
        filemenu = tk.Menu(menu, tearoff=False)
        filemenu.add_command(label='Open ROM…', command=self.open_rom, accelerator='Ctrl+O')
        filemenu.add_command(label='Save ROM', command=self.save_rom, accelerator='Ctrl+S')
        filemenu.add_command(label='Save ROM As…', command=self.save_rom_as)
        filemenu.add_separator()
        filemenu.add_command(label='Exit', command=self.request_close)
        menu.add_cascade(label='File', menu=filemenu)
        editmenu = tk.Menu(menu, tearoff=False)
        editmenu.add_command(label='Undo', command=self.undo, accelerator='Ctrl+Z', state='disabled')
        editmenu.add_command(label='Redo', command=self.redo, accelerator='Ctrl+Y', state='disabled')
        editmenu.add_separator()
        editmenu.add_checkbutton(label='Edit Room Tiles', variable=self.paint_mode, command=self.update_edit_mode)
        self.editmenu = editmenu
        self.paint_menu_index = editmenu.index('end')
        editmenu.add_checkbutton(label='Edit Room Sprites', variable=self.sprite_mode, command=self.toggle_sprite_mode)
        self.sprite_menu_index = editmenu.index('end')
        editmenu.add_checkbutton(label='Edit Room Collisions', variable=self.collision_mode, command=self.toggle_collision_mode)
        editmenu.add_checkbutton(label='Add Warp',variable=self.warp_mode,command=self.toggle_warp_mode)
        self.warp_menu_index=editmenu.index('end')
        from windfish.app.windfish_room_actions import install as install_room_actions
        install_room_actions(self,editmenu)
        editmenu.configure(postcommand=self.update_edit_menu)
        menu.add_cascade(label='Edit', menu=editmenu)
        viewmenu = tk.Menu(menu, tearoff=False)
        viewmenu.add_checkbutton(label='View Full Overworld', variable=self.full_map, command=self.change_map_mode)
        self.full_map_menu_index = viewmenu.index('end')
        viewmenu.add_separator()
        overlay_variables = (self.room_borders, self.show_sprites, self.show_sprite_ids, self.show_collisions)
        self.borders_menu_index = add_overlay_menu(
            viewmenu, overlay_variables, self.show_room, borders_label='Overworld Room Borders')[0]
        self.viewmenu = viewmenu
        viewmenu.add_separator()
        for level in range(1, 5):
            viewmenu.add_radiobutton(label=f'Zoom {level}x', variable=self.zoom, value=level, command=self.show_room)
        viewmenu.add_separator()
        from windfish.app.windfish_screen_editor import open_screen_editor
        viewmenu.add_command(label='8x8 Tile Viewer...', command=self.open_8x8_tile_viewer)
        self.tile_viewer_menu_index=viewmenu.index('end')
        viewmenu.add_command(label='Room GFX Settings...', command=self.open_room_settings)
        self.room_gfx_menu_index=viewmenu.index('end')
        viewmenu.add_checkbutton(label='Room Properties', variable=self.show_inspector, command=self.toggle_inspector)
        self.inspector_menu_index = viewmenu.index('end')
        viewmenu.configure(postcommand=self.update_view_menu)
        menu.add_cascade(label='View', menu=viewmenu)
        editors_menu = tk.Menu(menu, tearoff=False)
        editors_menu.add_command(label='Dungeon Editor...',command=self.open_dungeon_window)
        editors_menu.add_command(label='Screen Editor...', command=lambda: open_screen_editor(self))
        editors_menu.add_separator()
        editors_menu.add_command(label='Tile Selector...', command=lambda: self.open_catalog_window('tiles'))
        editors_menu.add_command(label='Collision Selector...', command=self.open_add_collisions)
        editors_menu.add_command(label='Sprite Selector...', command=lambda: self.open_catalog_window('sprites'))
        editors_menu.add_separator()
        editors_menu.add_command(label='Palette editor...', command=self.open_bg_palette_editor)
        editors_menu.add_command(label='16x16 Tile Map Editor...',command=self.open_tile_definition_editor)
        from windfish.app.windfish_text_editor import open_text_editor
        editors_menu.add_command(label='Text Editor…', command=lambda: open_text_editor(self))
        self.editors_menu = editors_menu
        self.main_menu = menu
        self.edit_cascade_index = menu.index('Edit')
        menu.add_cascade(label='Editors', menu=editors_menu)
        self.editors_cascade_index = menu.index('Editors')
        from windfish.app.windfish_collision_settings import install_menu
        install_menu(self, menu)
        helpmenu = tk.Menu(menu, tearoff=False)
        from tkinter import messagebox
        from windfish.app.windfish_version import VERSION
        helpmenu.add_command(label='About Windfish…', command=lambda: messagebox.showinfo(
            'About Windfish', f'Windfish Editor — {VERSION}', parent=self))
        menu.add_cascade(label='Help', menu=helpmenu)
        self.config(menu=menu)
        self.set_rom_menu_state(False)
        # Global Tk bindings otherwise fire even while a floating editor is
        # active. Dispatch editor shortcuts ONLY when the main root owns focus.
        # Return None for other windows so their normal Listbox/Entry keyboard
        # navigation (including arrow keys and text editing) still works.
        def main_window_shortcut(callback):
            return window_shortcut(self, callback, focus=True)

        self.bind_all('<Control-o>', main_window_shortcut(self.open_rom))
        self.bind_all('<Control-s>', main_window_shortcut(self.save_rom))
        self.bind_all('<Control-z>', main_window_shortcut(self.undo))
        bind_overlay_shortcuts(self, overlay_variables, self.show_room, global_bind=True)
        self.bind('<Delete>', self.delete_selected_sprite)
        self.bind_all('<Control-y>', main_window_shortcut(self.redo))
        for key, dx, dy in (('Left', -1, 0), ('Right', 1, 0),
                            ('Up', 0, -1), ('Down', 0, 1)):
            self.bind_all(f'<{key}>', main_window_shortcut(
                lambda x=dx, y=dy: self.move_room(x, y)))
        for key in ('<plus>', '<equal>', '<KP_Add>'):
            self.bind_all(key, main_window_shortcut(lambda: self.change_zoom(1)))
        for key in ('<minus>', '<KP_Subtract>'):
            self.bind_all(key, main_window_shortcut(lambda: self.change_zoom(-1)))
        for key in ('<asterisk>', '<KP_Multiply>'):
            self.bind_all(key, main_window_shortcut(self.toggle_alternate_map))

    def set_rom_menu_state(self, loaded):
        """Keep Edit and Editors inaccessible until a ROM is loaded."""
        state = 'normal' if loaded else 'disabled'
        self.main_menu.entryconfigure(self.edit_cascade_index, state=state)
        self.main_menu.entryconfigure(self.editors_cascade_index, state=state)


    def update_view_menu(self):
        for index in (self.room_gfx_menu_index,self.tile_viewer_menu_index):
            self.viewmenu.entryconfigure(index,state='normal' if self.data is not None else 'disabled')
        self.viewmenu.entryconfigure(self.inspector_menu_index, state='normal' if self.data is not None else 'disabled')
        self.viewmenu.entryconfigure(self.full_map_menu_index, state='normal' if self.data is not None else 'disabled')
        self.viewmenu.entryconfigure(self.borders_menu_index, state='normal' if self.data is not None else 'disabled')


    def update_edit_menu(self):
        self.editmenu.entryconfigure(0, state='normal' if self.document and self.history.can_undo else 'disabled')
        self.editmenu.entryconfigure(1, state='normal' if self.document and self.history.can_redo else 'disabled')
        self.editmenu.entryconfigure(self.paint_menu_index, state='normal' if self.document else 'disabled')
        self.editmenu.entryconfigure(self.sprite_menu_index, state='normal' if self.document else 'disabled')
        self.editmenu.entryconfigure(self.warp_menu_index,state='normal' if self.document else 'disabled')



