"""Prevent simultaneous major ROM editors without discarding their work."""


def can_open(owner,requested):
    windows={'Dungeon':getattr(owner,'dungeon_window',None),
             'Text':getattr(owner,'text_editor_window',None),
             'Screen':getattr(owner,'catalog_windows',{}).get('screens')}
    for name,window in windows.items():
        if name==requested or window is None:continue
        if window.winfo_exists():
            window.deiconify();window.lift()
            status=getattr(owner,'status',None)
            if status is not None:status.configure(text=f'Close the {name} Editor before opening the {requested} Editor.')
            return False
    return True
