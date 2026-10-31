"""Whole-room Edit menu commands with focus-scoped, input-safe shortcuts."""
from tkinter import Menu,messagebox
from windfish.app.windfish_gui_shared import window_shortcut
from windfish.rom import windfish_room_actions as operations

ACTIONS=(('bg','Clear Room BG','B'),('sprites','Clear Room Sprites','S'),
         ('collisions','Clear Room Collisions','C'),('all','Clear All Room Contents','A'),
         ('fill','Fill Room with Selected Tiles','F'))


def run(window,action,dungeon=False):
    root=window.owner if dungeon else window
    if root.document is None:return
    try:
        if dungeon:
            window.finish_draw();context,_=window.render_context(window.room)
            width,height=window.draw_size
            values=window.draw_values or tuple(window.draw_tile.get()+y*16+x for y in range(height) for x in range(width))
            kwargs={'map_id':context,'stamp':(width,height,values),'add_collisions':window.add_collisions.get()}
        else:
            root.end_stroke();sel=root.tile_selection
            stamp=(sel[4],sel[5],sel[6]) if sel else (1,1,(root.selected_tile.get(),))
            from windfish.rendering.windfish_overworld_render import SPECIAL_MAP
            kwargs={'alternate':bool(root.alternate.get() and root.room in SPECIAL_MAP),
                    'stamp':stamp,'add_collisions':root.direct_add_collisions.get()}
        edits=operations.changes(root.data,window.room,action,**kwargs)
        if dungeon:
            window.tile_map_selection=None;window.selected_collision=None
            if action in ('sprites','all'):window.selected_sprite=None
            window.apply_room_changes(edits)
        else:
            for at,old,new in edits:root.history.record(at,old,new,root.room,False);root.data[at]=new
            root.history.commit();root.collision_selected=None
            if action!='fill':root.tile_selection=None
            if action in ('sprites','all'):root.selected_sprite=None
            if edits:root.refresh_changed_rooms([(at,old,new,root.room,kwargs['alternate']) for at,old,new in edits])
            else:root.show_room()
    except (ValueError,IndexError) as exc:messagebox.showerror('Cannot change room',str(exc),parent=window)


def install(window,edit_menu,dungeon=False):
    edit_menu.add_separator()
    for action,label,key in ACTIONS:
        callback=lambda a=action:run(window,a,dungeon)
        edit_menu.add_command(label=label,accelerator=f'Ctrl+Shift+{key}',command=callback)
        bind=window.bind if dungeon else window.bind_all
        bind(f'<Control-Shift-KeyPress-{key}>',window_shortcut(window,callback,focus=not dungeon,ignore_inputs=True))

    from windfish.app.windfish_room_copy import open_copy_dialog
    callback=lambda:open_copy_dialog(window,dungeon)
    edit_menu.add_separator()
    edit_menu.add_command(label='Copy From Room…',accelerator='Ctrl+Shift+R',command=callback)
    bind=window.bind if dungeon else window.bind_all
    bind('<Control-Shift-KeyPress-R>',window_shortcut(window,callback,focus=not dungeon,ignore_inputs=True))
