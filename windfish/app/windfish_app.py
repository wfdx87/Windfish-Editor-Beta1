"""Windfish application and overworld editing window.

Launch with python run-windfish-editor.py. Requires Pillow and Tkinter.
"""
import tkinter as tk
from tkinter import ttk
from windfish.overworld.windfish_collision_objects import ALTERNATE_POINTERS
from windfish.overworld.windfish_collision_editor import CollisionEditorMixin
from windfish.rom.windfish_history import StrokeHistory
from windfish.overworld.windfish_warps import WarpEditorMixin
from windfish.overworld.windfish_warp_placement import WarpPlacementMixin
from windfish.app.windfish_tile_editor import TileEditorMixin
from windfish.app.windfish_bg_palette_editor import BgPaletteEditorMixin

from windfish.overworld.windfish_overworld_properties import OverworldPropertiesMixin
from windfish.overworld.windfish_overworld_settings import OverworldSettingsMixin
from windfish.overworld.windfish_overworld_sprites import OverworldSpriteMixin

from windfish.rendering.windfish_render_cache import OverworldRenderCacheMixin


from windfish.app.windfish_app_menus import AppMenusMixin
from windfish.app.windfish_app_document import AppDocumentMixin
from windfish.app.windfish_app_selectors import AppSelectorsMixin
from windfish.app.windfish_app_navigation import AppNavigationMixin
from windfish.overworld.windfish_overworld_tiles import OverworldTilesMixin

class Viewer(WarpPlacementMixin, AppMenusMixin, AppDocumentMixin, AppSelectorsMixin, AppNavigationMixin, OverworldTilesMixin, OverworldRenderCacheMixin, OverworldPropertiesMixin, OverworldSettingsMixin, OverworldSpriteMixin, TileEditorMixin, CollisionEditorMixin, BgPaletteEditorMixin, WarpEditorMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Windfish Editor — Overworld')
        self.geometry('1030x650')
        # Windows: maximize the application on startup (not borderless F11 mode).
        try:
            self.state('zoomed')
        except tk.TclError:
            self.attributes('-fullscreen', True)
            self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.minsize(650, 400)
        self.data = None
        self.document = None
        self.dungeon_window = None
        self.room = 0
        self.zoom = tk.IntVar(value=3)
        self.alternate = tk.BooleanVar(value=False)
        self.image_ref = None
        self.paint_mode = tk.BooleanVar(value=False)
        self.warp_mode = tk.BooleanVar(value=False)
        self.direct_add_collisions = tk.BooleanVar(value=False)
        self.collision_mode = tk.BooleanVar(value=False)
        self.show_collisions = tk.BooleanVar(value=False)
        self.collision_selected = None
        self.collision_target = None
        self.collision_brush = None
        self.collision_brush_direction = tk.StringVar(value='Single')
        self.collision_brush_length = tk.IntVar(value=1)
        self.collision_combined = tk.BooleanVar(value=True)
        self._collision_drag = None
        self.collision_capacities = {}
        self.collision_alternates = ALTERNATE_POINTERS
        self.sprite_mode = tk.BooleanVar(value=False)
        self.sprite_brush = None
        self.sprite_capacities = {}
        self.sprite_shared_streams = set()
        self._sprite_drag = None
        self._sprite_drag_changed = False
        self.selected_tile = tk.IntVar(value=0)
        self.map16_page = tk.StringVar(value='00 — Room tiles')
        self.tileset_marker = None
        self.tile_selection = None  # (room, alternate, x0, y0, width, height, bytes)
        self._tile_select_start = None
        self._tile_select_action = None
        self._tile_select_target = None
        self._tile_catalog_update = None
        self._room_image_cache = {}
        self._inspector_last_key = None
        self._paint_drag_cell = None
        self.history = StrokeHistory()
        self.full_map = tk.BooleanVar(value=False)
        self.room_borders = tk.BooleanVar(value=False)
        self.atlas_default = None
        self.atlas_alt = None
        self._tile_sheets = {}  # Room-specific graphics cached for fast painting
        self.map_x = 0  # Scaled-pixel viewport origin
        self.map_y = 0
        self.drag_start = None
        self.nav_window = None
        self.nav = None
        self.inspector_window = None
        self.inspector_image = None
        self.tilepicker_scale = 2
        self.tilepicker_label = tk.StringVar(value="Selected tile: 0x00")
        self.show_inspector = tk.BooleanVar(value=False)
        self.show_navigator = tk.BooleanVar(value=True)
        self.show_sprites = tk.BooleanVar(value=True)
        self.show_sprite_ids = tk.BooleanVar(value=False)
        self.selected_sprite = None
        self.sprite_sheet_image = None
        self._sprite_photo_refs = []
        self.catalog_windows = {}
        self._sprite_catalog_select = None
        self.room_settings_window = None
        self.bg_palette_window = None
        self.bg_palette_id_var = None
        self.bg_palette_source_var = None
        self.bg_palette_canvas = None
        self.bg_palette_copy_button = None
        self.room_settings_vars = {}
        self.palette_patch_installed = False
        self.extended_sprites_enabled = False
        self.room_settings_combos = {}
        self.sprite_slot_vars = []
        self.sprite_slot_combos = []
        self.build_menus_and_shortcuts()
        content = ttk.Frame(self, padding=0)
        content.pack(fill='both', expand=True)
        # Fixed 16-pixel margin on the top and left, independent of zoom.
        self.render_area = ttk.Frame(content, padding=(16, 16, 0, 0))
        self.render_area.pack(side='left', fill='both', expand=True)
        self.sidebar = ttk.Frame(content, width=310, padding=(8, 8, 8, 8))
        # Keep sidebar hidden until a ROM has been opened successfully.
        self.sidebar.pack_propagate(False)
        self.nav = tk.Canvas(self.sidebar, bg='#22252b', highlightthickness=0, height=292)
        self.nav.pack(side='top', fill='x')
        self.alternate_checkbox = ttk.Checkbutton(self.sidebar, text='Show alternate Rooms', variable=self.alternate, command=self.toggle_alternate_rooms)
        self.alternate_checkbox.pack(side='top', anchor='w', pady=(8, 0))
        ttk.Button(self.sidebar, text='Recalculate Collisions',
                   command=self.recalculate_collisions).pack(side='top', fill='x', pady=(8, 0))
        self.nav.bind('<Button-1>', self.select_from_map)
        self.nav.bind('<ButtonPress-3>',self.begin_nav_area)
        self.nav.bind('<B3-Motion>',self.drag_nav_area)
        self.nav.bind('<ButtonRelease-3>',self.end_nav_area)
        self.nav.bind('<Configure>', lambda e: self.draw_nav())
        self.preview = ttk.Label(self.render_area, anchor='nw', text='', justify='left')
        self.preview.pack(anchor='nw')
        self.preview.bind('<Button-1>', self.click_single_room)
        self.preview.bind('<Double-Button-1>', self.sprite_double_click_single)
        self.preview.bind('<Button-3>', self.sprite_right_press_single)
        self.preview.bind('<B3-Motion>', self.sprite_right_drag_single)
        self.preview.bind('<ButtonRelease-3>', self.sprite_right_release_single)
        self.preview.bind('<B1-Motion>', self.sprite_left_drag_single)
        self.preview.bind('<ButtonRelease-1>', self.sprite_left_release_single)
        self.map_canvas = tk.Canvas(self.render_area, highlightthickness=0, bg='#202020', cursor='fleur')
        self.map_canvas.bind('<Configure>', lambda e: self.draw_full_map())
        self.map_canvas.bind('<ButtonPress-2>', self.pan_start)
        self.map_canvas.bind('<B2-Motion>', self.pan_move)
        self.map_canvas.bind('<ButtonRelease-2>', self.pan_end)
        # Some Windows mouse drivers send Button-2; Tk on other platforms may
        # identify the middle button as Button-2 as well.
        self.preview.bind('<Motion>', lambda event:self.collision_hover(event,False), add='+')
        self.preview.bind('<Leave>', lambda event:self.collision_leave(event,False), add='+')
        self.map_canvas.bind('<Motion>', lambda event:self.collision_hover(event,True), add='+')
        self.map_canvas.bind('<Leave>', lambda event:self.collision_leave(event,True), add='+')
        self.bind('<Escape>',self.collision_escape,add='+')
        for widget,full in ((self.preview,False),(self.map_canvas,True)):
            widget.bind('<Motion>',lambda event,full=full:self.warp_hover(event,full),add='+')
            widget.bind('<Leave>',lambda event,full=full:self.clear_warp_hover(event,full),add='+')
        self.bind('<Escape>',self.warp_escape,add='+')
        self.map_canvas.bind('<Button-1>', self.click_full_map)
        self.map_canvas.bind('<Double-Button-1>', self.sprite_double_click_full)
        self.map_canvas.bind('<Button-3>', self.sprite_right_press_full)
        self.map_canvas.bind('<B3-Motion>', self.sprite_right_drag_full)
        self.map_canvas.bind('<ButtonRelease-3>', self.sprite_right_release_full)
        self.map_canvas.bind('<B1-Motion>', self.sprite_left_drag_full)
        self.map_canvas.bind('<ButtonRelease-1>', self.sprite_left_release_full)
        self._set_render_padding()
        self.protocol('WM_DELETE_WINDOW', self.request_close)
        self.bind('<Unmap>', self.on_main_unmap, add='+')
        self.bind('<Map>', self.on_main_map, add='+')
        self.bind('<FocusIn>', self.on_main_focus, add='+')


    def open_dungeon_window(self):
        from windfish.app.windfish_editor_guard import can_open
        if not can_open(self,'Dungeon'):return
        from windfish.dungeon.windfish_dungeon_window import DungeonWindow
        old=self.dungeon_window
        if old is not None and old.winfo_exists():
            old.deiconify();old.lift();old.refresh_document();return
        self.dungeon_window=DungeonWindow(self)


if __name__=='__main__':
    Viewer().mainloop()
