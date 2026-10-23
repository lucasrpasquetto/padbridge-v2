"""PadBridge v2.

    python -m padbridge2              # servidor: tablet mostra os decks do Rekordbox (porta 8766)
    python -m padbridge2 --terminal   # so imprime os decks no terminal
    python -m padbridge2 --porta 9000
"""
import argparse, os, time
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


def main():
    ap = argparse.ArgumentParser(prog="padbridge2")
    ap.add_argument("--terminal", action="store_true")
    ap.add_argument("--porta", type=int, default=8766)
    ap.add_argument("--python-db", help="python que tem o pyrekordbox (padrao: o venv do rekordbox-mcp)")
    ap.add_argument("--sem-onda", action="store_true", help="nao busca a waveform no banco")
    a = ap.parse_args()
    try:
        if a.terminal:
            terminal()
        else:
            from .servidor import roda
            bib = None
            if not a.sem_onda:
                from .biblioteca import Biblioteca, python_padrao, AQUI
                py = a.python_db or python_padrao()
                print(f"waveform: banco via {py}" + ("" if os.path.exists(py) else "  (NAO ENCONTRADO: use --python-db ou --sem-onda)"))
                bib = Biblioteca([py, os.path.join(AQUI, "ajudante_db.py")])
            roda(LeitorDecks(), a.porta, bib)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
