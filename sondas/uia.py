"""Sonda UIA (v2: inclui posicao x/y/largura/altura de cada texto, para saber de qual deck ele e): le (somente leitura) a arvore de acessibilidade da janela do Rekordbox.

Ideia: o Rekordbox usa a API de acessibilidade do Windows (UIAutomationCore). Se os textos dos decks
(titulo da faixa, artista, BPM, tempo) aparecerem como elementos com nome, da para le-los em tempo real
sem mexer no Rekordbox. Esta sonda so mostra o que existe; nao clica em nada.

Uso (Rekordbox aberto, com uma faixa carregada em cada deck):
    pip install pywinauto
    python sondas/uia.py                 # grava sondas/saida_uia.txt
    python sondas/uia.py --mudancas 20   # depois repete a leitura por 20 s e mostra o que mudou (tocando uma faixa)
"""
import argparse, os, sys, time

try:
    from pywinauto import Desktop
except ImportError:
    sys.exit("Instale antes:  pip install pywinauto")


def acha_janela():
    for w in Desktop(backend="uia").windows():
        try:
            if "rekordbox" in (w.window_text() or "").lower() and w.is_visible():
                return w
        except Exception:
            pass
    return None


def varre(w, limite=6000):
    linhas = []
    try:
        itens = w.descendants()
    except Exception as e:
        sys.exit(f"nao consegui ler a janela: {e}")
    for i, c in enumerate(itens):
        if i >= limite:
            linhas.append("... (cortado)")
            break
        try:
            i_ = c.element_info
            nome = (i_.name or "").strip()
            if not nome:
                continue
            r = i_.rectangle
            linhas.append(f"{i_.control_type or '?':<12} x={r.left:<5} y={r.top:<5} w={r.right - r.left:<5} h={r.bottom - r.top:<4} nome={nome[:90]!r}")
        except Exception:
            continue
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mudancas", type=int, default=0, help="segundos observando o que muda")
    a = ap.parse_args()
    w = acha_janela()
    if not w:
        sys.exit("janela do Rekordbox nao encontrada (aberta e visivel?)")
    print("janela:", w.window_text())
    base = varre(w)
    aqui = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(aqui, "saida_uia.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(base))
    print(f"{len(base)} elementos com nome -> sondas/saida_uia.txt")
    if a.mudancas:
        antes, vistos, fim = set(base), set(), time.time() + a.mudancas
        print("observando mudancas... (toque uma faixa)")
        while time.time() < fim:
            for l in set(varre(w)) - antes - vistos:
                vistos.add(l)
                print("novo/mudou:", l)
            time.sleep(1)


if __name__ == "__main__":
    main()
