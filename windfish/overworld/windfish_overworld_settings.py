"""Overworld graphics settings and native/custom assignment controls."""
from windfish.compatibility import api as profile

import tkinter as tk
from tkinter import messagebox, ttk
from windfish.rendering.windfish_sprite_graphics import sprite_bank

class OverworldSettingsMixin:
    def _room_sog_index(self, room):
        from windfish.rom.windfish_bg_graphics import selector_offset
        return selector_offset(self.data,room)

    def open_room_settings(self):
        if self.room_settings_window is not None and self.room_settings_window.winfo_exists():
            self.room_settings_window.lift()
            self.update_room_settings()
            return
        win = tk.Toplevel(self)
        win.title('Room GFX Settings')
        win.geometry('620x620')
        win.minsize(620, 620)
        win.transient(self)
        win.protocol('WM_DELETE_WINDOW', lambda: (win.destroy(), setattr(self, 'room_settings_window', None)))
        self.room_settings_window = win
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill='both', expand=True)
        self.settings_room_label = ttk.Label(frame, font=('TkDefaultFont', 11, 'bold'))
        self.settings_room_label.pack(anchor='w', pady=(0, 8))
        notebook=ttk.Notebook(frame)
        notebook.pack(fill='both',expand=True)
        bg_frame=ttk.Frame(notebook,padding=10)
        bank1_frame=ttk.Frame(notebook,padding=10)
        sprite_frame=ttk.Frame(notebook,padding=10)
        notebook.add(bg_frame,text='BG(VRAM0)')
        notebook.add(bank1_frame,text='VRAM1 GFX')
        notebook.add(sprite_frame,text='Sprites')
        transfer_frame=ttk.Frame(notebook,padding=10)
        notebook.add(transfer_frame,text='Extraction/Insert GFX')
        notebook.select(bg_frame)
        fields = (('BG Tileset', 'sog'),)
        ttk.Label(bg_frame,text='Background graphics',font=('TkDefaultFont',10,'bold')).pack(anchor='w')
        self.room_settings_vars = {}
        self.room_settings_combos = {}
        for label, key in fields:
            line = ttk.Frame(bg_frame)
            line.pack(fill='x', pady=5)
            ttk.Label(line, text=label, width=24).pack(side='left')
            var = tk.StringVar()
            self.room_settings_vars[key] = var
            combo = ttk.Combobox(line, textvariable=var, state='readonly', width=18)
            combo.pack(side='left', fill='x', expand=True)
            self.room_settings_combos[key] = combo
            if key == 'sog':
                combo['values'] = [f'{i:02X}' for i in range(0x40)]
            elif key == 'sprite':
                combo['values'] = [f'{i:02X}' for i in range(0x100)]
            combo.bind('<<ComboboxSelected>>', lambda e, k=key: self.apply_room_setting(k))
        self.build_room_graphics_controls(bg_frame, bank1_frame)
        self.build_graphics_transfer_controls(transfer_frame)
        line=ttk.Frame(sprite_frame);line.pack(fill='x',pady=5)
        ttk.Label(line,text='Sprite tileset bank',width=24).pack(side='left')
        var=tk.StringVar();self.room_settings_vars['sprite']=var
        combo=ttk.Combobox(line,textvariable=var,state='readonly',width=18,values=[f'{i:02X}' for i in range(256)])
        combo.pack(side='left',fill='x',expand=True)
        self.room_settings_combos['sprite']=combo
        combo.bind('<<ComboboxSelected>>',lambda e:self.apply_room_setting('sprite'))
        ttk.Label(sprite_frame, text='Sprite graphics slots (experimental)',
                  font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        self.sprite_slot_vars = []
        self.sprite_slot_combos = []
        for slot in range(4):
            line = ttk.Frame(sprite_frame)
            line.pack(fill='x', pady=3)
            ttk.Label(line, text=f'Sprite slot {slot + 1}', width=24).pack(side='left')
            var = tk.StringVar()
            combo = ttk.Combobox(line, textvariable=var, state='readonly', width=18,
                                 values=[f'{v:02X}' for v in range(256)])
            combo.pack(side='left', fill='x', expand=True)
            combo.bind('<<ComboboxSelected>>', lambda e, i=slot: self.apply_sprite_slot(i))
            self.sprite_slot_vars.append(var)
            self.sprite_slot_combos.append(combo)
        ttk.Label(sprite_frame, text='00 = empty. FF also loads as empty. Slot values select 16-tile graphics blocks.',
                  wraplength=475, justify='left').pack(anchor='w', pady=(5, 0))
        self.bg_settings_detail=tk.StringVar()
        ttk.Label(bg_frame,textvariable=self.bg_settings_detail,wraplength=550).pack(anchor='w',pady=(8,0))
        self.settings_detail = tk.StringVar()
        ttk.Label(sprite_frame, textvariable=self.settings_detail, justify='left',
                  wraplength=550).pack(anchor='w', pady=(8, 0))
        self.room_graphics_status=tk.StringVar()
        ttk.Label(frame,textvariable=self.room_graphics_status,wraplength=580).pack(anchor='w',pady=(5,0))
        ttk.Label(frame, text='Changes affect the open ROM immediately; save the ROM to keep them.\n'
                  'BG graphics entries and sprite configurations may be shared between rooms.',
                  wraplength=580, justify='left').pack(anchor='w', pady=(8, 0))
        self.update_room_settings()

    def update_room_settings(self):
        win = self.room_settings_window
        if win is None or not win.winfo_exists() or not self.room_settings_vars:
            return
        if self.data is None:
            self.settings_room_label.configure(text='Open a ROM to edit room settings')
            self.settings_detail.set('')
            self.bg_settings_detail.set('')
            return
        self.refresh_room_graphics_controls()
        r = self.room
        from windfish.rom.windfish_bg_graphics import enabled as bg_enabled,available_ids
        self.room_settings_combos['sog'].configure(values=[f'{i:02X}' for i in (available_ids(self.data) if bg_enabled(self.data) else range(0x40))])
        sog_off = self._room_sog_index(r)
        bank_off = profile.bank20_table(self.data,0x830DB) + r
        vals = {'sog': self.data[sog_off], 'sprite': self.data[bank_off]}
        self.settings_room_label.configure(text=f'Overworld room {r:02X}  ({r % 16}, {r // 16})')
        for k, v in vals.items():
            self.room_settings_vars[k].set(f'{v:02X}')
        _, selectors, offsets, _ = sprite_bank(self.data, r)
        for i, v in enumerate(selectors):
            self.sprite_slot_vars[i].set(f'{v:02X}')
        shared = [i for i in range(256) if self._room_sog_index(i) == sog_off]
        self.bg_settings_detail.set(f'BG tileset table: 0x{sog_off:05X} ({len(shared)} rooms share this entry)')
        self.settings_detail.set(
            f'Sprite bank index: 0x{bank_off:05X}  •  slot IDs: ' +
            ' / '.join(f'{v:02X}' for v in selectors) +
            '\n'
            f'Sprite configuration shared by {sum(self.data[profile.bank20_table(self.data,0x830DB) + i] == vals["sprite"] for i in range(256))} room(s).')

    def apply_sprite_slot(self, slot):
        """Edit a graphics selector in the selected shared four-slot configuration."""
        if self.document is None:
            return
        try:
            room = self.room
            config = self.data[profile.bank20_table(self.data,0x830DB) + room]
            off = profile.bank20_table(self.data,0x833FB) + 4 * config + slot
            if off >= profile.bank20_table(self.data,0x83700):
                raise ValueError('Sprite configuration points outside the graphics selector table')
            value = int(self.sprite_slot_vars[slot].get(), 16)
            if not 0 <= value <= 0xFF:
                raise ValueError('Sprite slot selector must be 00–FF')
            old = self.data[off]
            if old == value:
                return
            self.data[off] = value
            try:
                # The slot selector must resolve to a valid ROM graphics block.
                sprite_bank(self.data, room)
                self.cached_room_render( room, scale=1)
            except Exception:
                self.data[off] = old
                raise
            self._inspector_last_key = None
            self.show_room()
            self.refresh_title()
        except Exception as exc:
            messagebox.showerror('Sprite slot not applied', str(exc),
                                 parent=self.room_settings_window)
        finally:
            self.update_room_settings()

    def apply_room_setting(self, key):
        if self.document is None:
            return
        offsets = {'sog': self._room_sog_index(self.room),
                   'sprite': profile.bank20_table(self.data,0x830DB) + self.room}
        off = offsets[key]
        try:
            value = int(self.room_settings_vars[key].get(), 16)
            if key == 'sprite':
                # The selected bank must refer to an existing complete table record.
                if profile.bank20_table(self.data,0x833FB) + value * 4 + 4 > profile.bank20_table(self.data,0x83700):
                    raise ValueError('Sprite bank index outside its table')
                selectors = self.data[profile.bank20_table(self.data,0x833FB) + value * 4:profile.bank20_table(self.data,0x833FB) + value * 4 + 4]
                if all(x == 0 for x in selectors):
                    raise ValueError('Sprite bank is empty')
            from windfish.rom.windfish_bg_graphics import enabled as bg_enabled,available_ids
            if key=='sog' and bg_enabled(self.data) and value not in available_ids(self.data):
                raise ValueError('Room BG block must be 00–3E; 3F crosses the graphics bank boundary.')
            if key == 'sog' and not bg_enabled(self.data) and value >= 0x40:
                raise ValueError('BG Graphics ID must be 00–3F')
            old = self.data[off]
            if old == value:
                return
            self.data[off] = value
            # Verify the selected room can still be rendered before keeping the edit.
            try:
                self.cached_room_render( self.room, scale=1)
                sprite_bank(self.data, self.room)
            except Exception:
                self.data[off] = old
                raise
            if key=='sog':
                self.end_stroke()
                self.history.record(off,old,value,self.room,False)
                self.history.commit()
            self._inspector_last_key = None
            self.show_room()
        except Exception as exc:
            messagebox.showerror('Room setting not applied', str(exc), parent=self.room_settings_window)
        finally:
            self.update_room_settings()

    def available_bg_palette_ids(self):
        return [f'{i:02X}' for i in range(0x40 if self.palette_patch_installed else 0x1F)]

