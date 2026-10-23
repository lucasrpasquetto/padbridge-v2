"""PadBridge v2.

    python -m padbridge2              # servidor: tablet mostra os decks do Rekordbox (porta 8766)
    python -m padbridge2 --terminal   # so imprime os decks no terminal
    python -m padbridge2 --porta 9000
"""
import argparse, os, sys, time
from .leitor_decks import LeitorDecks


def fmt(d):
    if not d["carregada"]:
        return f"DECK {d['n']}: (vazio)"
    return (f"DECK {d['n']}: {d['titulo']} | {d['artista'] or '-'} | {d['bpm'] or '-'} BPM | {d['tonalidade'] or '-'} | "
            f"restante {d['restante'] or '-'} | decorrido {d['decorrido'] or '-'}")


def terminal():
    leitor, ultimo = LeitorDecks(), None
    print("lendo os decks (Ctrl+C para sair)...")
    while True:
        t0 = time.time()
        decks = leitor.ler()
        ms = (time.time() - t0) * 1000
        chave = [(d["carregada"], d["titulo"], d["artista"], d["bpm"], d["tonalidade"]) for d in decks]
        if chave != ultimo:
            ultimo = chave
            print(f"--- leitura em {ms:.0f} ms ({leitor.modo})")
            for d in decks:
                print(fmt(d))
        time.sleep(0.3)


def testa_banco():
    from .ajudante_db import BackendPyrekordbox
    try:
        n = len(list(BackendPyrekordbox().db.get_content()))
        msg = f"OK: banco do Rekordbox aberto, {n} faixas."
    except Exception as e:
        msg = (f"FALHOU: {type(e).__name__}: {e}\n\nAbra o Rekordbox ao menos uma vez neste computador. "
               "Se persistir, instale o Python 3.12 e rode: python -m pyrekordbox download-key")
    print(msg)
    from .bandeja import aviso
    aviso(msg)                                  # o exe nao tem console: mostra numa janela


def prepara_exe():
    """Exe sem janela: sem console o print quebraria; log e arquivos ficam ao lado do programa."""
    if not getattr(sys, "frozen", False):
        return
    os.chdir(os.path.dirname(sys.executable))
    if sys.stdout is None:
        sys.stdout = sys.stderr = open(os.devnull, "w")


def main():
    prepara_exe()
    ap = argparse.ArgumentParser(prog="padbridge2")
    ap.add_argument("--terminal", action="store_true")
    ap.add_argument("--porta", type=int, default=8766)
    ap.add_argument("--python-db", help="python que tem o pyrekordbox (padrao: o venv do rekordbox-mcp)")
    ap.add_argument("--sem-onda", action="store_true", help="nao busca a waveform no banco")
    ap.add_argument("--console", action="store_true", help="roda no terminal, sem icone na bandeja")
    ap.add_argument("--ajudante", action="store_true", help="(interno) roda como ajudante de banco, por stdin/stdout")
    ap.add_argument("--testa-banco", action="store_true", help="abre o banco do Rekordbox, mostra o resultado e sai")
    a, resto = ap.parse_known_args()      # o resto (--wifi, --debug, --http...) e do v1
    try:
        if a.ajudante:
            from . import ajudante_db
            if sys.stdin is None or sys.stdout is None or sys.stdout.name == os.devnull:
                sys.stdin = open(0, encoding="utf-8", closefd=False)
                sys.stdout = open(1, "w", encoding="utf-8", buffering=1, closefd=False)
            ajudante_db.main()
        elif a.testa_banco:
            testa_banco()
        elif a.terminal:
            terminal()
        else:
            from .servidor import roda
            bib = None
            if not a.sem_onda:
                from .biblioteca import Biblioteca, python_padrao, AQUI
                if getattr(sys, "frozen", False) and not a.python_db:
                    cmd = [sys.executable, "--ajudante"]      # o proprio exe faz o papel de ajudante
                    print("waveform: banco via o proprio programa")
                else:
                    py = a.python_db or python_padrao()
                    print(f"waveform: banco via {py}" + ("" if os.path.exists(py) else "  (NAO ENCONTRADO: use --python-db ou --sem-onda)"))
                    cmd = [py, os.path.join(AQUI, "ajudante_db.py")]
                bib = Biblioteca(cmd)
            if a.console or os.name != "nt":
                roda(LeitorDecks(), a.porta, bib)
            else:
                from .bandeja import roda_unico, ja_esta_rodando, aviso
                if ja_esta_rodando():
                    aviso("O PadBridge ja esta aberto (veja o icone ao lado do relogio).")
                    return
                roda_unico(LeitorDecks(), a.porta, bib, resto)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
