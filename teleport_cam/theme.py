import tkinter as tk
import customtkinter as ctk

COLORS={'shell':'#f4f5f7','panel':'#ffffff','surface':'#e9ecf1','line':'#d9dee7',
        'text':'#202536','muted':'#596174','accent':'#5259d9','accent_hover':'#4248bc',
        'ink':'#ffffff','preview':'#151a24','live':'#28765e','danger':'#9c3b35'}

def apply_theme(root:tk.Tk) -> None:
    ctk.set_appearance_mode('light')
    if isinstance(root,ctk.CTk): root.configure(fg_color=COLORS['shell'])
    else: root.configure(background=COLORS['shell'])
