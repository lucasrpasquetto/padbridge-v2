"""Logica do servidor (sem aiohttp): publica estado, busca a waveform quando a faixa muda, ignora resultado velho."""
import asyncio, json, os, sys, threading, time
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
from padbridge2.servidor import Estado

falhas = 0
def ok(c, m):
    global falhas
    if not c:
        falhas += 1; print("FALHA:", m)

def deck(n, titulo, artista="A", bpm=120.0, tom="5A", rest="-03:00.0", dec="00:01.0"):
    if titulo is None:
        return dict(n=n, carregada=False, titulo=None, artista=None, bpm=None, tonalidade=None, restante=None, decorrido=None)
    return dict(n=n, carregada=True, titulo=titulo, artista=artista, bpm=bpm, tonalidade=tom, restante=rest, decorrido=dec)

class Leitor:
    def __init__(self): self.decks = [deck(1, None), deck(2, None)]
    def ler(self): return self.decks

class Bib:
    def __init__(self): self.chamadas, self.solta, self.solta2, self.trava_cues = [], threading.Event(), threading.Event(), threading.Event()
    def onda(self, titulo, artista, bpm, tom):
        self.chamadas.append(titulo)
        if titulo == "Lenta": self.solta.wait(3)
        if artista == "Outro": self.solta2.wait(3)
        if titulo == "SemOnda": return {"ok": False, "motivo": "faixa sem arquivo de analise"}
        return {"ok": True, "faixa": 7, "onda": {"duracao": 200.0, "colunas": 2, "alturas": [5, 9], "cores": [1, 2], "batidas": [0, 500], "fonte": titulo}}
    def cues(self, faixa):
        self.n_cues = getattr(self, "n_cues", 0) + 1
        if self.trava_cues.is_set() is False and getattr(self, "usa_trava", False): self.trava_cues.wait(3)
        return list(self.lista_cues)
    lista_cues = [{"kind": 1, "ms": 0, "fim": None, "comentario": ""}]
    def fecha(self): pass

class Cli:
    def __init__(self): self.msgs = []
    async def send_str(self, m): self.msgs.append(json.loads(m))
    def cues(self): return [m for m in self.msgs if m.get("tipo") == "cues"]
    def ondas(self): return [m for m in self.msgs if m.get("tipo") == "onda"]

async def espera(cond, s=3):
    t = time.time()
    while time.time() - t < s:
        if cond(): return True
        await asyncio.sleep(0.02)
    return False

async def main():
    lei, bib, cli = Leitor(), Bib(), Cli()
    est = Estado(lei, intervalo=0.02, biblioteca=bib, cue_intervalo=0.1); est.clientes.add(cli)
    est.inicia(asyncio.get_running_loop())
    await asyncio.sleep(0.15)
    ok(cli.ondas() == [] and bib.chamadas == [], "sem faixa carregada nao busca nada")
    lei.decks = [deck(1, "Oh La La", "2 Eivissa"), deck(2, None)]
    ok(await espera(lambda: any(m.get("ok") for m in cli.ondas())), "faixa carregada -> chega a waveform")
    o = cli.ondas()
    ok(o[0].get("pendente") and o[0]["n"] == 1, f"1o aviso e 'pendente': {o[0]}")
    ok(o[-1]["ok"] and o[-1]["alturas"] == [5, 9] and o[-1]["duracao"] == 200.0, f"depois a onda: {o[-1]}")
    n = len(bib.chamadas)
    lei.decks = [deck(1, "Oh La La", "2 Eivissa", dec="00:02.0"), deck(2, None)]    # so o tempo muda
    await asyncio.sleep(0.2)
    ok(len(bib.chamadas) == n, "so o tempo mudou: nao busca de novo")
    # cliente que chega depois recebe a waveform guardada
    tarde = Cli(); est.clientes.add(tarde)
    for m in list(est.ondas.values()): await tarde.send_str(json.dumps(m))
    ok(any(m.get("ok") for m in tarde.ondas()), "cliente novo recebe a waveform guardada")
    # cues: chegam depois da onda; so reenviam quando mudam; mudanca durante o set aparece
    ok(await espera(lambda: cli.cues()), "cues chegam depois da waveform")
    ok(cli.cues()[-1]["n"] == 1 and cli.cues()[-1]["cues"][0]["kind"] == 1, f"cues: {cli.cues()[-1]}")
    await asyncio.sleep(0.5); k = len(cli.cues())
    ok(k == 1 and bib.n_cues >= 3, f"relê o banco mas nao reenvia igual: {k} msgs, {bib.n_cues} leituras")
    bib.lista_cues = [{"kind": 1, "ms": 0, "fim": None, "comentario": ""}, {"kind": 2, "ms": 5000, "fim": 9000, "comentario": ""}]
    ok(await espera(lambda: len(cli.cues()) == 2 and len(cli.cues()[-1]["cues"]) == 2), "cue criado durante o set aparece")
    ok(est.cues[1][1]["fim"] == 9000, "loop (fim) preservado")
    # faixa sem analise
    lei.decks = [deck(1, "SemOnda"), deck(2, None)]
    ok(await espera(lambda: any(m.get("ok") is False for m in cli.ondas())), "sem analise avisa o motivo")
    ok("sem arquivo" in [m for m in cli.ondas() if m.get("ok") is False][-1]["motivo"], "motivo repassado")
    # resultado velho e ignorado: a faixa "Lenta" termina DEPOIS de o deck ja ter outra faixa (cuja busca ainda esta na fila)
    lei.decks = [deck(1, "Lenta"), deck(2, None)]
    await espera(lambda: "Lenta" in bib.chamadas)
    lei.decks = [deck(1, "Oh La La", "Outro"), deck(2, None)]
    await espera(lambda: est._faixa_vista.get(1) == ("Oh La La", "Outro"))
    bib.solta.set(); await asyncio.sleep(0.3)
    ok(est.ondas[1].get("pendente") and not est.ondas[1].get("ok"), f"waveform da faixa velha nao aparece na faixa nova: {est.ondas[1].get('fonte')} {est.ondas[1]}")
    ok(not any(m.get("fonte") == "Lenta" for m in cli.ondas()), "cliente nunca recebeu a waveform da 'Lenta'")
    bib.solta2.set()
    ok(await espera(lambda: est.ondas[1].get("ok") and est.ondas[1]["fonte"] == "Oh La La"), "e depois chega a da faixa nova")
    ok(not any(m["cues"] for m in cli.cues() if m["n"] == 2), "deck 2 nunca teve cues")
    # leitura de cues lenta que termina depois de o deck trocar de faixa: nao pode aparecer na faixa nova
    lei.decks = [deck(1, "Oh La La", "Outro"), deck(2, None)]
    await espera(lambda: est.ondas.get(1, {}).get("ok")); bib.solta2.clear(); bib.usa_trava = True
    lei.decks = [deck(1, "Oh La La", "Cx"), deck(2, None)]
    await espera(lambda: est.ondas.get(1, {}).get("fonte") == "Oh La La" and est._faixa_vista.get(1) == ("Oh La La", "Cx"))
    await asyncio.sleep(0.4)                              # leitura de cues de "Cx" travada no banco
    lei.decks = [deck(1, "Oh La La", "Outro"), deck(2, None)]
    await espera(lambda: est._faixa_vista.get(1) == ("Oh La La", "Outro"))
    est.cues.pop(1, None); bib.usa_trava = False; bib.trava_cues.set(); await asyncio.sleep(0.15)
    ok(1 not in est.cues, f"cues velhos nao aparecem na faixa nova: {est.cues}")
    bib.solta2.set(); await asyncio.sleep(0.2)
    # deck descarregado
    lei.decks = [deck(1, None), deck(2, None)]
    ok(await espera(lambda: est.ondas.get(1, {}).get("vazia")), "deck vazio limpa a waveform")
    ok(cli.cues()[-1]["cues"] == [] and 1 not in est.cues, "deck vazio limpa os cues")
    est.para()
    # sem biblioteca: nada de ondas
    cli2 = Cli(); lei2 = Leitor(); lei2.decks = [deck(1, "X"), deck(2, None)]
    e2 = Estado(lei2, intervalo=0.02); e2.clientes.add(cli2); e2.inicia(asyncio.get_running_loop())
    await asyncio.sleep(0.2); ok(cli2.ondas() == [], "sem biblioteca nao ha mensagens de onda"); e2.para()

asyncio.run(main())
print("FALHAS:", falhas); sys.exit(1 if falhas else 0)
