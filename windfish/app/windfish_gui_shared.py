"""Small shared GUI mechanics; editor state and ROM operations stay with callers."""
import tkinter as tk
from PIL import Image, ImageTk

INPUT_WIDGETS = frozenset(('Entry', 'TEntry', 'Text', 'Spinbox', 'TSpinbox', 'TCombobox'))


def window_shortcut(window, callback, *, focus=False, ignore_inputs=False):
    """Dispatch only inside the owning window, preserving child text entry.

    Root bind_all handlers need the current focus; Toplevel bindings use the
    event widget. Keep this distinction so a floating editor never runs the
    main window's commands. A handled editor command stops Tk propagation.
    """
    def dispatch(event):
        widget = getattr(event, 'widget', None)
        try:
            if ignore_inputs and widget is not None and widget.winfo_class() in INPUT_WIDGETS:
                return None
            source = window.focus_get() if focus else widget
            if source is None or source.winfo_toplevel() is not window:
                return None
        except tk.TclError:
            return None
        callback()
        return 'break'
    return dispatch


def bind_overlay_shortcuts(window, variables, redraw, *, global_bind=False):
    """Bind overlays in menu order (1–4) without capturing input-field digits."""
    bind = window.bind_all if global_bind else window.bind
    for key, variable in enumerate(variables, 1):
        def toggle(value=variable):
            value.set(not value.get())
            redraw()
        bind(f'<KeyPress-{key}>', window_shortcut(
            window, toggle, focus=global_bind, ignore_inputs=True))


def add_overlay_menu(menu, variables, redraw, *, borders_label):
    """Build shared overlay entries, retaining each editor's border wording."""
    indices = []
    labels = (borders_label, 'Show Sprites', 'Show Sprite IDs', 'Show Collisions')
    for key, (label, variable) in enumerate(zip(labels, variables), 1):
        menu.add_checkbutton(label=label, accelerator=str(key), variable=variable, command=redraw)
        indices.append(menu.index('end'))
    return tuple(indices)


def tile_canvas(parent, background):
    canvas = tk.Canvas(parent, width=260, height=260, highlightthickness=0, background=background)
    canvas.pack(fill='both', expand=True)
    return canvas


def tile_cell(x, y, cell):
    """Clamp pointer coordinates to the 16-by-16 selector sheet."""
    return max(0, min(15, x // cell)), max(0, min(15, y // cell))


def tile_rectangle(start, end):
    left, right = sorted((start[0], end[0]))
    top, bottom = sorted((start[1], end[1]))
    return left, top, right, bottom


def tile_values(rectangle):
    left, top, right, bottom = rectangle
    return tuple(y * 16 + x for y in range(top, bottom + 1) for x in range(left, right + 1))


def draw_tile_sheet(canvas, sheet, cell):
    """Return the PhotoImage so the caller retains its Tk lifetime reference."""
    photo = ImageTk.PhotoImage(sheet.resize((cell * 16, cell * 16), Image.Resampling.NEAREST))
    canvas.delete('all')
    canvas.create_image(0, 0, image=photo, anchor='nw')
    return photo
