"""Palette editor UI, protected-row copying, Undo, and optional HUD/item preview."""
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, filedialog
from pathlib import Path
from windfish.rendering.windfish_sprite_palettes import palette_record_offset
from windfish.rendering.windfish_hud_preview import render_hud_preview
from PIL import ImageTk

class BgPaletteEditorMixin:
    def open_bg_palette_editor(self):
        """Floating palette editor: Eight BG and two room OBJ palettes; edit custom IDs only."""
        win = self.bg_palette_window
        if win is not None and win.winfo_exists():
            win.lift()
            self.update_bg_palette_editor()
            return
        win = tk.Toplevel(self)
        win.title('Palette editor')
        win.resizable(False, False)
        win.transient(self)
        self.bg_palette_window = win
        self._bg_palette_undo = []
        self._bg_palette_saturation_mode = 0
        win.protocol('WM_DELETE_WINDOW', self.close_bg_palette_editor)
        self.bg_palette_hover_status = tk.StringVar(value='')
        status_frame = ttk.Frame(win, relief='sunken', padding=(6, 3))
        status_frame.pack(side='bottom', fill='x')
        ttk.Label(status_frame, textvariable=self.bg_palette_hover_status, anchor='w').pack(fill='x')
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill='both', expand=True)
        # Identically sized, right-aligned comboboxes in a two-column grid.
        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=(0, 10))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text='Room Palette Set').grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.bg_palette_id_var = tk.StringVar()
        id_combo = ttk.Combobox(controls, textvariable=self.bg_palette_id_var,
                                state='readonly')
        id_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=(0, 5))
        id_combo.bind('<<ComboboxSelected>>', self.select_bg_palette_id)
        self.bg_palette_id_combo = id_combo
        self.bg_palette_source_var = tk.StringVar()
        self.bg_palette_copy_button = ttk.Button(controls, text='Copy ID Set from Room #',
                                                 command=self.copy_bg_palette_set)
        self.bg_palette_copy_button.grid(row=1, column=0, sticky='w')
        self.bg_palette_source_combo = ttk.Combobox(controls, textvariable=self.bg_palette_source_var,
                                                    state='readonly')
        self.bg_palette_source_combo.grid(row=1, column=1, sticky='ew', padx=(8, 0))
        ttk.Label(frame, text='BG 0–7 and room OBJ 6–7 • Checked rows are not overwritten', anchor='w').pack(fill='x', pady=(0, 4))
        swatch_row = ttk.Frame(frame)
        swatch_row.pack(anchor='w')
        self.bg_palette_canvas = tk.Canvas(swatch_row, width=128, height=320,
                                           bg='#eeeeee', highlightthickness=1,
                                           highlightbackground='#999999')
        self.bg_palette_canvas.pack(side='left')
        shifts = ttk.Frame(swatch_row)
        shifts.pack(side='left', padx=(12, 0))
        self.bg_palette_shift_buttons = []
        self.bg_palette_keep_rows = [tk.BooleanVar(value=False) for _ in range(10)]
        for row_index in range(10):
            pair = ttk.Frame(shifts, height=32)
            pair.pack()
            pair.pack_propagate(False)
            pair.configure(width=300)
            label = f'BG {row_index}' if row_index < 8 else f'OBJ {row_index-2}'
            ttk.Label(pair, text=label, width=6).pack(side='left')
            left = ttk.Button(pair, text='<', width=4,
                command=lambda r=row_index: self.shift_bg_palette_row(r, -1))
            right = ttk.Button(pair, text='>', width=4,
                command=lambda r=row_index: self.shift_bg_palette_row(r, 1))
            left.pack(side='left', padx=(0, 2))
            right.pack(side='left')
            ttk.Checkbutton(pair, text="Don't Overwrite",
                            variable=self.bg_palette_keep_rows[row_index]).pack(side='left', padx=(6, 0))
            self.bg_palette_shift_buttons.extend((left, right))
        self.bg_palette_canvas.bind('<Button-1>', self.adjust_bg_palette_saturation_row)
        win.bind('<Escape>', lambda event: self._set_saturation_mode(0))
        self.bg_palette_canvas.bind('<Button-3>', self.edit_bg_palette_color)
        self.bg_palette_canvas.bind('<Motion>', self.bg_palette_hover)
        self.bg_palette_canvas.bind('<Leave>', lambda event: self.bg_palette_hover_status.set(''))
        ttk.Label(frame, text='OBJ color 0 is transparent. Shared OBJ 0–5 are not edited here.',
                  wraplength=390).pack(fill='x', pady=(5, 3))
        files = ttk.Frame(frame)
        files.pack(fill='x', pady=(4, 2))
        self.bg_palette_save_button = ttk.Button(files, text='Save Palette…',
                                                command=self.save_bg_palette_file)
        self.bg_palette_save_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.bg_palette_load_button = ttk.Button(files, text='Load Palette…',
                                                command=self.load_bg_palette_file)
        self.bg_palette_load_button.pack(side='left', fill='x', expand=True)
        saturation = ttk.Frame(frame)
        saturation.pack(fill='x', pady=2)
        self.bg_palette_desaturate_button = ttk.Button(saturation, text='Saturation −20%',
                                                       command=self.toggle_bg_palette_desaturate)
        self.bg_palette_desaturate_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.bg_palette_resaturate_button = ttk.Button(saturation, text='Saturation +20%',
                                                       command=self.toggle_bg_palette_resaturate)
        self.bg_palette_resaturate_button.pack(side='left', fill='x', expand=True)
        ttk.Button(frame, text='Undo Palette Change',
                   command=self.undo_bg_palette_change).pack(fill='x', pady=2)
        self.hud_preview_visible = False
        self.hud_preview_toggle = ttk.Button(frame, text='Show HUD/Item preview',
                                             command=self.toggle_hud_preview)
        self.hud_preview_toggle.pack(fill='x', pady=(2, 0))
        self.hud_preview_frame = ttk.Frame(frame, padding=(0, 6, 0, 0))
        self.hud_preview_label = ttk.Label(self.hud_preview_frame, anchor='center')
        self.hud_preview_label.pack(fill='x')
        self.hud_preview_photo = None
        self.update_bg_palette_editor()
        self._resize_palette_editor()

    def _resize_palette_editor(self):
        win = self.bg_palette_window
        if win is None or not win.winfo_exists():
            return
        win.update_idletasks()
        # Fit the actual controls instead of keeping empty space for a hidden preview.
        win.geometry(f'{max(420, win.winfo_reqwidth())}x{win.winfo_reqheight()}')

    def toggle_hud_preview(self):
        self.hud_preview_visible = not self.hud_preview_visible
        if self.hud_preview_visible:
            self.hud_preview_frame.pack(fill='x')
            self.hud_preview_toggle.configure(text='Hide HUD/Item preview')
            self.update_bg_palette_editor()
        else:
            self.hud_preview_frame.pack_forget()
            self.hud_preview_label.configure(image='', text='')
            self.hud_preview_photo = None
            self.hud_preview_toggle.configure(text='Show HUD/Item preview')
        self._resize_palette_editor()

    def close_bg_palette_editor(self):
        if self.bg_palette_window is not None and self.bg_palette_window.winfo_exists():
            self.bg_palette_window.destroy()
        self.bg_palette_window = None
        self.bg_palette_canvas = None
        self.hud_preview_label = None
        self.hud_preview_photo = None
        self.hud_preview_frame = None
        self.hud_preview_toggle = None
        self.hud_preview_visible = False

    def bg_palette_record_offset(self, palette_id):
        return palette_record_offset(self.data, palette_id)

    def update_bg_palette_editor(self):
        win = self.bg_palette_window
        if win is None or not win.winfo_exists():
            return
        c = self.bg_palette_canvas
        c.delete('all')
        available = self.available_bg_palette_ids()
        self.bg_palette_id_combo['values'] = available
        self.bg_palette_source_combo['values'] = available
        if not self.data:
            self._set_saturation_mode(0)
            self.hud_preview_label.configure(image='')
            self.hud_preview_photo = None
            self.bg_palette_hover_status.set('')
            self.bg_palette_copy_button.configure(state='disabled')
            self.bg_palette_save_button.configure(state='disabled')
            self.bg_palette_load_button.configure(state='disabled')
            self.bg_palette_desaturate_button.configure(state='disabled')
            self.bg_palette_resaturate_button.configure(state='disabled')
            for button in self.bg_palette_shift_buttons:button.configure(state='disabled')
            return
        if self.hud_preview_visible:
            try:
                self.hud_preview_photo = ImageTk.PhotoImage(render_hud_preview(self.data, self.room))
                self.hud_preview_label.configure(image=self.hud_preview_photo, text='')
            except ValueError as exc:
                self.hud_preview_label.configure(image='', text=f'HUD preview unavailable: {exc}')
                self.hud_preview_photo = None
        pal_id = self.data[0x842EF + self.room]
        self.bg_palette_id_var.set(f'{pal_id:02X}')
        if self.bg_palette_source_var.get() not in available:
            self.bg_palette_source_var.set('00')
        editable = self.palette_patch_installed and 0x1F <= pal_id <= 0x3F
        if not editable:
            self._set_saturation_mode(0)
        self.bg_palette_copy_button.configure(state='normal' if editable else 'disabled')
        self.bg_palette_save_button.configure(state='normal')
        self.bg_palette_load_button.configure(state='normal' if editable else 'disabled')
        self.bg_palette_desaturate_button.configure(state='normal' if editable else 'disabled')
        self.bg_palette_resaturate_button.configure(state='normal' if editable else 'disabled')
        for button in self.bg_palette_shift_buttons:
            button.configure(state='normal' if editable else 'disabled')
        try:
            offset = self.bg_palette_record_offset(pal_id)
            for i in range(40):
                val = int.from_bytes(self.data[offset+i*2:offset+i*2+2], 'little')
                r, g, b = ((val & 31) * 255 // 31,
                           ((val >> 5) & 31) * 255 // 31,
                           ((val >> 10) & 31) * 255 // 31)
                x, y = (i % 4) * 32, (i // 4) * 32
                c.create_rectangle(x, y, x+32, y+32, fill=f'#{r:02x}{g:02x}{b:02x}',
                                   outline='#555555', width=1, tags=(f'bg_{i}',))
        except Exception as exc:
            self.bg_palette_hover_status.set(f'Cannot display palette: {exc}')

    def bg_palette_hover(self, event):
        if self.data is None:
            self.bg_palette_hover_status.set('')
            return
        col, row = event.x // 32, event.y // 32
        if not (0 <= col < 4 and 0 <= row < 10):
            self.bg_palette_hover_status.set('')
            return
        index = row * 4 + col
        try:
            pal_id = self.data[0x842EF + self.room]
            offset = self.bg_palette_record_offset(pal_id) + index * 2
            self.bg_palette_hover_status.set(
                f'{"BG " + str(row) if row < 8 else "OBJ " + str(row-2)}  |  Color {col}  |  ROM 0x{offset:05X}')
        except Exception as exc:
            self.bg_palette_hover_status.set(str(exc))

    def select_bg_palette_id(self, event=None):
        if self.data is None:
            return
        try:
            value = int(self.bg_palette_id_var.get(), 16)
            if f'{value:02X}' not in self.available_bg_palette_ids():
                raise ValueError('This palette requires the expansion patch')
            self._bg_palette_undo.append((0x842EF + self.room,bytes(self.data[0x842EF + self.room:0x842F0 + self.room])))
            del self._bg_palette_undo[:-64]
            self.data[0x842EF + self.room] = value
            self._refresh_bg_palette_changes()
        except Exception as exc:
            messagebox.showerror('Palette selection', str(exc), parent=self.bg_palette_window)
            self.update_bg_palette_editor()

    def edit_bg_palette_color(self, event):
        if self.data is None or not self.palette_patch_installed:
            return
        pal_id = self.data[0x842EF + self.room]
        if not 0x1F <= pal_id <= 0x3F:
            return
        col, row = event.x // 32, event.y // 32
        if not (0 <= col < 4 and 0 <= row < 10):
            return
        index = row * 4 + col
        offset = self.bg_palette_record_offset(pal_id) + index * 2
        value = int.from_bytes(self.data[offset:offset+2], 'little')
        rgb5 = (value & 31, (value >> 5) & 31, (value >> 10) & 31)
        rgb8 = tuple((v << 3) | (v >> 2) for v in rgb5)
        selected, _ = colorchooser.askcolor(color='#%02X%02X%02X' % rgb8,
            title=f'Custom set {pal_id:02X} — {"BG " + str(row) if row < 8 else "OBJ " + str(row-2)} — color {col}',
            parent=self.bg_palette_window)
        if selected is None:
            return
        new5 = tuple(max(0, min(31, round(v * 31 / 255))) for v in selected)
        new_value = new5[0] | (new5[1] << 5) | (new5[2] << 10)
        if new_value != value:
            self._bg_palette_undo.append((offset,bytes(self.data[offset:offset+2])))
            del self._bg_palette_undo[:-64]
            self.data[offset:offset+2] = new_value.to_bytes(2, 'little')
            self._refresh_bg_palette_changes()

    def shift_bg_palette_row(self, row, direction):
        """Rotate one BG or room OBJ palette row, with local undo."""
        if self.data is None or not self.palette_patch_installed:
            return
        palette_id = self.data[0x842EF + self.room]
        if not 0x1F <= palette_id <= 0x3F or not 0 <= row < 10:
            return
        offset = self.bg_palette_record_offset(palette_id) + row * 8
        old = bytes(self.data[offset:offset + 8])
        if len(old) != 8:
            return
        colors = [old[i:i+2] for i in range(0, 8, 2)]
        if direction < 0:
            colors = colors[1:] + colors[:1]
        else:
            colors = colors[-1:] + colors[:-1]
        self._bg_palette_undo.append((offset, old))
        del self._bg_palette_undo[:-64]
        self.data[offset:offset + 8] = b''.join(colors)
        self._refresh_bg_palette_changes()

    def copy_bg_palette_set(self):
        if self.data is None or not self.palette_patch_installed:
            return
        target_id = self.data[0x842EF + self.room]
        if not 0x1F <= target_id <= 0x3F:
            return
        try:
            source_id = int(self.bg_palette_source_var.get(), 16)
            source = self.bg_palette_record_offset(source_id)
            target = self.bg_palette_record_offset(target_id)
            if source == target:
                return
            keep = [variable.get() for variable in getattr(self, 'bg_palette_keep_rows', ())]
            keep = keep or [False] * 10
            if all(keep):
                self.bg_palette_hover_status.set('All rows are kept; nothing copied.')
                return
            original = bytes(self.data[target:target+0x50])
            copied = bytearray(original)
            source_bytes = bytes(self.data[source:source+0x50])
            for row in range(10):
                if not keep[row]:
                    start = row * 8
                    copied[start:start+8] = source_bytes[start:start+8]
            if copied == original:
                self.bg_palette_hover_status.set('Unchecked rows already match the source set.')
                return
            if not messagebox.askyesno('Copy palette set',
                    f'Copy {10-sum(keep)} unchecked rows from palette {source_id:02X} '
                    f'to custom palette {target_id:02X}?\n\n'
                    f'{sum(keep)} checked rows will keep their current colors.\n'
                    'Other rooms using the destination palette will also be affected.',
                    parent=self.bg_palette_window):
                return
            self._bg_palette_undo.append((target, original))
            del self._bg_palette_undo[:-64]
            self.data[target:target+0x50] = copied
            self._refresh_bg_palette_changes()
            self.bg_palette_hover_status.set(
                f'Copied unchecked rows; kept {sum(keep)} checked rows.')

        except Exception as exc:
            messagebox.showerror('Copy BG palette', str(exc), parent=self.bg_palette_window)

    def save_bg_palette_file(self):
        """Save BG0–7 followed by OBJ6–7 as 40 little-endian GBC words.

        The 80-byte file has no header. Its first 64 bytes use the same raw
        BGR555 layout as the separate Oracle viewer's palette exports.
        Protection checkboxes apply to replacement, not export.
        """
        if self.data is None:return
        try:
            palette_id = self.data[0x842EF + self.room]
            offset = self.bg_palette_record_offset(palette_id)
            raw = bytes(self.data[offset:offset+80])
            if len(raw) != 80:raise ValueError('Incomplete palette record.')
            path = filedialog.asksaveasfilename(parent=self.bg_palette_window,
                title='Save Palette — GBC BGR555', initialfile=f'palette-{palette_id:02X}.bin',
                defaultextension='.bin', filetypes=[('GBC palette data', '*.bin'), ('All files', '*.*')])
            if not path:return
            source = getattr(getattr(self, 'document', None), 'path', None)
            if source is not None and Path(path).resolve() == Path(source).resolve():
                raise ValueError('Choose a different filename; the source ROM cannot be overwritten.')
            Path(path).write_bytes(raw)
            self.bg_palette_hover_status.set('Saved 80 bytes: BG0–7, then OBJ6–7.')
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror('Save palette', str(exc), parent=self.bg_palette_window)

    def load_bg_palette_file(self):
        """Replace unprotected rows of the current custom set in one undo step.

        A 64-byte import only contains BG0–7. An 80-byte import also contains
        OBJ6–7. Check length before any mutation; never pad missing OBJ rows.
        """
        if self.data is None or not self.palette_patch_installed:return
        target_id = self.data[0x842EF + self.room]
        if not 0x1F <= target_id <= 0x3F:return
        path = filedialog.askopenfilename(parent=self.bg_palette_window,
            title='Load Palette — 64 or 80 bytes',
            filetypes=[('GBC palette data', '*.bin'), ('All files', '*.*')])
        if not path:return
        try:
            raw = Path(path).read_bytes()
            if len(raw) not in (64, 80):
                raise ValueError('Palette files must be exactly 64 bytes (BG0–7) or 80 bytes (BG0–7, OBJ6–7).')
            target = self.bg_palette_record_offset(target_id)
            original = bytes(self.data[target:target+80])
            if len(original) != 80:raise ValueError('Incomplete destination palette record.')
            merged = bytearray(original)
            protected = [variable.get() for variable in self.bg_palette_keep_rows]
            for row in range(len(raw)//8):
                if not protected[row]:merged[row*8:(row+1)*8] = raw[row*8:(row+1)*8]
            if merged == original:
                self.bg_palette_hover_status.set('No palette changes; checked rows were not overwritten.')
                return
            self._bg_palette_undo.append((target, original))
            del self._bg_palette_undo[:-64]
            self.data[target:target+80] = merged
            self._refresh_bg_palette_changes()
            self.bg_palette_hover_status.set(
                f'Loaded {len(raw)} bytes into custom set {target_id:02X}; checked rows were not overwritten.')
        except (OSError, ValueError, IndexError) as exc:
            messagebox.showerror('Load palette', str(exc), parent=self.bg_palette_window)

    def _set_saturation_mode(self, mode):
        """Only one row adjustment tool can be active: -1, 0, or +1."""
        self._bg_palette_saturation_mode = mode
        self.bg_palette_desaturate_button.configure(
            text='Saturation −20%: click a row' if mode == -1 else 'Saturation −20%')
        self.bg_palette_resaturate_button.configure(
            text='Saturation +20%: click a row' if mode == 1 else 'Saturation +20%')
        self.bg_palette_canvas.configure(cursor='crosshair' if mode else '')
        action = 'reduce' if mode == -1 else 'increase'
        self.bg_palette_hover_status.set(
            f'Click a BG or OBJ row to {action} saturation by 20%; Escape to finish.'
            if mode else '')

    def toggle_bg_palette_desaturate(self):
        self._set_saturation_mode(0 if self._bg_palette_saturation_mode == -1 else -1)

    def toggle_bg_palette_resaturate(self):
        self._set_saturation_mode(0 if self._bg_palette_saturation_mode == 1 else 1)

    def adjust_bg_palette_saturation_row(self, event):
        """Adjust one unprotected row, with one undo per click."""
        mode = self._bg_palette_saturation_mode
        if not mode:
            return
        if self.data is None or not self.palette_patch_installed:
            return
        palette_id = self.data[0x842EF + self.room]
        if not 0x1F <= palette_id <= 0x3F:
            return
        row = event.y // 32
        if not (0 <= event.x < 128 and 0 <= row < 10):
            return
        if self.bg_palette_keep_rows[row].get():
            self.bg_palette_hover_status.set("That row has Don't Overwrite checked.")
            return
        offset = self.bg_palette_record_offset(palette_id) + row * 8
        original = bytes(self.data[offset:offset + 8])
        if len(original) != 8:
            self.bg_palette_hover_status.set('Cannot adjust saturation: incomplete palette row.')
            return
        converted = bytearray(original)
        for index in range(0, 8, 2):
            value = int.from_bytes(original[index:index + 2], 'little')
            channels = (value & 31, (value >> 5) & 31, (value >> 10) & 31)
            # Scale each channel's distance from weighted gray by 0.8 or 1.2.
            # RGB555 quantization can stall small changes; step by one when
            # needed. Clamp increased saturation to the hardware color range.
            gray = (299 * channels[0] + 587 * channels[1] + 114 * channels[2] + 500) // 1000
            factor = 4 if mode == -1 else 6
            result = tuple(max(0, min(31, (factor * c + (5 - factor) * gray + 2) // 5))
                           for c in channels)
            if result == channels and len(set(channels)) > 1:
                result = tuple(max(0, min(31, c + mode * ((c > gray) - (c < gray))))
                               for c in channels)
            value = (value & 0x8000) | result[0] | (result[1] << 5) | (result[2] << 10)
            converted[index:index + 2] = value.to_bytes(2, 'little')
        if converted == original:
            self.bg_palette_hover_status.set('No change: row is grayscale or at the saturation limit.')
            return
        self._bg_palette_undo.append((offset, original))
        del self._bg_palette_undo[:-64]
        self.data[offset:offset + 8] = converted
        self._refresh_bg_palette_changes()
        label = f'BG {row}' if row < 8 else f'OBJ {row - 2}'
        action = 'Reduced' if mode == -1 else 'Increased'
        self.bg_palette_hover_status.set(
            f'{action} {label} saturation; click again to continue, Escape to finish.')

    def undo_bg_palette_change(self):
        if not getattr(self,'_bg_palette_undo',None):return
        offset,original=self._bg_palette_undo.pop()
        self.data[offset:offset+len(original)]=original
        self._refresh_bg_palette_changes()

    def _refresh_bg_palette_changes(self):
        from windfish.rom.windfish_palette_patch import fix_checksums
        fix_checksums(self.data)
        self._inspector_last_key = None
        self.show_room()
        self.update_bg_palette_editor()

