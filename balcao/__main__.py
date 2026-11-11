import argparse
import logging
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from waitress import serve

from .web import create_app


def main():
    parser = argparse.ArgumentParser(description="Balcão — caixa local para pequenos mercados")
    parser.add_argument("--data-dir",type=Path)
    parser.add_argument("--port",type=int,default=7470)
    parser.add_argument("--server",action="store_true",help="Não abre o navegador")
    parser.add_argument("--reset-password",action="store_true",help="Redefine o acesso neste computador")
    args = parser.parse_args()
    directory = args.data_dir or Path(os.environ.get("LOCALAPPDATA",Path.home()/".local"/"share"))/"BalcaoPDV"
    directory.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=directory/"balcao.log",level=logging.INFO,encoding="utf-8")
    app = create_app(directory)
    if args.reset_password:
        import getpass
        from werkzeug.security import generate_password_hash
        password = getpass.getpass("Nova senha (mínimo 10 caracteres): ")
        if not 10 <= len(password) <= 200 or getpass.getpass("Repita a senha: ") != password:
            raise ValueError("As senhas precisam conferir e ter de 10 a 200 caracteres.")
        with app.extensions["store"].db(True) as db:
            if not db.execute("SELECT 1 FROM profile").fetchone():
                raise ValueError("Configure o primeiro acesso antes de redefinir a senha.")
            db.execute("UPDATE profile SET password=? WHERE id=1",(generate_password_hash(password),))
        # Invalida também sessões antigas depois do reinício.
        import secrets
        (directory/".session-key").write_text(secrets.token_hex(32),encoding="ascii")
        print("Senha redefinida. Inicie o Balcão novamente.")
        return
    if not 1024 <= args.port <= 65535:
        raise ValueError("Escolha uma porta de 1024 a 65535.")
    url = f"http://127.0.0.1:{args.port}"
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1",args.port))
        except OSError:
            raise ValueError("Essa porta já está em uso. Feche outra instância ou escolha --port diferente.") from None
    if args.server:
        print("Balcão disponível em "+url,flush=True)
        serve(app,host="127.0.0.1",port=args.port,threads=4)
    else:
        import tkinter as tk
        from tkinter import ttk
        thread = threading.Thread(target=lambda:serve(app,host="127.0.0.1",port=args.port,threads=4),daemon=True)
        thread.start()
        window = tk.Tk()
        window.title("Balcão — aplicativo em execução")
        window.geometry("440x210")
        ttk.Label(window,text="Balcão está aberto.",font=("Segoe UI",16)).pack(pady=(25,10))
        ttk.Label(window,text="Mantenha esta janela aberta enquanto usa o caixa.").pack()
        ttk.Button(window,text="Abrir o caixa no navegador",command=lambda:webbrowser.open(url)).pack(pady=18)
        ttk.Label(window,text="Feche esta janela para encerrar o aplicativo.").pack()
        window.after(500,lambda:webbrowser.open(url))
        window.mainloop()


if __name__ == "__main__":
    main()
