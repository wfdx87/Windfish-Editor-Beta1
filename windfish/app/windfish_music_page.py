"""Shared native-default music controls for overworld and indoor properties."""
import tkinter as tk
from tkinter import ttk
from windfish.rom import windfish_room_music as music


class MusicPage:
    def __init__(self, owner, tabs, *, indoor=False):
        self.owner = owner
        self.indoor = indoor
        self.target = None
        self.key = None
        page = ttk.Frame(tabs, padding=12)
        tabs.add(page, text='Music')
        self.heading = tk.StringVar()
        self.scope = tk.StringVar()
        self.feedback = tk.StringVar()
        self.value = tk.StringVar()
        ttk.Label(page, textvariable=self.heading, wraplength=420).pack(anchor='w')
        ttk.Label(page, textvariable=self.scope, wraplength=420).pack(anchor='w', pady=8)
        self.combo = ttk.Combobox(page, textvariable=self.value, state='disabled', width=48,
                                 values=[music.label(track) for track in sorted(music.TRACKS)])
        self.combo.pack(fill='x', pady=8)
        self.apply_button = ttk.Button(page, text='Apply music', command=self.apply, state='disabled')
        self.apply_button.pack(anchor='w')
        ttk.Label(page, text='97 named tracks, plus 00 (no new request) and FF (silence). '
                  'Some songs are short item or cutscene sequences rather than looping themes. '
                  'Silence behavior can depend on the active track.', wraplength=420).pack(anchor='w', pady=12)
        ttk.Label(page, text='This edits the default music. Swordless state, power-ups, bosses, '
                  'entities and scripted sequences may override it. Save ROM to keep changes; '
                  'Ctrl+Z / Ctrl+Y undo and redo.', wraplength=420).pack(anchor='w')
        ttk.Label(page, textvariable=self.feedback, wraplength=420).pack(anchor='w', pady=12)

    def context(self):
        owner = self.owner
        context, side = owner.render_context(owner.room) if self.indoor and owner.data is not None else (None, False)
        return owner.data, owner.room, context, side

    def refresh(self):
        self.target = None
        self.combo.configure(state='disabled')
        self.apply_button.configure(state='disabled')
        data, room, context, side = self.context()
        if data is None:
            self.heading.set('Open a ROM first.')
            self.scope.set('')
            self.value.set('')
            return
        try:
            at, track, scope = music.setting(data, room, context, side)
        except (ValueError, IndexError) as exc:
            self.heading.set('Music setting unavailable')
            self.scope.set(str(exc))
            self.value.set('')
            return
        key = (id(data), room, context, side, at, track)
        if key != self.key:
            self.feedback.set('')
            self.value.set(music.label(track))
        self.key = key
        self.target = (id(data), room, context, side, at, track)
        self.heading.set(f'Room {room:02X} default: {music.label(track)} · ROM {at:06X}')
        self.scope.set(scope)
        self.combo.configure(state='readonly')
        self.apply_button.configure(state='normal')

    def apply(self):
        if self.target is None:
            return
        try:
            data, room, context, side = self.context()
            identity, old_room, old_context, old_side, at, old_track = self.target
            if (id(data), room, context, side) != (identity, old_room, old_context, old_side):
                raise ValueError('Selected room changed. Reload Room Properties before applying.')
            track = int(self.value.get().split(' — ', 1)[0], 16)
            edits = music.changes(data, room, track, context, side, expected=(at, old_track))
            if self.indoor:
                self.owner.apply_room_changes(edits)
            elif edits:
                root = self.owner
                if root.document is None or root.document.data is not data:
                    raise ValueError('The active ROM changed. Reload Room Properties.')
                root.end_stroke()
                for offset, before, after in edits:
                    root.history.record(offset, before, after, room, False)
                    data[offset] = after
                root.history.commit()
                root.show_room()
            self.refresh()
            self.feedback.set('Music saved to ROM buffer. File → Save ROM writes the file.')
        except (ValueError, IndexError) as exc:
            self.feedback.set(str(exc))
