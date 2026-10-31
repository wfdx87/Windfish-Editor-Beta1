"""Floating overworld tile and sprite selector windows.

Methods keep the Viewer interface and call the existing guarded backends.
The application composes this mixin; it must not import Viewer.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from windfish.rendering.windfish_overworld_render import SPECIAL_MAP
from windfish.overworld.windfish_sprites import read_room_sprites
from windfish.rendering.windfish_sprite_render import render_sprite_result, SpriteRenderResult
from windfish.rendering.windfish_sprite_definitions import SPRITE_DEFINITIONS
from windfish.rendering.windfish_sprite_names import SPRITE_NAMES


from windfish.app.windfish_gui_shared import tile_canvas, tile_cell, tile_rectangle, tile_values, draw_tile_sheet


class AppSelectorsMixin:
    def open_tile_sheet_window(self):
        """16x16 graphical tileset picker, with drag-to-select rectangular stamps."""
        existing = self.catalog_windows.get('tiles')
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return
        win = tk.Toplevel(self)
        win.title('Tile Selector')
        win.transient(self)
        win.geometry('350x260')
        win.minsize(350, 200)
        win.resizable(True, True)
        self.catalog_windows['tiles'] = win
        win.protocol('WM_DELETE_WINDOW', lambda: (self.catalog_windows.pop('tiles', None),
                                                   setattr(self, '_tile_catalog_update', None), win.destroy()))
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill='both', expand=True)
        self.build_tile_page_control(frame)
        from windfish.overworld.windfish_collision_palette import build_draw_controls
        build_draw_controls(frame,self.direct_add_collisions,self.recalculate_collisions)
        canvas = tile_canvas(frame, win.cget('bg'))
        label = ttk.Label(frame, text='Select tiles by clicking or dragging. Right-click the map to paste.',wraplength=320)
        label.pack(fill='x', pady=(6, 0))
        state = {'start': None, 'rect': (0,0,0,0), 'photo': None, 'sheet': None, 'cell': 16}

        def draw_sheet():
            if not win.winfo_exists() or self.data is None:
                return
            special = self.alternate.get() and self.room in SPECIAL_MAP
            try:
                key = (self.room, special)
                sheet = self._tile_sheets.get(key)
                if sheet is None:
                    _, sheet, _ = self.cached_room_render( self.room, special=special, scale=1)
                    self._tile_sheets[key] = sheet
                    while len(self._tile_sheets)>16:self._tile_sheets.pop(next(iter(self._tile_sheets)))
                page=self.tile_page_index()
                sheet=sheet.crop((0,page*256,256,page*256+256))
                state['sheet'] = sheet
                from windfish.app.windfish_selector_size import cell_size
                cell = cell_size(canvas.winfo_width(),canvas.winfo_height())
                state['cell'] = cell
                state['photo'] = draw_tile_sheet(canvas, sheet, cell)
                x0,y0,x1,y1=state['rect']
                canvas.create_rectangle(x0*cell,y0*cell,(x1+1)*cell,(y1+1)*cell,
                                        outline='#ffff55',width=3,tags='selection')
            except Exception as exc:
                canvas.delete('all')
                canvas.create_text(12,12,anchor='nw',text=str(exc))

        def cell_at(event):
            return tile_cell(event.x, event.y, state['cell'])

        def choose(start, end):
            x0,y0,x1,y1 = tile_rectangle(start, end)
            state['rect']=(x0,y0,x1,y1)
            values = tuple(t+self.tile_page_index()*256 for t in tile_values(state['rect']))
            special=self.alternate.get() and self.room in SPECIAL_MAP
            # Negative map coordinates mean the selection comes from the palette,
            # not from a movable region on the map.
            self.tile_selection=(self.room,special,-1,-1,x1-x0+1,y1-y0+1,values)
            self.selected_tile.set(values[0])
            label.configure(text=f'Tile {values[0]:02X}  |  {x1-x0+1} × {y1-y0+1} tiles  |  Right-click map to paste')
            canvas.delete('selection')
            c=state['cell']
            canvas.create_rectangle(x0*c,y0*c,(x1+1)*c,(y1+1)*c,
                                    outline='#ffff55',width=3,tags='selection')
            self._refresh_selection_only()

        def press(event):
            state['start']=cell_at(event)
            choose(state['start'],state['start'])
        def drag(event):
            if state['start'] is not None:
                choose(state['start'],cell_at(event))
        def release(event):
            if state['start'] is not None:
                choose(state['start'],cell_at(event))
            state['start']=None
        canvas.bind('<ButtonPress-1>',press)
        canvas.bind('<B1-Motion>',drag)
        canvas.bind('<ButtonRelease-1>',release)
        canvas.bind('<Configure>',lambda event:draw_sheet())
        win.bind('<<WindfishRoomChanged>>',lambda event:draw_sheet())
        win.bind('<<WindfishRomChanged>>',lambda event:draw_sheet())
        self._tile_catalog_update=draw_sheet
        def set_size_limits():
            if not win.winfo_exists():return
            from windfish.app.windfish_selector_size import configure_bounds
            configure_bounds(win,canvas,maximize=True)
            draw_sheet()
        win.after_idle(set_size_limits)


    def open_8x8_tile_viewer(self):
        from windfish.app.windfish_8x8_tile_viewer import open_tile_viewer
        open_tile_viewer(self)

    def _refresh_selection_only(self):
        """Redraw selection without refreshing nav, inspector, palettes or ROM rendering."""
        if self.data is None or not self.paint_mode.get():
            return
        if self.full_map.get():
            self.draw_full_map()
            return
        special=self.alternate.get() and self.room in SPECIAL_MAP
        key=(self.room,special,self.zoom.get())
        base=self._room_image_cache.get(key)
        if base is None:
            base,_,_=self.cached_room_render(self.room,special=special,scale=self.zoom.get())
            self._room_image_cache[key]=base
            while len(self._room_image_cache)>8:self._room_image_cache.pop(next(iter(self._room_image_cache)))
        image=self._draw_tile_selection(base,self.room,self.zoom.get())
        image=self.collision_overlay(image,self.room,self.zoom.get())
        image=self.draw_sprite_positions_on_image(image,self.room,self.zoom.get())
        image=self._draw_room_border_on_image(image,self.zoom.get())
        self.image_ref=ImageTk.PhotoImage(image)
        self.preview.configure(image=self.image_ref,text='')


    def open_catalog_window(self, kind):
        if kind == "tiles":
            return self.open_tile_sheet_window()
        """Lunar Magic-style floating selection palette; intentionally read-only for now."""
        existing = self.catalog_windows.get(kind)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return
        is_sprite = kind == 'sprites'
        title = 'Sprite Selector' if is_sprite else 'Tile Selector'
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry('735x300')
        win.resizable(False, False)
        win.transient(self)
        self.catalog_windows[kind] = win
        def close():
            self.catalog_windows.pop(kind, None)
            if is_sprite:
                self._sprite_catalog_select = None
            else:
                self._tile_catalog_update = None
            win.destroy()
        win.protocol('WM_DELETE_WINDOW', close)
        body = ttk.Panedwindow(win, orient='horizontal')
        win.rowconfigure(0, weight=1)
        win.columnconfigure(0, weight=1)
        body.grid(row=0, column=0, sticky='nsew', padx=6, pady=(0, 4))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=0)
        body.add(right, weight=1)
        win.after_idle(lambda: body.sashpos(0, 245))
        body.bind('<ButtonPress-1>', lambda event: 'break')
        list_frame = ttk.Frame(left)
        list_frame.pack(fill='both', expand=True)
        items = tk.Listbox(list_frame, exportselection=False, font=('Consolas', 10), activestyle='dotbox')
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=items.yview)
        items.configure(yscrollcommand=scrollbar.set)
        items.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        preview = tk.Canvas(right, width=160, height=160, highlightthickness=0)
        preview.grid(row=0, column=0, sticky='nsew')
        frame_state = {'sprite_id': None, 'frame': 0}
        availability_text = tk.StringVar(value='')
        ttk.Label(right, textvariable=availability_text, anchor='center',
                  wraplength=440).grid(row=1, column=0, sticky='ew')
        if is_sprite:
            frame_controls = ttk.Frame(right)
            right.rowconfigure(2, minsize=52)
            frame_controls.grid(row=2, column=0, sticky='ew', pady=(0, 12))
            frame_controls.columnconfigure(1, weight=1)
            previous_frame = ttk.Button(frame_controls, text='<', width=4,
                                        command=lambda: cycle_preview_frame(-1))
            previous_frame.grid(row=0, column=0, padx=(8, 4))
            frame_text = tk.StringVar(value='')
            ttk.Label(frame_controls, textvariable=frame_text, anchor='center').grid(
                row=0, column=1, sticky='ew')
            next_frame = ttk.Button(frame_controls, text='>', width=4,
                                    command=lambda: cycle_preview_frame(1))
            next_frame.grid(row=0, column=2, padx=(4, 8))
        selected_text = tk.StringVar(value='Select an entry')
        ttk.Label(win, textvariable=selected_text, anchor='w').grid(
            row=1, column=0, sticky='ew', padx=7, pady=(0, 5))
        if is_sprite:
            catalog = [(idx, SPRITE_NAMES.get(idx, 'Unknown sprite')) for idx in range(255)]
        else:
            catalog = [(idx, '') for idx in range(256)]
        visible = []
        # The catalog previews use the same ROM renderer as the map and Sprites tab.
        # Preview frame selection belongs to this window, never the map definition.
        preview_photo = [None]  # retain Tk image reference while the window is open

        def catalog_sprite_image(sprite_id, frame):
            if self.data is None:
                return SpriteRenderResult(None, True)
            # Use exactly the same room-specific renderer as the main map.
            # Only fall back to another room if the selected room has no such sprite.
            try:
                here = any(sp.id == sprite_id for sp in read_room_sprites(self.data, self.room)['sprites'])
            except (ValueError, IndexError, KeyError):
                here = False
            result = render_sprite_result(self.data, self.room, sprite_id, frame=frame)
            if here:
                return result
            for room in range(256):
                try:
                    if not any(sp.id == sprite_id for sp in read_room_sprites(self.data, room)['sprites']):
                        continue
                    candidate = render_sprite_result(self.data, room, sprite_id, frame=frame, palette_room=self.room)
                    if not candidate.is_placeholder:
                        return candidate
                except (ValueError, IndexError, KeyError):
                    continue
            return result

        def cycle_preview_frame(direction):
            selection = items.curselection()
            if not is_sprite or not selection or selection[0] >= len(visible):
                return
            sprite_id = visible[selection[0]][0]
            definition = SPRITE_DEFINITIONS.get(sprite_id)
            if definition is None or len(definition.frames) < 2:
                return
            # Only window-local state changes. Overworld display_frame stays intact.
            from windfish.app.windfish_sprite_display import cycle_preview_frame
            frame_state['frame'] = cycle_preview_frame(sprite_id,frame_state['frame'],direction)
            paint_preview()

        def paint_preview(_event=None):
            preview.delete('all')
            w = max(preview.winfo_width(), 120)
            h = max(preview.winfo_height(), 120)
            selection = items.curselection()
            if not selection or selection[0] >= len(visible):
                return
            idx, name = visible[selection[0]]
            selected_text.set(f'{idx:02X}  {name}  —  selected for placement' if is_sprite else f'{idx:02X}')
            if is_sprite:
                self.sprite_brush = idx
                definition = SPRITE_DEFINITIONS.get(idx)
                if frame_state['sprite_id'] != idx:
                    frame_state['sprite_id'] = idx
                    frame_state['frame'] = definition.display_frame if definition else 0
                count = len(definition.frames) if definition else 0
                enabled = self.data is not None and count > 1
                previous_frame.configure(state='normal' if enabled else 'disabled')
                next_frame.configure(state='normal' if enabled else 'disabled')
                frame_text.set(f"Frame {frame_state['frame']} / {count - 1}" if count else '')
            else:
                self.selected_tile.set(idx)
            preview_photo[0] = None
            if is_sprite:
                result = catalog_sprite_image(idx, frame_state['frame'])
                sprite_image = result.image
                availability_text.set(result.message)
                if sprite_image is not None:
                    # Scale with nearest-neighbor to preserve Game Boy pixels.
                    scale = max(1, min((w - 20) // sprite_image.width, (h - 32) // sprite_image.height, 8))
                    scaled = sprite_image.convert('RGBA').resize(
                        (sprite_image.width * scale, sprite_image.height * scale), Image.Resampling.NEAREST)
                    preview_photo[0] = ImageTk.PhotoImage(scaled)
                    preview.create_image(w // 2, h // 2 - 7, image=preview_photo[0])
                    return
                message = ''
            else:
                message = ''
                if self.data is not None:
                    try:
                        art=self._tile_image(self.room,self.alternate.get() and self.room in SPECIAL_MAP,idx)
                        scale=max(1,min((w-20)//16,(h-45)//16,8))
                        preview_photo[0]=ImageTk.PhotoImage(art.resize((16*scale,16*scale),Image.Resampling.NEAREST))
                        preview.create_image(w//2,h//2-10,image=preview_photo[0])
                        preview.create_text(w//2,h-15,text=f'Tile {idx:02X}')
                        return
                    except (ValueError,IndexError,KeyError):pass
            preview.create_text(w // 2, h // 2 - 13, text=f'{idx:02X}', fill='white', font=('Consolas', 22, 'bold'))
            if message:
                preview.create_text(w // 2, h // 2 + 17, text=message, fill='#b5d5e8', font=('TkDefaultFont', 9))
        def refill(*_args):
            term = ''
            current = visible[items.curselection()[0]][0] if items.curselection() and visible else None
            visible.clear()
            items.delete(0, 'end')
            for idx, name in catalog:
                label = f'{idx:02X}  {name}' if is_sprite else f'{idx:02X}'
                if term in label.lower():
                    visible.append((idx, name))
                    items.insert('end', label)
            if visible:
                choice = next((i for i, (idx, _) in enumerate(visible) if idx == current), 0)
                items.selection_set(choice)
                items.see(choice)
            else:
                selected_text.set('No matching entries')
            paint_preview()
        def select_sprite_id(sprite_id):
            """Keep the Add Sprites list and map-selected brush synchronized."""
            if not is_sprite or not win.winfo_exists():
                return
            # A filter may hide the map-selected ID; clear it to show the match.
            if not any(idx == sprite_id for idx, _ in visible):
                refill()
            for row, (idx, _) in enumerate(visible):
                if idx == sprite_id:
                    items.selection_clear(0, 'end')
                    items.selection_set(row)
                    items.activate(row)
                    items.see(row)
                    paint_preview()
                    return
        if is_sprite:
            self._sprite_catalog_select = select_sprite_id
        else:
            self._tile_catalog_update = lambda: (refill(), paint_preview())
        items.bind('<<ListboxSelect>>', paint_preview)
        preview.bind('<Configure>', paint_preview)
        win.bind('<<WindfishRomChanged>>', paint_preview)
        win.bind('<<WindfishRoomChanged>>', paint_preview)
        initial_sprite_brush = self.sprite_brush if is_sprite else None
        refill()
        if is_sprite and initial_sprite_brush is not None:
            select_sprite_id(initial_sprite_brush)
        elif not is_sprite:
            items.selection_clear(0,'end')
            items.selection_set(self.selected_tile.get())
            items.see(self.selected_tile.get())
            paint_preview()


