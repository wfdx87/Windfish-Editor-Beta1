"""Shared display limits for the 16-by-16 room tile selectors."""
MIN_CELL=16
MAX_CELL=32  # Maximum displayed size of each tile.


def cell_size(width,height):
    return max(MIN_CELL,min((width-4)//16,(height-4)//16,MAX_CELL))


def configure_bounds(window,canvas,maximize=False):
    if not window.winfo_exists():return
    # Toplevel requested height can reflect the manually set geometry rather
    # than the packed content (clipping the footer). Measure actual siblings.
    window.update_idletasks()
    parent=canvas.master
    padding=tuple(int(value) for value in parent.cget('padding'))
    vertical=(padding[0]*2 if len(padding)==1 else padding[1]*2 if len(padding)==2 else padding[1]+padding[3] if len(padding)==4 else 0)
    chrome=vertical
    for widget in parent.winfo_children():
        if widget is canvas or widget.winfo_manager()!='pack':continue
        info=widget.pack_info()
        pady=info.get('pady',0)
        if isinstance(pady,(tuple,list)):gap=sum(int(value) for value in pady)
        else:
            values=str(pady).split();gap=sum(map(int,values)) if len(values)>1 else 2*int(pady)
        chrome+=widget.winfo_reqheight()+gap+2*int(info.get('ipady',0))
    minimum=(350,16*MIN_CELL+chrome+4)
    maximum=(16*MAX_CELL+20,16*MAX_CELL+chrome+4)
    window.resizable(True,True)
    window.minsize(*minimum);window.maxsize(*maximum)
    initial=maximum if maximize else minimum
    window.geometry(f'{initial[0]}x{initial[1]}')
