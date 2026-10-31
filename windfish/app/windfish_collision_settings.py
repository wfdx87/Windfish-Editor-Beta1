"""Session-wide filters for automatic collision generation, separate by world."""
import tkinter as tk
from tkinter import ttk


def _owner(editor):
    return getattr(editor, 'owner', editor)


def filters(editor):
    owner = _owner(editor)
    if not hasattr(owner, '_collision_recalculate_filters'):
        owner._collision_recalculate_filters = {
            kind: [tk.BooleanVar(master=owner, value=True) for _ in range(254)]
            for kind in ('overworld', 'dungeon')}
    return owner._collision_recalculate_filters


def allowed_types(editor, kind):
    return {i for i, flag in enumerate(filters(editor)[kind]) if flag.get()}


def install_menu(editor, menu):
    settings = tk.Menu(menu, tearoff=False)
    settings.add_command(label='Collision Settings…', command=lambda: open_window(editor))
    menu.add_cascade(label='Settings', menu=settings)


def open_window(editor):
    owner = _owner(editor)
    previous = getattr(owner, '_collision_settings_window', None)
    if previous is not None and previous.winfo_exists():
        previous.lift()
        return
    win = tk.Toplevel(owner)
    owner._collision_settings_window = win
    win.title('Collision Settings')
    win.geometry('820x600')
    win.resizable(False, False)
    win.transient(editor)
    ttk.Label(win, text='Recalculate Collisions: checked IDs may be generated. '
              'Page 1 placements, dungeon templates, and existing special registrations are preserved.',
              wraplength=860).pack(fill='x', padx=12, pady=10)
    tabs = ttk.Notebook(win)
    tabs.pack(fill='both', expand=True, padx=12, pady=(0, 12))
    for kind, title in (('overworld', 'Overworld'), ('dungeon', 'Dungeon / Interior')):
        page = ttk.Frame(tabs)
        tabs.add(page, text=title)
        flags = filters(editor)[kind]
        buttons = ttk.Frame(page)
        buttons.pack(fill='x', pady=6)
        for label, value in (('Check All', True), ('Uncheck All', False)):
            ttk.Button(buttons, text=label,
                       command=lambda fs=flags, v=value: [f.set(v) for f in fs]).pack(side='left', padx=4)
        canvas = tk.Canvas(page, highlightthickness=0)
        scroll = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = ttk.Frame(canvas)
        item = canvas.create_window(0, 0, window=body, anchor='nw')
        body.bind('<Configure>', lambda event, c=canvas: c.configure(scrollregion=c.bbox('all')))
        canvas.bind('<Configure>', lambda event, c=canvas, i=item: c.itemconfigure(i, width=event.width))
        def wheel(event, c=canvas):
            c.yview_scroll(-1 if event.delta > 0 else 1, 'units')
            return 'break'
        canvas.bind('<MouseWheel>', wheel)
        for i, flag in enumerate(flags):
            check = ttk.Checkbutton(body, text=f'{i:02X}', variable=flag)
            check.grid(row=i//16, column=i%16, sticky='w', padx=3, pady=3)
            check.bind('<MouseWheel>', wheel)
        # FE/FF terminate streams and cannot be collision placements.
        for i in (0xFE, 0xFF):
            ttk.Checkbutton(body, text=f'{i:02X}', state='disabled').grid(
                row=i//16, column=i%16, sticky='w', padx=3, pady=3)
        for col in range(16):
            body.columnconfigure(col, weight=1)
    if hasattr(editor, 'owner'):
        tabs.select(1)
