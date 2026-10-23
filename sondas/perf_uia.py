"""Mede onde a leitura do Rekordbox gasta tempo (somente leitura).

    python sondas/perf_uia.py

Mostra: tempo para achar a janela, quantos elementos 'Text' existem e quanto custa buscar todos,
e depois, por sub-arvore da janela, quantos 'Text' ha e quanto tempo leva. Grava sondas/saida_perf.txt.
"""
import os, sys, time

try:
    import comtypes
    from pywinauto import Desktop
    from pywinauto.uia_defines import IUIA
except ImportError:
    sys.exit("Instale antes:  pip install pywinauto")

NAME, RECT, CTYPE, CLASS = 30005, 30001, 30003, 30012
TEXT = 50020
CHILDREN, DESCENDANTS = 2, 4
saida = []


def p(*a):
    l = " ".join(str(x) for x in a)
    print(l)
    saida.append(l)


def main():
    t0 = time.time()
    jan = next((w for w in Desktop(backend="uia").windows() if "rekordbox" in (w.window_text() or "").lower() and w.is_visible()), None)
    if jan is None:
        sys.exit("janela do Rekordbox nao encontrada")
    p(f"achar a janela: {(time.time() - t0) * 1000:.0f} ms (feito uma vez so)")
    ia = IUIA().iuia
    cond_texto = ia.CreatePropertyCondition(CTYPE, TEXT)
    cr = ia.CreateCacheRequest()
    for pid in (NAME, RECT, CTYPE, CLASS):
        cr.AddProperty(pid)
    raiz = ia.ElementFromHandle(jan.handle)

    ts = []
    for i in range(3):
        t = time.time()
        arr = raiz.FindAllBuildCache(DESCENDANTS, cond_texto, cr)
        n = arr.Length
        ts.append((time.time() - t) * 1000)
    p(f"todos os Text da janela: {n} elementos; 3 buscas = {', '.join(f'{x:.0f}' for x in ts)} ms")

    t = time.time()
    arr = raiz.FindAllBuildCache(DESCENDANTS, ia.CreateTrueCondition(), cr)
    p(f"TODOS os elementos (qualquer tipo): {arr.Length} em {(time.time() - t) * 1000:.0f} ms")

    contador = [0]

    def desce(el, nivel, max_nivel=4):
        if nivel > max_nivel or contador[0] > 60:
            return
        filhos = el.FindAllBuildCache(CHILDREN, ia.CreateTrueCondition(), cr)
        for i in range(filhos.Length):
            f = filhos.GetElement(i)
            t = time.time()
            n = f.FindAllBuildCache(DESCENDANTS, cond_texto, cr).Length
            ms = (time.time() - t) * 1000
            if n == 0:
                continue
            contador[0] += 1
            try:
                r = f.CachedBoundingRectangle
                geo = f"x={r.left} y={r.top} w={r.right - r.left} h={r.bottom - r.top}"
            except Exception:
                geo = "?"
            p(f"{'  ' * nivel}[{f.CachedClassName or '-'}] {str(f.CachedName or '')[:28]!r} {geo}  Text={n}  {ms:.0f} ms")
            desce(f, nivel + 1, max_nivel)

    p("\nsub-arvores com Text (indentacao = profundidade):")
    desce(raiz, 0)
    aqui = os.path.dirname(os.path.abspath(__file__))
    open(os.path.join(aqui, "saida_perf.txt"), "w", encoding="utf-8").write("\n".join(saida))
    p("\ngravado em sondas/saida_perf.txt")


if __name__ == "__main__":
    main()
