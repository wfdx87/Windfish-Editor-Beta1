"""Searchable dialogs, optional added IDs, and shared ROM history."""
import tkinter as tk
from tkinter import ttk, messagebox
from hashlib import sha256
from windfish.rom import windfish_dialogue as dialogue


class TextEditor(tk.Toplevel):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.key = None
        self.target = None
        self.entries = ()
        self.visible = []
        self.selected = 0
        self.title('Text Editor')
        self.geometry('960x650')
        self.minsize(760, 520)
        self.transient(owner)
        self.protocol('WM_DELETE_WINDOW', self.close)
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill='both', expand=True)
        self.search = tk.StringVar()
        ttk.Label(frame, text='Search dialogue ID or text').pack(anchor='w')
        search = ttk.Entry(frame, textvariable=self.search)
        search.pack(fill='x', pady=(4, 8))
        self.search.trace_add('write', lambda *_: self.filter())
        body = ttk.Panedwindow(frame, orient='horizontal')
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)
        self.list = tk.Listbox(left, exportselection=False, font=('Consolas', 10), width=34)
        scroll = ttk.Scrollbar(left, command=self.list.yview)
        self.list.configure(yscrollcommand=scroll.set)
        self.list.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.list.bind('<<ListboxSelect>>', self.select)
        self.heading = tk.StringVar()
        self.info = tk.StringVar()
        self.status = tk.StringVar()
        self.count = tk.StringVar()
        ttk.Label(right, textvariable=self.heading, wraplength=560).pack(anchor='w')
        ttk.Label(right, textvariable=self.info, wraplength=560).pack(anchor='w', pady=6)
        self.text = tk.Text(right, wrap='word', width=16, undo=True, font=('Consolas', 12), height=18)
        self.text.pack(fill='y', expand=True, anchor='w')
        self.text.bind('<<Modified>>', self.modified)
        ttk.Label(right, textvariable=self.count).pack(anchor='w', pady=4)
        end_row = ttk.Frame(right)
        end_row.pack(fill='x')
        ttk.Label(end_row, text='Ending').pack(side='left')
        self.ending = tk.StringVar(value='FF — Normal end')
        self.end_combo = ttk.Combobox(end_row, textvariable=self.ending, state='readonly', width=24,
                                     values=('FF — Normal end', 'FE — Existing choice prompt'))
        self.end_combo.pack(side='left', padx=8)
        self.end_combo.bind('<<ComboboxSelected>>', self.update_count)
        actions = ttk.Frame(right)
        actions.pack(fill='x', pady=8)
        self.apply_button = ttk.Button(actions, text='Apply Text', command=self.apply)
        self.apply_button.pack(side='left')
        ttk.Button(actions,text='Add Dialog',command=self.add_dialog).pack(side='left',padx=8)
        self.delete_button=ttk.Button(actions,text='Delete Dialog',command=self.delete_dialog,state='disabled')
        self.delete_button.pack(side='left')
        ttk.Button(actions, text='Reload entry', command=self.reload).pack(side='left', padx=8)
        history_actions=ttk.Frame(right)
        history_actions.pack(fill='x',pady=(0,4))
        ttk.Button(history_actions, text='Undo ROM', command=owner.undo).pack(side='left')
        ttk.Button(history_actions, text='Redo ROM', command=owner.redo).pack(side='left', padx=8)
        ttk.Button(history_actions, text='Character tokens…', command=self.tokens).pack(side='left')
        self.help = tk.StringVar()
        ttk.Label(frame, textvariable=self.help, wraplength=920).pack(anchor='w', pady=(10, 4))
        self.native_help = ('16 cells per line. Words wrap automatically while typing; Apply encodes the same word wrapping. Explicit line breaks pad to the next line. '
                  '##### inserts the player name. Choices use existing scripted branches. '
                  'Original text must fit its current byte length. Added IDs 2B0–3AF share bank 7F and repack automatically.')
        ttk.Label(frame, textvariable=self.status, wraplength=920).pack(anchor='w')
        self.bind('<FocusIn>', lambda event: self.refresh() if event.widget is self else None)
        self.refresh()

    def close(self):
        self.owner.text_editor_window = None
        self.destroy()

    def refresh(self):
        data = self.owner.data
        key = (id(data), sha256(data).digest() if data is not None else None)
        if key == self.key:
            return
        previous_target = self.target
        self.key = key
        self.target = None
        self.entries = ()
        self.apply_button.configure(state='disabled')
        self.delete_button.configure(state='disabled')
        try:
            if data is None:
                raise ValueError('Open a ROM first.')
            self.entries = dialogue.records(data)
            # A fixed 16-character viewport gives native text soft word wrapping
            # without inserting newlines into the draft. The codec remains the
            # authority for token widths and the final encoded dialog text.
            vwf=dialogue.is_vwf(data)
            self.text.configure(wrap='none' if vwf else 'word',width=60 if vwf else 16)
            self.text.pack_configure(fill='both' if vwf else 'y')
            self.title('Text Editor — VWF' if dialogue.is_vwf(data) else 'Text Editor')
            self.help.set('VWF: Enter inserts an FD line break. Glyph widths vary; lines wrap in game at 128 pixels. '
                          'Spacing tokens preserve existing alignment; ##### inserts the player name. '
                          'Choices retain existing scripted branches. Text must fit its current byte length.'
                          if dialogue.is_vwf(data) else self.native_help)
        except (ValueError, IndexError) as exc:
            self.list.delete(0, 'end')
            self.text.delete('1.0', 'end')
            self.heading.set('Text unavailable')
            self.info.set('')
            self.status.set(str(exc))
            return
        self.selected=min(self.selected,max(0,len(self.entries)-1))
        self.filter()
        if (previous_target is not None and previous_target[0] == id(data)
                and previous_target[1] == self.selected
                and self.entries[self.selected] == previous_target[2:]):
            # Unrelated ROM edits must not throw away an unapplied text draft.
            self.target = previous_target
            self.apply_button.configure(state='normal')
            self.delete_button.configure(state='normal' if self.selected>=dialogue.COUNT else 'disabled')
        else:
            self.load_selected()

    def filter(self):
        query = self.search.get().strip().lower()
        self.list.delete(0, 'end')
        self.visible = []
        for index, (at, raw, flag) in enumerate(self.entries):
            text, _ = dialogue.decode(raw, data=self.owner.data)
            flat = text.replace('\n', ' ')
            if query and query not in f'{index:03x} {flat.lower()}':
                continue
            self.visible.append(index)
            self.list.insert('end', f'{index:03X}  {flat[:48]}')
        if self.selected in self.visible:
            row = self.visible.index(self.selected)
            self.list.selection_set(row)
            self.list.see(row)

    def select(self, event=None):
        selection = self.list.curselection()
        if selection:
            self.selected = self.visible[selection[0]]
            self.load_selected()

    def reload(self):
        self.key = None
        self.target = None
        self.refresh()

    def load_selected(self):
        if not self.entries:
            return
        self.delete_button.configure(state='normal' if self.selected>=dialogue.COUNT else 'disabled')
        at, raw, flag = self.entries[self.selected]
        text, ending = dialogue.decode(raw, data=self.owner.data)
        self.target = (id(self.owner.data), self.selected, at, raw, flag)
        aliases = [f'{i:03X}' for i, entry in enumerate(self.entries) if entry[0] == at]
        self.heading.set(f'Dialogue {self.selected:03X} · ROM {at:06X} · Bank {flag if self.selected>=dialogue.COUNT else flag & 0x3F:02X}')
        self.info.set('Shared text IDs (editing changes all): ' + ', '.join(aliases) if len(aliases) > 1 else 'This entry has its own text pointer.')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', text)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.ending.set('FE — Existing choice prompt' if ending == 0xFE else 'FF — Normal end')
        self.apply_button.configure(state='normal')
        self.status.set('Apply changes the ROM buffer. File → Save ROM writes the file. Ctrl+Z inside the text box edits its draft; Undo ROM uses shared history.')
        self.update_count()

    def modified(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.update_count()

    def update_count(self, event=None):
        if self.target is None:
            self.count.set('')
            return
        try:
            raw = dialogue.encode(self.text.get('1.0', 'end-1c'), int(self.ending.get()[:2], 16), data=self.owner.data)
            if self.selected>=dialogue.COUNT:
                from windfish.rom import windfish_dialogue_expansion as ext
                total=sum(len(row[1]) for row in self.entries[dialogue.COUNT:])-len(self.target[3])+len(raw)
                label=f'{len(raw)} bytes · Added text: {total} / {ext.END-ext.POOL} bytes'
            else:
                label = f'{len(raw)} / {len(self.target[3])} bytes including ending'
            if dialogue.is_vwf(self.owner.data):
                widths = dialogue.vwf_codec().line_widths(self.owner.data, raw)
                label += f' · Widest entered line: {max(widths)} / 128 px (names estimated)'
            self.count.set(label)
        except ValueError as exc:
            self.count.set(str(exc))

    def apply(self):
        if self.target is None:
            return
        try:
            identity, index, at, raw, flag = self.target
            root = self.owner
            if id(root.data) != identity or root.document is None or root.document.data is not root.data:
                raise ValueError('The active ROM changed. Reload the selected entry.')
            edits = dialogue.changes(root.data, index, self.text.get('1.0', 'end-1c'),
                                     int(self.ending.get()[:2], 16), expected=(at, raw, flag))
            if edits:
                root.end_stroke()
                for offset, before, after in edits:
                    root.history.record(offset, before, after, root.room, False)
                    root.data[offset] = after
                root.history.commit()
                root.show_room()
                self.refresh()
            self.status.set('Text applied to ROM buffer. File → Save ROM writes the file.')
        except (ValueError, IndexError) as exc:
            messagebox.showwarning('Cannot apply text', str(exc), parent=self)

    def add_dialog(self):
        root=self.owner
        try:
            if root.document is None:raise ValueError('Open a ROM first.')
            edits=dialogue.add_changes(root.data)
            index=len(dialogue.records(root.data))
            root.end_stroke()
            for offset,before,after in edits:
                root.history.record(offset,before,after,root.room,False)
                root.data[offset]=after
            root.history.commit()
            self.selected=index
            self.search.set('')
            self.target=None
            self.refresh()
            self.status.set(f'Added dialog {index:03X}. Enter text and apply, then save the ROM.')
        except (ValueError,IndexError) as exc:
            messagebox.showwarning('Cannot add dialog',str(exc),parent=self)

    def delete_dialog(self):
        if self.target is None:return
        identity,index,at,raw,flag=self.target
        if index<dialogue.COUNT:return
        root=self.owner
        from windfish.rom import windfish_dialogue_expansion as expansion
        last=len(self.entries)-1
        warning=(f'Delete added dialog {index:03X}? Any unapplied text for it will be discarded.\n\n')
        if index<last:
            warning+=(f'Added IDs {index+1:03X}–{last:03X} will shift down by one. '
                      'References in custom scripts and other game code are not updated automatically. '
                      'Update those references before testing your ROM.\n\n')
        else:
            warning+='This ID will become available for the next added dialog.\n\n'
        warning+='You can reverse this with Undo ROM before saving.'
        if not messagebox.askyesno('Delete dialog',warning,parent=self):return
        try:
            if id(root.data)!=identity or root.document is None or root.document.data is not root.data:
                raise ValueError('The active ROM changed. Reload the selected entry.')
            edits=expansion.delete_changes(root.data,index,expected=(at,raw,flag))
            root.end_stroke()
            for offset,before,after in edits:
                root.history.record(offset,before,after,root.room,False)
                root.data[offset]=after
            root.history.commit()
            self.selected=min(index,last-1)
            self.target=None
            self.search.set('')
            self.refresh()
            self.status.set(f'Dialog {index:03X} deleted from ROM buffer. File → Save ROM writes the file.')
        except (ValueError,IndexError) as exc:
            messagebox.showwarning('Cannot delete dialog',str(exc),parent=self)

    def tokens(self):
        table = dialogue.characters(self.owner.data)
        values = [f'{value} = {byte:02X}' for byte, value in table.items() if len(value) > 1]
        extra = ('VWF padding tokens name their byte, not pixel count. Widths: 00–08 = 0–8 px, '
                 '10 = 8 px, other padding bytes = 5 px. Enter inserts FD.'
                 if dialogue.is_vwf(self.owner.data) else 'Native lines contain 16 cells.')
        messagebox.showinfo('Dialogue character tokens', '\n'.join(values) +
                            '\n\nUnknown glyphs use <$XX>. Apostrophes use 5E. '
                            'Select FE/FF separately. ' + extra, parent=self)



def open_text_editor(owner):
    from windfish.app.windfish_editor_guard import can_open
    if not can_open(owner,'Text'):return
    window = getattr(owner, 'text_editor_window', None)
    if window is None or not window.winfo_exists():
        owner.text_editor_window = TextEditor(owner)
    else:
        window.deiconify()
        window.lift()
        window.refresh()
