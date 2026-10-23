"""Sonda do BPM: mostra, a cada ~1 s, todos os valores que parecem BPM / pitch de cada deck.
Uso: python sondas/bpm.py   (Rekordbox aberto, com musica nos decks)  -> mexa o pitch/tempo na controladora durante a leitura.
Mostra TEXTOS (Text) e CAMPOS (Edit) com numero, a posicao e o valor: assim vemos qual deles acompanha o tempo."""
import re, sys, time
from pywinauto import Desktop

NUM = re.compile(r"^[-+]?\d{1,3}\.\d{1,2}$")

def janela():
    return next(w for w in Desktop(backend="uia").windows() if "rekordbox" in (w.window_text() or "").lower() and w.is_visible())

def main(n=25):
    w = janela()
    for i in range(n):
        t0 = time.time()
        linhas = []
        for tipo in ("Text", "Edit"):
            for c in w.descendants(control_type=tipo):
                try:
                    nome = (c.element_info.name or "").strip()
                    r = c.element_info.rectangle
                except Exception:
                    continue
                if NUM.match(nome) and r.top < 700:
                    linhas.append((r.left, r.top, tipo, nome, r.right - r.left, r.bottom - r.top))
        print(f"--- leitura {i + 1} ({round((time.time() - t0) * 1000)} ms)")
        for x, y, tipo, nome, ww, hh in sorted(linhas):
            print(f"{tipo:5} x={x:5} y={y:4} w={ww:3} h={hh:3} nome={nome!r}")
        sys.stdout.flush()
        time.sleep(max(0, 1 - (time.time() - t0)))

if __name__ == "__main__":
    main()
