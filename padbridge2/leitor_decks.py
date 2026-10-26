"""Leitor dos decks do Rekordbox pela acessibilidade do Windows (UI Automation). Somente leitura.

`interpreta()` e uma funcao pura (recebe textos com posicao) e e testada com um dump real.
`coleta()` e `LeitorDecks` usam pywinauto e so funcionam no Windows com o Rekordbox aberto.
"""
import ast
import re
import time
from collections import namedtuple

Texto = namedtuple("Texto", "nome x y w h tipo", defaults=("Text",))   # tipo: "Text" ou "Edit" (campo do BPM)

RE_BPM = re.compile(r"^\d{2,3}\.\d{2}$")
RE_CHAVE = re.compile(r"^(\d{1,2}[AB]|[A-G][#b]?m?)$")
RE_TEMPO = re.compile(r"^-?\d{2,3}:\d{2}$")
RE_FRACAO = re.compile(r"^\.\d$")
NAO_CARREGADA = {"not loaded.", "not loaded"}


# Todas as medidas abaixo foram tiradas com a tela em 100% (o numero do deck mede 12 px de altura). Em outra escala do Windows
# (125%, 150%...) ou outro tamanho de janela, tudo cresce junto: `_k(ancora)` e a razao (altura medida / 12) e escala os limites.
def _k(a):
    return min(3.0, max(0.7, a.h / 12.0))


def _ancoras(textos):
    """Numero do deck (1..4): texto pequeno ('1', quadrado) com um titulo grande logo a direita, na mesma linha."""
    r = []
    for t in textos:
        if t.nome in ("1", "2", "3", "4") and t.w <= 2 * t.h and 8 <= t.h <= 36:
            k = _k(t)
            tit = [u for u in textos if u.h >= 1.3 * t.h and u.w >= 200 * k and t.x + 20 * k <= u.x <= t.x + 140 * k and abs(u.y - t.y) <= 8 * k]
            if tit:
                r.append(t)
    return sorted(r, key=lambda a: a.x)


def interpreta(textos):
    """Devolve uma lista com um dict por deck: n, carregada, titulo, artista, bpm, tonalidade, restante, decorrido."""
    ancoras = _ancoras(textos)
    decks = []
    for i, a in enumerate(ancoras):
        k = _k(a)
        x_fim = ancoras[i + 1].x if i + 1 < len(ancoras) else a.x + 1200 * k
        faixa = [t for t in textos if a.x <= t.x < x_fim and a.y - 6 * k <= t.y <= a.y + 40 * k]
        d = dict(n=int(a.nome), carregada=False, titulo=None, artista=None, bpm=None, bpm_faixa=None, tonalidade=None,
                 restante=None, decorrido=None)
        grandes = [t for t in faixa if t.h >= 1.3 * a.h and t.w >= 200 * k]
        if grandes:
            titulo = grandes[0].nome.strip()
            if titulo.lower() not in NAO_CARREGADA and titulo:
                d["carregada"], d["titulo"] = True, titulo
        for t in sorted((t for t in faixa if t not in grandes), key=lambda t: (t.y // 8, t.x)):
            n = t.nome.strip()
            if RE_TEMPO.match(n):
                frac = next((f.nome for f in faixa if RE_FRACAO.match(f.nome) and abs(f.x - (t.x + t.w)) <= 8 * k and abs(f.y - t.y) <= 4 * k), "")
                chave = "restante" if n.startswith("-") else "decorrido"
                if d[chave] is None:
                    d[chave] = n + frac
            elif RE_BPM.match(n) and d["bpm"] is None and t.h <= 1.2 * a.h:
                d["bpm"] = d["bpm_faixa"] = float(n)      # o texto do cabecalho e o BPM da FAIXA (nao muda com o pitch)
            elif RE_CHAVE.match(n) and d["tonalidade"] is None and t.h <= 1.2 * a.h and (d["bpm"] is not None or d["artista"] is not None):
                d["tonalidade"] = n
            elif d["artista"] is None and t.h <= 1.2 * a.h and t.y >= a.y + 15 * k and d["bpm"] is None and not RE_TEMPO.match(n) and not RE_FRACAO.match(n):
                d["artista"] = n
        # BPM ao vivo (com o pitch): campo "Edit" do painel de tempo do deck, mais abaixo; medido: muda quando se mexe no pitch
        vivo = [t for t in textos if t.tipo == "Edit" and RE_BPM.match(t.nome.strip()) and a.x <= t.x < x_fim and a.y + 100 * k <= t.y <= a.y + 320 * k]
        if vivo and d["bpm"] is not None:
            d["bpm"] = float(vivo[0].nome.strip())
        if not d["carregada"]:
            d.update(artista=None, bpm=None, bpm_faixa=None, tonalidade=None)
        decks.append(d)
    return decks


def le_dump(caminho):
    """Le um arquivo gerado por sondas/uia.py (so linhas 'Text')."""
    padrao = re.compile(r"^(Text|Edit)\s+x=(-?\d+)\s+y=(-?\d+)\s+w=(\d+)\s+h=(\d+)\s+nome=(.*)$")
    out = []
    for l in open(caminho, encoding="utf-8"):
        m = padrao.match(l.rstrip("\n"))
        if m:
            nome = m.group(6)
            out.append(Texto(ast.literal_eval(nome), *(int(m.group(i)) for i in (2, 3, 4, 5)), m.group(1)))   # nome vem como repr() de str
    return out


# ---- parte que depende do Windows -------------------------------------------------------
UIA_NAME, UIA_RECT, UIA_CONTROLTYPE, UIA_TEXT_TYPE, UIA_EDIT_TYPE, ESCOPO_DESCENDENTES = 30005, 30001, 30003, 50020, 50004, 4


def itens_de_array(arr):
    """Converte o IUIAutomationElementArray (Name e BoundingRectangle em cache) em lista de (elemento, Texto)."""
    out = []
    for i in range(arr.Length):
        el = arr.GetElement(i)
        try:
            n = (el.CachedName or "").strip()
            if n:
                r = el.CachedBoundingRectangle
                try:
                    tipo = "Edit" if el.CachedControlType == UIA_EDIT_TYPE else "Text"
                except Exception:
                    tipo = "Text"
                out.append((el, Texto(n, r.left, r.top, r.right - r.left, r.bottom - r.top, tipo)))
        except Exception:
            pass
    return out


def textos_de_array(arr):
    return [t for _, t in itens_de_array(arr)]


def so_faixa_dos_decks(itens):
    """Fica so com os textos que importam (as faixas horizontais dos decks); o resto da janela e ignorado."""
    textos = [t for _, t in itens]
    ancoras = _ancoras(textos)
    if not ancoras:
        return []
    return [(el, t) for el, t in itens
            if any((a.y - 6 * _k(a) <= t.y <= a.y + 40 * _k(a) or (t.tipo == "Edit" and a.y + 100 * _k(a) <= t.y <= a.y + 320 * _k(a))) and t.x >= a.x for a in ancoras)]


def _acha_janela_lenta():
    from pywinauto import Desktop
    janela = next((w for w in Desktop(backend="uia").windows() if "rekordbox" in (w.window_text() or "").lower() and w.is_visible()), None)
    if janela is None:
        raise RuntimeError("janela do Rekordbox nao encontrada")
    return janela


def coleta():
    """Caminho lento (reserva): percorre a arvore pelo pywinauto, elemento por elemento."""
    out = []
    for c in _acha_janela_lenta().descendants(control_type="Text"):
        try:
            i = c.element_info
            n = (i.name or "").strip()
            if n:
                r = i.rectangle
                out.append(Texto(n, r.left, r.top, r.right - r.left, r.bottom - r.top))
        except Exception:
            pass
    return out


class LeitorDecks:
    """Leitura em 2 velocidades (o provedor de acessibilidade do Rekordbox gasta ~600 ms para varrer a janela):
      - VARREDURA (lenta): acha os textos da janela e guarda so as referencias dos que estao nas faixas dos decks;
      - LEITURA (rapida): relê o nome so dessas referencias (dezenas de ms).
    Faz nova varredura quando: a faixa/estado de carga de algum deck muda, uma referencia falha, ou a cada `revarre_s`.
    Tudo que usa COM e criado na PRIMEIRA leitura, dentro da thread que le."""

    def __init__(self, revarre_s=30, varredor=None, relogio=time.time):
        self.modo = "nao iniciado"
        self.revarre_s, self._relogio = revarre_s, relogio
        self._varredor = varredor            # injetavel para teste: funcao() -> lista de (elemento, Texto)
        self._itens = None
        self._t_varredura = 0
        self._sig = None
        self.ms_varredura = None
        self._ia = self._cond = self._cache = None
        self._hwnd = None

    # --- varredura -------------------------------------------------------------------
    def _inicia_com(self):
        import comtypes
        try:
            comtypes.CoInitialize()
        except OSError:
            pass
        from pywinauto.uia_defines import IUIA
        ia = IUIA().iuia
        self._cond = ia.CreateOrCondition(ia.CreatePropertyCondition(UIA_CONTROLTYPE, UIA_TEXT_TYPE),
                                          ia.CreatePropertyCondition(UIA_CONTROLTYPE, UIA_EDIT_TYPE))
        self._cache = ia.CreateCacheRequest()
        self._cache.AddProperty(UIA_NAME)
        self._cache.AddProperty(UIA_CONTROLTYPE)
        self._cache.AddProperty(UIA_RECT)
        self._ia = ia

    def _varre_com(self):
        if self._ia is None:
            self._inicia_com()
        if self._hwnd is None:
            self._hwnd = _acha_janela_lenta().handle
        raiz = self._ia.ElementFromHandle(self._hwnd)
        return itens_de_array(raiz.FindAllBuildCache(ESCOPO_DESCENDENTES, self._cond, self._cache))

    def _varre(self, motivo="primeira"):
        t0 = self._relogio()
        try:
            itens = (self._varredor or self._varre_com)()
        except Exception:
            self._hwnd = None                # janela pode ter mudado
            self._itens = None
            raise
        self.ms_varredura = round((self._relogio() - t0) * 1000)
        decks = interpreta([t for _, t in itens])
        self._itens = so_faixa_dos_decks(itens)
        self._sig = [(d["n"], d["carregada"], d["titulo"]) for d in decks]
        self._t_varredura = self._relogio()
        self.modo = f"{len(self._itens)} textos em cache; ultima varredura {self.ms_varredura} ms por: {motivo}"
        return decks

    # --- leitura rapida ---------------------------------------------------------------
    @staticmethod
    def _nome(el):
        return (el.CurrentName or "").strip()

    def ler(self):
        if self._itens is None:
            return self._varre("sem cache")
        if self._relogio() - self._t_varredura > self.revarre_s:
            return self._varre("prazo")
        try:
            textos = []
            for el, t in self._itens:
                n = self._nome(el)
                if n:
                    textos.append(Texto(n, t.x, t.y, t.w, t.h, t.tipo))
        except Exception as e:
            return self._varre(f"referencia falhou ({type(e).__name__}: {e})"[:90])   # Rekordbox reconstruiu a tela
        decks = interpreta(textos)
        sig = [(d["n"], d["carregada"], d["titulo"]) for d in decks]
        if sig != self._sig:
            return self._varre(f"titulos mudaram: {self._sig} -> {sig}"[:140])   # pode ter surgido/sumido texto (artista, tom...)
        return decks
