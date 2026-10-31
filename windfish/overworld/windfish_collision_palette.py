"""Shared catalog layout for overworld and dungeon collision tools."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk


def build_collision_palette(window,direction_var,length_var,combined_var,names):
    window.title('Collision Selector');window.geometry('735x300')
    window.resizable(False,False)
    window.columnconfigure(0,weight=1);window.rowconfigure(0,weight=1)
    body=ttk.Panedwindow(window,orient='horizontal')
    body.grid(row=0,column=0,sticky='nsew',padx=6,pady=(0,4))
    left=ttk.Frame(body);right=ttk.Frame(body)
    body.add(left,weight=0);body.add(right,weight=1)
    window.after_idle(lambda:body.sashpos(0,245))
    body.bind('<ButtonPress-1>',lambda event:'break')
    items=tk.Listbox(left,font=('Consolas',10),exportselection=False,activestyle='dotbox')
    scroll=ttk.Scrollbar(left,command=items.yview);items.configure(yscrollcommand=scroll.set)
    items.pack(side='left',fill='both',expand=True);scroll.pack(side='left',fill='y')
    for obj,name in enumerate(names):items.insert('end',f'{obj:02X} — {name}')
    right.columnconfigure(0,weight=1);right.rowconfigure(0,weight=1)
    preview=tk.Canvas(right,width=160,height=120,highlightthickness=0)
    preview.grid(row=0,column=0,sticky='nsew')
    availability=tk.StringVar()
    ttk.Label(right,textvariable=availability,wraplength=440,anchor='center').grid(row=1,column=0,sticky='ew',pady=2)
    controls=ttk.Frame(right);controls.grid(row=2,column=0,sticky='ew',pady=3)
    ttk.Label(controls,text='Placement').pack(side='left',padx=4)
    direction=ttk.Combobox(controls,textvariable=direction_var,values=('Single','Horizontal','Vertical'),state='readonly',width=12)
    direction.pack(side='left')
    ttk.Label(controls,text='Length').pack(side='left',padx=(8,4))
    length=ttk.Spinbox(controls,from_=1,to=15,textvariable=length_var,width=4);length.pack(side='left')
    ttk.Checkbutton(right,text='Graphics + collisions (old footprint → floor)',variable=combined_var).grid(row=3,column=0,sticky='w',padx=4,pady=3)
    help_text=tk.StringVar()
    ttk.Label(window,textvariable=help_text,anchor='w').grid(row=1,column=0,sticky='ew',padx=7,pady=(0,5))
    return SimpleNamespace(items=items,preview=preview,availability=availability,direction=direction,length=length,help_text=help_text)


def build_draw_controls(parent,add_collisions,calculate=None):
    """Matching top toolbar for both Direct Draw selectors."""
    bar=ttk.Frame(parent);bar.pack(fill='x',pady=(0,6))
    ttk.Checkbutton(bar,text='Add Collisions',variable=add_collisions).pack(side='left')
    return bar
