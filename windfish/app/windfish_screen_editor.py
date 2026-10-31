"""Screen Editor: common screen/tile-sheet tabs, with shared ROM undo."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from PIL import Image,ImageTk,ImageOps
from windfish.rom import windfish_screen_maps as maps
from windfish.rendering import windfish_title as title
from windfish.rendering.windfish_screen_render import segments,raw_gfx,tile_image
from windfish.app.windfish_screen_buffer import TabBuffer


class ScreenTab(ttk.Frame):
    def __init__(self,parent,owner,kind):
        super().__init__(parent,padding=12);self.owner=owner;self.kind=kind;self.stamp=(1,1,((0x80,0),),False);self.anchor=None;self.selection=None;self.last=None;self._tile_cache={};self._gfx_signature=None;self._sheet_image=None;self._dx_layer=None
        left=ttk.Frame(self);left.grid(row=0,column=0,sticky='nw',padx=(0,16))
        self.screen=tk.Canvas(left,width=480,height=432,highlightthickness=0);self.screen.pack()
        ttk.Label(left,text='Left-drag selects tiles. Right-click/drag paints.\nChanges use ROM Undo/Redo; Save ROM writes the file.',wraplength=480).pack(anchor='w',pady=6)
        right=ttk.Frame(self);right.grid(row=0,column=1,sticky='nw')
        ttk.Label(right,text='8×8 GFX · VRAM tile IDs').pack(anchor='w')
        self.sheet=tk.Canvas(right,width=256,height=256,highlightthickness=1);self.sheet.pack(pady=6)
        self.palette=tk.StringVar(value='0');self.dx=tk.BooleanVar(value=True)
        if kind=='title':ttk.Checkbutton(right,text='Show DX sprites',variable=self.dx,command=self.refresh).pack(anchor='w',pady=6)
        ttk.Label(right,text='GFX imports can affect other screens using the same graphics.\nGray tiles are not loaded by this screen.',wraplength=320).pack(anchor='w',pady=8)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status,wraplength=850).grid(row=1,column=0,columnspan=2,sticky='w',pady=8)
        for canvas,source in ((self.screen,'screen'),(self.sheet,'sheet')):
            canvas.bind('<ButtonPress-1>',lambda e,s=source:self.select(e,s,True))
            canvas.bind('<B1-Motion>',lambda e,s=source:self.select(e,s,False))
        self.screen.bind('<ButtonPress-3>',self.paint_start);self.screen.bind('<B3-Motion>',self.paint)
        self.screen.bind('<ButtonRelease-3>',self.paint_end)
        self.refresh()

    def change_palette(self,event=None):
        w,h,cells,full=self.stamp;self.stamp=(w,h,tuple((t,(a&0xF8)|int(self.palette.get())) for t,a in cells),True);self.refresh()

    def select(self,event,source,start):
        size=24 if source=='screen' else 16;limit=(20,18) if source=='screen' else (16,16)
        x=event.x//size;y=event.y//size
        if not 0<=x<limit[0] or not 0<=y<limit[1]:return
        if start:self.anchor=(source,x,y)
        if self.anchor is None or self.anchor[0]!=source:return
        _,ax,ay=self.anchor;x0,x1=sorted((x,ax));y0,y1=sorted((y,ay));cells=[]
        grid=maps.cells(self.owner.data,self.kind)
        valid={i for first,_,count in segments(self.kind) for i in range(first,first+count//16)}
        for cy in range(y0,y1+1):
            for cx in range(x0,x1+1):
                cell=grid[cy*20+cx] if source=='screen' else (cy*16+cx,5 if self.kind=='save' else int(self.palette.get()))
                if cell[0] not in valid:self.status.set('Selection contains graphics not loaded by this screen.');return
                cells.append(cell)
        self.stamp=(x1-x0+1,y1-y0+1,tuple(cells),source=='screen')
        self.selection=(source,x0,y0,x1,y1);self.refresh()
        self.status.set(f'{len(cells)} tile(s) selected · first ID {cells[0][0]:02X}')

    def paint_start(self,event):self.last=None;self.paint(event)

    def paint_end(self,event=None):
        self.owner.history.commit();self.last=None

    def paint(self,event):
        x=event.x//24;y=event.y//24
        if not 0<=x<20 or not 0<=y<18 or self.last==(x,y):return
        self.last=(x,y)
        try:self.commit(maps.stamp_changes(self.owner.data,self.kind,x,y,self.stamp))
        except (ValueError,IndexError) as exc:self.status.set(str(exc))

    def commit(self,edits):
        for at,old,new in edits:self.owner.history.record(at,old,new,self.owner.room,False);self.owner.data[at]=new
        self.refresh()
        self.status.set('Updated ROM buffer. Undo/Redo available.')

    def refresh(self,event=None):
        if self.owner.data is None:return
        try:
            data=self.owner.data;grid=maps.cells(data,self.kind);image=Image.new('RGB',(160,144))
            palat=maps.SPECS[self.kind][2]
            signature=(raw_gfx(data,self.kind),bytes(data[palat:palat+64]),self.palette.get())
            if signature!=self._gfx_signature:
                self._gfx_signature=signature;self._tile_cache={};self._sheet_image=None
            cache=self._tile_cache
            for pos,cell in enumerate(grid):
                if cell not in cache:cache[cell]=tile_image(data,self.kind,*cell)
                image.paste(cache[cell],(pos%20*8,pos//20*8))
            if self.kind=='title' and self.dx.get():
                if self._dx_layer is None:
                    base=title.render_complete(data,False);overlay=title.render_complete(data,True)
                    self._dx_layer=tuple((x,y,overlay.getpixel((x,y))) for y in range(144) for x in range(160) if base.getpixel((x,y))!=overlay.getpixel((x,y)))
                for x,y,color in self._dx_layer:image.putpixel((x,y),color)
            if self._sheet_image is None:
                sheet=Image.new('RGB',(128,128))
                for i in range(256):
                    key=(i,int(self.palette.get()) if self.kind!='save' else 5)
                    if key not in cache:cache[key]=tile_image(data,self.kind,*key)
                    sheet.paste(cache[key],(i%16*8,i//16*8))
                self._sheet_image=sheet
            sheet=self._sheet_image.copy()
            if self.selection:
                source,x0,y0,x1,y1=self.selection;target=image if source=='screen' else sheet
                box=(x0*8,y0*8,(x1+1)*8,(y1+1)*8);target.paste(ImageOps.invert(target.crop(box)),box[:2])
            for canvas,im,scale in ((self.screen,image,3),(self.sheet,sheet,2)):
                canvas.photo=ImageTk.PhotoImage(im.resize((im.width*scale,im.height*scale),Image.Resampling.NEAREST));canvas.delete('all');canvas.create_image(0,0,anchor='nw',image=canvas.photo)
        except (ValueError,IndexError) as exc:self.status.set(str(exc))



def open_screen_editor(owner,tab=0):
    from windfish.app.windfish_editor_guard import can_open
    if not can_open(owner,'Screen'):return
    if owner.data is None:return
    old=owner.catalog_windows.get('screens')
    if old is not None and old.winfo_exists():old.deiconify();old.lift();old.notebook.select(tab);return
    win=tk.Toplevel(owner);win.title('Screen Editor');win.transient(owner);win.resizable(False,False)
    owner.catalog_windows['screens']=win;book=ttk.Notebook(win);win.notebook=book;book.pack(fill='both',expand=True)
    definitions=(('Title Screen','title'),('File Select','file'),('Copy File','copy'),('Erase File','erase'),('Save Menu','save'),('Overworld Map','world'),('Photo Album','photo'))
    holders=[];loaded={};active=[None]
    for label,kind in definitions:
        frame=ttk.Frame(book);book.add(frame,text=label);holders.append(frame)
    bar=ttk.Frame(win,padding=(12,6,12,6));bar.pack(fill='x')
    message=ttk.Frame(win,padding=(12,0,12,8));message.pack(fill='x')
    status=tk.StringVar(value='Edits are staged per tab. Save writes the active tab to the ROM.')
    def refresh_frame(frame):
        if isinstance(frame,ScreenTab):frame.refresh()
        elif hasattr(frame,'refresh'):frame.refresh(force=True)
        else:frame.refresh_photo()
    def switch(event=None):
        previous=loaded.get(active[0])
        if previous:
            frame,buffer=previous
            if hasattr(frame,'end_paint'):frame.end_paint()
            buffer.end_stroke()
        index=book.index(book.select());active[0]=index
        if index not in loaded:
            buffer=TabBuffer(owner);kind=definitions[index][1];holder=holders[index]
            if kind=='world':
                from windfish.app.windfish_world_map_editor import WorldMapEditor
                frame=WorldMapEditor(buffer,parent=holder)
            elif kind=='photo':
                from windfish.app.windfish_picture_viewer import open_picture_viewer
                frame=open_picture_viewer(buffer,parent=holder)
            else:frame=ScreenTab(holder,buffer,kind)
            frame.pack(fill='both',expand=True);loaded[index]=(frame,buffer)
            buffer.notify=lambda f=frame:refresh_frame(f)
        else:refresh_frame(loaded[index][0])
        update_toolbar()
    def save():
        if active[0] is None:return
        frame,buffer=loaded[active[0]]
        if definitions[active[0]][1]=='photo':return
        if hasattr(frame,'end_paint'):frame.end_paint()
        try:
            if isinstance(frame,ScreenTab) and frame.kind=='title':
                cell=maps.cells(buffer.data,'title')[0]
                frame.commit(maps.stamp_changes(buffer.data,'title',0,0,(1,1,(cell,),True)))
            buffer.save();status.set(f'Saved {definitions[active[0]][0]} to {owner.document.path.name}. Other tabs remain staged.')
        except (ValueError,OSError) as exc:messagebox.showerror('Cannot save tab',str(exc),parent=win)
    def current():return loaded[active[0]]
    def finish(frame,buffer):
        if hasattr(frame,'end_paint'):frame.end_paint()
        buffer.end_stroke()
    def undo_redo(redo=False):
        frame,buffer=current();finish(frame,buffer)
        (buffer.redo if redo else buffer.undo)();update_toolbar()
    def transfer(action):
        from windfish.app.windfish_screen_transfer import export_payload,import_changes
        frame,buffer=current();kind=definitions[active[0]][1];finish(frame,buffer)
        importing=action.startswith('insert') or action.startswith('import')
        tilemap=action.endswith('tilemap')
        if kind=='photo' and importing:return
        ext='.tilemap' if tilemap else '.bin'
        kwargs=dict(parent=win,title=action.replace('_',' ').title(),filetypes=[('Raw tilemap' if tilemap else 'GB 2bpp GFX','*'+ext),('All files','*.*')])
        path=filedialog.askopenfilename(**kwargs) if importing else filedialog.asksaveasfilename(**kwargs,initialfile=kind+('-map' if tilemap else '-gfx')+ext,defaultextension=ext)
        if not path:return
        try:
            if importing:
                edits=import_changes(buffer.data,kind,frame,Path(path).read_bytes(),tilemap)
                for at,old,new in edits:buffer.history.record(at,old,new,buffer.room,False);buffer.data[at]=new
                buffer.history.commit();refresh_frame(frame);status.set('Imported into the active tab. Save Current Tab writes it to the ROM.')
            else:
                if Path(path).resolve()==Path(owner.document.path).resolve():raise ValueError('Choose a filename other than the ROM.')
                raw=export_payload(buffer.data,kind,frame,tilemap);Path(path).write_bytes(raw)
                status.set(f'Exported {len(raw)} bytes.')
            update_toolbar()
        except (OSError,ValueError,IndexError) as exc:messagebox.showerror('Screen transfer',str(exc),parent=win)
    buttons={}
    for label,callback in (('Save Current Tab',save),('Undo',lambda:undo_redo()),('Redo',lambda:undo_redo(True)),('Extract GFX',lambda:transfer('extract_gfx')),('Insert GFX',lambda:transfer('insert_gfx')),('Export Tilemap',lambda:transfer('export_tilemap')),('Import Tilemap',lambda:transfer('import_tilemap'))):
        button=ttk.Button(bar,text=label,command=callback);button.pack(side='left',padx=(0,5));buttons[label]=button
    ttk.Label(bar,text='Palette').pack(side='left',padx=(8,4))
    palette_var=tk.StringVar(value='0')
    palette_combo=ttk.Combobox(bar,textvariable=palette_var,values=tuple(range(8)),state='readonly',width=7);palette_combo.pack(side='left')
    def palette_changed(event=None):
        frame,buffer=current();frame.palette.set(palette_var.get())
        if isinstance(frame,ScreenTab):frame.change_palette()
        else:frame.change_brush()
    palette_combo.bind('<<ComboboxSelected>>',palette_changed)
    def update_toolbar():
        frame,buffer=current();kind=definitions[active[0]][1];readonly=kind=='photo'
        for label in ('Save Current Tab','Insert GFX','Import Tilemap'):buttons[label].configure(state='disabled' if readonly else 'normal')
        buttons['Undo'].configure(state='normal' if not readonly and buffer.history.can_undo else 'disabled')
        buttons['Redo'].configure(state='normal' if not readonly and buffer.history.can_redo else 'disabled')
        palette_combo.configure(state='disabled' if kind in ('save','photo') else 'readonly')
        palette=getattr(frame,'palette',None)
        palette_var.set('Default' if kind in ('save','photo') else palette.get() if palette is not None else '0')
    ttk.Label(message,textvariable=status,wraplength=1020).pack(anchor='w')
    book.bind('<<NotebookTabChanged>>',switch)
    win.bind('<ButtonRelease-1>',lambda e:win.after_idle(update_toolbar),add='+')
    win.bind('<ButtonRelease-3>',lambda e:win.after_idle(update_toolbar),add='+')
    # Root notifications do not rebuild all staged tabs. They remain isolated;
    # saving checks byte conflicts against their original snapshot.
    def close():owner.catalog_windows.pop('screens',None);win.destroy()
    win.protocol('WM_DELETE_WINDOW',close)
    def history(event,redo=False):
        if event.widget.winfo_class() in ('Entry','TEntry','Text','Spinbox','TSpinbox','TCombobox'):return
        frame,buffer=loaded[active[0]]
        if hasattr(frame,'end_paint'):frame.end_paint()
        if definitions[active[0]][1]!='photo':(buffer.redo if redo else buffer.undo)()
        update_toolbar();return 'break'
    win.bind('<Control-z>',history);win.bind('<Control-y>',lambda e:history(e,True))
    win.bind('<Control-s>',lambda e:(save(),'break')[-1])
    book.select(tab)
    win.after_idle(lambda:switch() if active[0] is None else None)
