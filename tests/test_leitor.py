import os, sys
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
from padbridge2.leitor_decks import interpreta, le_dump, Texto, textos_de_array, LeitorDecks, so_faixa_dos_decks

falhas = 0
def ok(c, m):
    global falhas
    if not c:
        falhas += 1; print("FALHA:", m)

t = le_dump(os.path.join(AQUI, "tests", "fixtures", "uia_dois_decks.txt"))
d = interpreta(t)
ok(len(d) == 2, f"2 decks, veio {len(d)}")
e = dict(n=1, carregada=True, titulo="Oh La La", artista="2 Eivissa", bpm=130.46, bpm_faixa=130.46, tonalidade="5A", restante="-03:29.3", decorrido="00:01.0")
dd = dict(n=2, carregada=True, titulo="Candy Shop (Acapella 125 BPM)", artista="50 Cent", bpm=85.15, bpm_faixa=95.24, tonalidade="12A", restante="-02:54.7", decorrido="00:00.4")
ok(d[0] == e, f"deck 1: {d[0]}"); ok(d[1] == dd, f"deck 2: {d[1]}")

# outra escala do Windows (125%, 150%, 200%): as medidas crescem juntas e o resultado tem que ser o mesmo
for esc in (1.25, 1.5, 2.0):
    te = [Texto(x.nome, round(x.x * esc), round(x.y * esc), round(x.w * esc), round(x.h * esc), x.tipo) for x in t]
    de = interpreta(te)
    ok(de == d, f"escala {esc}: mesmo resultado ({[(x['n'], x['titulo'], x['bpm'], x['tonalidade'], x['artista']) for x in de]})")
    itens = [(i, x) for i, x in enumerate(te)]
    ok(interpreta([x for _, x in so_faixa_dos_decks(itens)]) == d, f"escala {esc}: o filtro de cache mantem o que importa")

# deck vazio: o titulo vira 'Not Loaded.'
t2 = [Texto("Not Loaded.", x.x, x.y, x.w, x.h) if x.nome == "Candy Shop (Acapella 125 BPM)" else x for x in t]
v = interpreta(t2)[1]
ok(v["carregada"] is False and v["titulo"] is None and v["bpm"] is None, f"deck vazio: {v}")
# faixa sem artista e sem tonalidade
t3 = [x for x in t if x.nome not in ("50 Cent", "12A")]
s = interpreta(t3)[1]
ok(s["titulo"].startswith("Candy") and s["artista"] is None and s["bpm"] == 85.15 and s["tonalidade"] is None, f"sem artista/tom: {s}")
# a numeracao '1','2' dos efeitos e dos stems nao vira deck
ok([x["n"] for x in d] == [1, 2], "so os numeros de deck viram deck")
# mutacao: sem o titulo grande, nao ha deck
ok(len(interpreta([x for x in t if not (x.h >= 16 and x.w >= 200)])) == 0, "sem titulo nao ha ancora")
# conversao do array COM (simulado): so Text com nome, ignora vazios e erros
class R:  # retangulo
    def __init__(s, l, t, r, b): s.left, s.top, s.right, s.bottom = l, t, r, b
class El:
    def __init__(s, n, r): s.CachedName, s._r = n, r
    @property
    def CachedBoundingRectangle(s):
        if s._r is None: raise OSError("sem retangulo")
        return s._r
class Arr:
    def __init__(s, els): s.els, s.Length = els, len(els)
    def GetElement(s, i): return s.els[i]
ar = textos_de_array(Arr([El(" Oh La La ", R(10, 20, 110, 40)), El("", R(0, 0, 1, 1)), El("sem", None), El(None, R(0, 0, 1, 1))]))
ok(ar == [Texto("Oh La La", 10, 20, 100, 20)], f"array COM: {ar}")
# --- LeitorDecks: varredura lenta so quando precisa; o resto e leitura rapida das referencias ----------------
class Fake:
    def __init__(s, nome): s.nome, s.quebra = nome, False
    @property
    def CurrentName(s):
        if s.quebra: raise OSError("elemento velho")
        return s.nome
class Rel:
    t = 1000.0
    def __call__(s): return s.t
def monta():
    els = [(Fake(x.nome), x) for x in t]
    cont = {"n": 0}
    def varredor():
        cont["n"] += 1
        return [(e, Texto(e.nome, x.x, x.y, x.w, x.h, x.tipo)) for e, x in els]
    return els, cont, varredor
els, cont, var = monta(); rel = Rel()
lk = LeitorDecks(revarre_s=30, varredor=var, relogio=rel)
a = lk.ler()
ok(a == d and cont["n"] == 1, f"1a leitura varre e interpreta: varreduras={cont['n']}")
ok(0 < len(lk._itens) < len(t) // 2 and all(x.y <= 240 or x.tipo == "Edit" for _, x in lk._itens), f"guarda so as faixas dos decks: {len(lk._itens)} de {len(t)}")
ok("por: sem cache" in lk.modo, lk.modo)
# BPM ao vivo: o campo Edit muda com o pitch; a leitura rapida pega, sem varredura, e o BPM da faixa fica
edit1 = next(e for e, x in els if x.tipo == "Edit" and x.nome == "130.46")
n0 = cont["n"]; edit1.nome = "144.01"; rel.t += 0.2
a = lk.ler()
ok(a[0]["bpm"] == 144.01 and a[0]["bpm_faixa"] == 130.46 and cont["n"] == n0, f"BPM ao vivo (pitch): {a[0]['bpm']} / faixa {a[0]['bpm_faixa']} varreduras {cont['n']}")
ok(a[1]["bpm"] == 85.15, "o outro deck nao muda")
edit1.nome = "130.46"
# sem o campo Edit usa o BPM do cabecalho
sem = interpreta([x for x in t if x.tipo != "Edit"])
ok(sem[0]["bpm"] == 130.46 and sem[1]["bpm"] == 95.24, "sem o campo Edit cai no BPM da faixa")
# tempo muda: leitura rapida, sem nova varredura
rest = next(e for e, x in els if x.nome == "-03:29")
rest.nome = "-03:28"; rel.t += 0.3
b = lk.ler()
ok(cont["n"] == 1 and b[0]["restante"] == "-03:28.3", f"tempo muda sem varrer: {b[0]['restante']} varreduras={cont['n']}")
# faixa troca: varre de novo
tit = next(e for e, x in els if x.nome == "Oh La La")
tit.nome = "Outra Musica"
c2 = lk.ler()
ok(cont["n"] == 2 and c2[0]["titulo"] == "Outra Musica" and "titulos mudaram" in lk.modo, f"faixa nova dispara varredura: {cont['n']} {lk.modo}")
# elemento velho: varre de novo
rest.quebra = True; rest.nome = "-03:00"
lk.ler(); ok(cont["n"] == 3 and "referencia falhou" in lk.modo, f"referencia velha dispara varredura: {cont['n']} {lk.modo}")
rest.quebra = False
# passou o prazo: varre de novo
rel.t += 31; lk.ler(); ok(cont["n"] == 4 and "por: prazo" in lk.modo, f"prazo vencido dispara varredura: {cont['n']} {lk.modo}")
# varredura que falha: erro sobe e o cache e descartado
def ruim(): raise RuntimeError("janela do Rekordbox nao encontrada")
lk2 = LeitorDecks(varredor=ruim, relogio=rel)
try: lk2.ler(); ok(False, "devia levantar")
except RuntimeError: ok(lk2._itens is None, "erro de varredura limpa o cache")
print("FALHAS:", falhas); sys.exit(1 if falhas else 0)
