import base64, os, sys
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
from padbridge2 import anlz, ajudante_db
from padbridge2.biblioteca import Biblioteca

falhas = 0
def ok(c, m):
    global falhas
    if not c:
        falhas += 1; print("FALHA:", m)

F = os.path.join(AQUI, "tests", "fixtures", "anlz")
DAT, EXT = os.path.join(F, "ANLZ0000.DAT"), os.path.join(F, "ANLZ0000.EXT")
if not os.path.exists(DAT):
    print("PULADO: faltam os arquivos de analise de teste (tests/fixtures/anlz/ANLZ0000.DAT/.EXT, de uma faixa pessoal que nao vai para o repositorio)"); sys.exit(0)

# --- leitor de ANLZ com arquivos reais do Rekordbox 7.2 (Oh La La, 210 s, 130.46 BPM, 457 batidas) ---
o = anlz.carrega(DAT, EXT)
ok(abs(o["duracao"] - 210.37) < 0.05 and o["fonte"].startswith("PWV5"), f"duracao/fonte: {o['duracao']} {o['fonte']}")
ok(len(o["batidas"]) == 457 and o["batidas"][:2] == [348, 808], f"batidas: {len(o['batidas'])} {o['batidas'][:2]}")
ok(o["colunas"] == 600 and len(o["alturas"]) == 600 and len(o["cores"]) == 600, "600 colunas")
ok(0 <= min(o["alturas"]) and max(o["alturas"]) <= 31 and max(o["cores"]) < 512, "alturas 0-31 e cores < 512")
ok(max(o["alturas"]) >= 22 and sum(o["alturas"]) / 600 > 10, "forma de onda com energia (nao e tudo zero)")
t = anlz.le_tags(open(DAT, "rb").read())
ok(anlz.batidas(t)[0] == (4, 130.46, 348), f"1a batida: {anlz.batidas(t)[0]}")
ok(len(anlz.miniatura(t)) == 400, "miniatura de 400 colunas")
so_dat = anlz.carrega(DAT, None)
ok(so_dat["colunas"] == 400 and so_dat["fonte"].startswith("PWAV") and abs(so_dat["duracao"] - 210) < 1, f"sem .EXT usa a miniatura: {so_dat['colunas']} {so_dat['duracao']}")
try: anlz.le_tags(b"lixo lixo lixo"); ok(False, "devia recusar arquivo invalido")
except ValueError: pass
ok(anlz.resumo_para_tela([], 10) == {"alturas": [], "cores": []}, "detalhe vazio")
ok(anlz.resumo_para_tela([(1, 2, 3, 9)], 4) == {"alturas": [9] * 4, "cores": [64 + 16 + 3] * 4}, "menos amostras que colunas nao quebra")
r = anlz.resumo_para_tela([(7, 0, 0, 30), (0, 0, 7, 10)], 1)
ok(r["alturas"] == [int(round(0.5 * 30 + 0.5 * 20))] and r["cores"][0] // 64 == 5 and r["cores"][0] % 8 == 2, f"altura = pico/media e cor ponderada pela altura: {r}")

# --- escolha da faixa certa quando ha titulos repetidos ---
c = [dict(artista="2 Eivissa", bpm=125.0, tom="1A", dat="a"), dict(artista="2 Eivissa", bpm=130.46, tom="5A", dat="b"), dict(artista="Outro", bpm=130.46, tom="5A", dat="c")]
ok(ajudante_db.escolhe(c, "2 eivissa", 130.46, "5A")["dat"] == "b", "escolhe por artista + bpm + tom")
ok(ajudante_db.escolhe(c, "2 Eivissa", None, None)["dat"] == "a", "sem bpm/tom fica com a primeira do artista")
ok(ajudante_db.escolhe(c, "Desconhecido", 130.46, "5A")["dat"] in ("b", "c"), "artista desconhecido ainda escolhe algo")
ok(ajudante_db.escolhe([dict(artista="x", bpm=1, tom="", dat=None), dict(artista="x", bpm=1, tom="", dat="ok")], "x")["dat"] == "ok", "prefere a que tem analise")
ok(ajudante_db.escolhe([], "x") is None, "sem candidatos")

ok([ajudante_db.kind_para_hotcue(k) for k in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9)] == [0, 1, 2, 3, None, 4, 5, 6, 7, 8], 'Kind do banco -> letra do hot cue (D=Kind 5)')
# --- processo ajudante de verdade (falso) ---
b = Biblioteca(comando=[sys.executable, os.path.join(AQUI, "tests", "ajudante_falso.py")], timeout=20)
r = b.onda("Oh La La", "2 Eivissa", 130.46, "5A")
ok(r["ok"] and r["faixa"] == 2 and r["onda"]["colunas"] == 600, f"onda pelo ajudante: {r.get('motivo') or r['faixa']}")
n0 = b._n; b.onda("Oh La La", "2 Eivissa", 130.46, "5A")
ok(b._n == n0, "segunda consulta vem do cache (nao pergunta de novo)")
r2 = b.onda("Nao Existe", "?", None, None); ok(not r2["ok"] and "nao encontrada" in r2["motivo"], f"nao encontrada: {r2}")
r3 = b.onda("Sem Analise", "X", 100.0, None); ok(not r3["ok"] and "analise" in r3["motivo"], f"sem analise: {r3}")
r4 = b.onda("Quebra", "", None, None); ok(not r4["ok"] and "banco travado" in r4["motivo"], f"erro do banco: {r4}")
r5 = b.onda("Oh La La", "2 Eivissa", 125.0, "1A"); ok(r5["ok"] and r5["faixa"] == 1 and r5["onda"]["colunas"] == 400, f"outra versao da faixa: {r5.get('faixa')} {r5.get('onda', {}).get('colunas')}")
ok(b.cues(2) == [dict(kind=1, ms=0, fim=None, comentario=""), dict(kind=2, ms=14725, fim=None, comentario=""), dict(kind=3, ms=73627, fim=None, comentario="")], f"cues pelo ajudante: {b.cues(2)}")
ok(b.cues(99) == [], "faixa sem cues")
ok(len(base64.b64decode(r["onda"]["detalhe"])) == 2 * 31556 or len(base64.b64decode(r["onda"]["detalhe"])) > 60000, "detalhe PWV5 vai junto")
ok(len(r["onda"]["batida_n"]) == len(r["onda"]["batidas"]) and r["onda"]["batida_n"][0] == 4, "numero da batida no compasso")
b.fecha()
# ajudante que nao existe: erro claro, sem travar
b2 = Biblioteca(comando=[sys.executable, os.path.join(AQUI, "tests", "nao_existe.py")], timeout=5)
r6 = b2.onda("x"); ok(not r6["ok"] and r6["motivo"], f"ajudante inexistente: {r6}")
print("FALHAS:", falhas); sys.exit(1 if falhas else 0)
