from balcao.__main__ import main

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import tkinter as tk
        from tkinter import messagebox
        window=tk.Tk()
        window.withdraw()
        messagebox.showerror("Não foi possível abrir o Balcão",str(error))
        window.destroy()
