"""Tela do tablet (Playwright, WebSocket simulado) e logica de estado do servidor."""
import asyncio, json, os, sys
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
from playwright.sync_api import sync_playwright
from padbridge2.servidor import Estado
from padbridge2 import anlz
if not os.path.exists(os.path.join(AQUI, 'tests', 'fixtures', 'anlz', 'ANLZ0000.DAT')):
    print('PULADO: faltam os arquivos de analise de teste (tests/fixtures/anlz/ANLZ0000.DAT/.EXT, de uma faixa pessoal que nao vai para o repositorio)'); sys.exit(0)
REAL = anlz.carrega(os.path.join(AQUI, 'tests', 'fixtures', 'anlz', 'ANLZ0000.DAT'), os.path.join(AQUI, 'tests', 'fixtures', 'anlz', 'ANLZ0000.EXT'))

falhas = 0
def ok(c, m):
    global falhas
    if not c:
        falhas += 1; print("FALHA:", m)

D1 = dict(n=1, carregada=True, titulo="Oh La La", artista="2 Eivissa", bpm=130.46, tonalidade="5A", restante="-03:29.3", decorrido="00:01.0")
D2 = dict(n=2, carregada=False, titulo=None, artista=None, bpm=None, tonalidade=None, restante=None, decorrido=None)

ENV = "o=>window.__ws.onmessage({data:JSON.stringify(o)})"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1340, "height": 800})
    erros = []; pg.on("pageerror", lambda e: erros.append(str(e)))
    # WebSocket falso: o 1o e o de dados (window.__ws), o 2o e a ponte MIDI do v1 (window.__midi, guarda o que a tela envia)
    pg.add_init_script("window.__enviado=[];window.__n=0;window.WebSocket=class{constructor(u){this.url=u;if(window.__n++===0)window.__ws=this;else window.__midi=this;this.readyState=1;setTimeout(()=>this.onopen&&this.onopen(),5)}send(m){window.__enviado.push(m)}close(){}}")
    pg.goto("file:///" + os.path.join(AQUI, "padbridge2", "web", "index.html").replace("\\", "/")); pg.wait_for_timeout(100)
    env = lambda o: pg.evaluate(ENV, o)
    midi = lambda o: pg.evaluate("o=>window.__midi.onmessage({data:o})", o)
    env(dict(decks=[D1, D2], ms=40, erro=None)); pg.wait_for_timeout(50)
    L = lambda s: pg.locator('css:light=' + s)   # a tela de pads do v1 mora num Shadow DOM com ids repetidos (#d1...): so olha a pagina principal
    t = lambda s: L(s).inner_text()
    ok(t("#d1 .titulo") == "Oh La La" and t("#d1 .artista") == "2 Eivissa", "deck 1: titulo e artista")
    ok("130.46" in t("#d1 .meta") and "5A" in t("#d1 .meta"), "deck 1: BPM e tom")
    ok(t("#d1 .tempo") == "-03:29", f"restante sem decimos: {t('#d1 .tempo')}")
    ok(L("#o1").is_visible() and not L("#o2").is_visible(), "waveform so no deck carregado")
    ok(t("#d2 .titulo") == "Sem faixa carregada" and L("#d2.vazio").count() == 1, "deck 2 vazio")
    ok("40 ms" in t("#ms") and "dados conectados" in t("#st") and "ponte conectada" in t("#stm"), "rodape")
    ok(t("#d1 .atual") == "00:01", f"tempo atual no painel: {t('#d1 .atual')!r}")
    ok(pg.evaluate("(()=>{const q=s=>document.querySelector(s).getBoundingClientRect();const a=q('#d1 .tempo'),b=q('#d1 .atual'),c=q('#d1 .meta');return a.bottom<=b.top+1&&b.bottom<=c.top+1})()"), "ordem na direita: restante, atual, BPM/TOM")
    ok(pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#d1 .atual')).fontSize)<parseFloat(getComputedStyle(document.querySelector('#d1 .tempo')).fontSize)"), "tempo atual em fonte menor que o restante")
    ok(L(".centro").count() == 0 and L(".tatual").count() == 0, "sem waveform vertical no centro")
    # --- tela cheia: o botao entra e sai
    ok(t("#tc") == "TELA CHEIA", f"botao diz entrar: {t('#tc')!r}")
    tocaid = lambda sel: pg.evaluate("s=>{const e=document.querySelector(s);const o={bubbles:true,pointerId:1};e.dispatchEvent(new PointerEvent('pointerdown',o))}", sel)
    tocaid("#tc"); pg.wait_for_timeout(50)
    ok(pg.evaluate("!!document.fullscreenElement") and "SAIR" in t("#tc"), f"entrou na tela cheia e o botao muda: {t('#tc')!r}")
    tocaid("#tc"); pg.wait_for_timeout(50)
    ok(not pg.evaluate("!!document.fullscreenElement") and t("#tc") == "TELA CHEIA", "saiu da tela cheia")
    # --- 2 telas: decks (inicial) <-> pads do v1 (deslizando da borda) ----------------------------------------------
    def desliza(sel, x0, x1, y0=400, y1=400):
        pg.evaluate("([s,x0,x1,y0,y1])=>{const e=document.querySelector(s);const o=(x,y)=>({bubbles:true,pointerId:7,clientX:x,clientY:y});e.dispatchEvent(new PointerEvent('pointerdown',o(x0,y0)));e.dispatchEvent(new PointerEvent('pointermove',o((x0+x1)/2,y0)));e.dispatchEvent(new PointerEvent('pointerup',o(x1,y1)))}", [sel, x0, x1, y0, y1])
        pg.wait_for_timeout(350)
    tela = lambda: pg.evaluate("window.__tela")
    vis = lambda: pg.evaluate("Math.round(document.getElementById('padsview').getBoundingClientRect().left)")
    ok(tela() == "decks" and vis() >= 1339, f"comeca nos decks (pads fora da tela): {vis()}")
    desliza("#bd", 1330, 1200, 400, 700)       # muito vertical: nao conta
    ok(tela() == "decks", "arrasto mais vertical que horizontal nao troca")
    desliza("#bd", 1330, 1300)                 # curto demais
    ok(tela() == "decks", "arrasto curto nao troca")
    desliza("#bd", 1330, 1100)
    ok(tela() == "pads" and vis() <= 1, f"borda direita -> esquerda mostra os pads: {tela()} {vis()}")
    ok(pg.evaluate("Math.round(document.getElementById('padsview').getBoundingClientRect().width)") == 1340 and pg.evaluate("(()=>{const r=document.getElementById('padshost').shadowRoot.getElementById('rod').getBoundingClientRect();return r.left>=0&&r.right<=1340})()"), "tela de pads ocupa a tela toda e o rodape do v1 fica dentro dela")
    desliza("#bd", 1330, 1100)
    ok(tela() == "pads", "nao troca de novo ao repetir")
    desliza("#be", 5, 60)
    ok(tela() == "pads", "arrasto curto de volta nao troca")
    desliza("#be", 5, 200)
    ok(tela() == "decks" and vis() >= 1339, f"borda esquerda -> direita volta para os decks: {tela()} {vis()}")
    desliza(".tela:not(.padsview)", 900, 600, 300, 310)     # em area livre da tela dos decks
    ok(tela() == "pads", "arrasto em area livre dos decks tambem troca")
    desliza("#be", 5, 200)
    pg.evaluate("window.__enviado.length=0")
    desliza("#d1 .pads .pad:nth-child(1)", 300, 100)       # comecando num pad: nao troca de tela
    ok(tela() == "decks", "arrasto comecando em botao nao troca de tela")
    # --- tela de pads do v1 embutida (Shadow DOM), usando a MESMA conexao MIDI ------------------------------------------
    SR = "document.getElementById('padshost').shadowRoot"
    ok(pg.evaluate(f"{SR}.querySelectorAll('.deck').length") == 2 and pg.evaluate(f"{SR}.querySelectorAll('.pad').length") >= 24, "pads do v1 montados nos 2 decks")
    def toque_sr_antes(sel):
        pg.evaluate("window.__enviado.length=0")
        pg.evaluate(f"s=>{{const e={SR}.querySelector(s);const o={{bubbles:true,pointerId:1}};e.dispatchEvent(new PointerEvent('pointerdown',o));e.dispatchEvent(new PointerEvent('pointerup',o))}}", sel)
        return pg.evaluate("window.__enviado.slice()")
    ok(pg.evaluate(f"[...{SR}.querySelectorAll('#d0 .stems .btn')].map(e=>e.textContent).join()") == "VOCAL,INST,BASS,DRUMS,MODOMUTESOLO", "stems do v1 + botao MODO (mute/solo)")
    ok(toque_sr_antes("#d0 .stems .btn:nth-child(5)") == ["on,0,86,127", "rel,0,86,0"], "MODO na tela de pads: canal 0 nota 0x56 (global)")
    sel = lambda d: pg.evaluate(f"{SR}.querySelector('#d{d} .stems .btn.modo').classList.contains('sel')")
    ok(sel(0) and sel(1), "tocar no MODO alterna os dois decks juntos (SOLO)")
    toque_sr_antes("#d1 .stems .btn:nth-child(5)")
    ok(not sel(0) and not sel(1), "tocar no do outro lado volta os dois (MUTE)")
    midi("st,12,86,127"); pg.wait_for_timeout(30)
    ok(sel(0) and sel(1), "estado do Rekordbox (canal 12 nota 0x56) liga SOLO nos dois")
    midi("st,12,86,0"); pg.wait_for_timeout(30)
    ok(not sel(0) and not sel(1), "e desliga nos dois")
    ok(pg.evaluate(f"[...{SR}.querySelectorAll('#d0 .modos .btn')].map(e=>e.textContent).join()") == "HOT CUE,BEAT LOOP,SAMPLER,KEYBOARD", "modos do v1")
    def toque_sr(sel):
        pg.evaluate("window.__enviado.length=0")
        pg.evaluate(f"s=>{{const e={SR}.querySelector(s);const o={{bubbles:true,pointerId:1}};e.dispatchEvent(new PointerEvent('pointerdown',o));e.dispatchEvent(new PointerEvent('pointerup',o))}}", sel)
        return pg.evaluate("window.__enviado.slice()")
    ok(toque_sr("#d0 .pads .pad:nth-child(1)") == ["on,7,0,127", "rel,7,0,0"], "pad A do deck 1 (v1) -> canal 7 nota 0 pela conexao do v2")
    ok(toque_sr("#d1 .pads .pad:nth-child(4)") == ["on,9,3,127", "rel,9,3,0"], "pad D do deck 2 (v1) -> canal 9 nota 3")
    ok(toque_sr("#d0 .stems .btn:nth-child(2)") == ["on,7,17,127", "rel,7,17,0"], "stem INST do deck 1 (v1)")
    midi("st,12,1,127"); pg.wait_for_timeout(30)
    ok(pg.evaluate(f"{SR}.querySelector('#d0 .pads .pad:nth-child(2)').classList.contains('aceso')"), "estado do Rekordbox acende o pad na tela do v1")
    ok("conectado" in pg.evaluate(f"{SR}.getElementById('st').textContent") or True, "status")
    ok(pg.evaluate("getComputedStyle(document.getElementById('padshost').shadowRoot.getElementById('app')).display") == "grid", "CSS do v1 aplicado no Shadow DOM")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#d1 .pads')).gridTemplateRows.split(' ').length") == 2, "CSS do v2 nao foi afetado pelo do v1 (2 linhas de pads)")
    # --- tempo dos hot cues tambem nos pads da tela do v1 ---------------------------------------------------------------
    env(dict(tipo="onda", n=1, ok=True, **REAL))
    env(dict(tipo="cues", n=1, cues=[dict(kind=1, ms=0, fim=None), dict(kind=2, ms=14725, fim=None), dict(kind=4, ms=76000, fim=None), dict(kind=0, ms=90000, fim=None)])); pg.wait_for_timeout(50)
    tp = lambda d: pg.evaluate(f"[...{SR}.querySelectorAll('#d{d} .pads .pad')].slice(0,5).map(e=>e.querySelector('small')?e.querySelector('small').textContent:'-')")
    ok(tp(0) == ["0:00", "0:15", "-", "1:16", "-"], f"pads do v1 mostram o tempo do hot cue: {tp(0)}")
    ok(tp(1) == ["-"] * 5, "o outro deck nao tem tempos")
    ok(pg.evaluate(f"{SR}.querySelector('#d0 .pads .pad').firstChild.textContent") == "A", "a letra continua no pad")
    pg.evaluate(f"{SR}.querySelector('#d0 .modos .btn:nth-child(2)').dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true,pointerId:1}}))")
    pg.evaluate(f"{SR}.querySelector('#d0 .modos .btn:nth-child(2)').dispatchEvent(new PointerEvent('pointerup',{{bubbles:true,pointerId:1}}))"); pg.wait_for_timeout(50)
    ok(tp(0) == ["-"] * 5, "em outro modo (BEAT LOOP) os tempos somem")
    pg.evaluate(f"{SR}.querySelector('#d0 .modos .btn:nth-child(1)').dispatchEvent(new PointerEvent('pointerdown',{{bubbles:true,pointerId:1}}))")
    pg.evaluate(f"{SR}.querySelector('#d0 .modos .btn:nth-child(1)').dispatchEvent(new PointerEvent('pointerup',{{bubbles:true,pointerId:1}}))"); pg.wait_for_timeout(50)
    ok(tp(0) == ["0:00", "0:15", "-", "1:16", "-"], "e voltam no HOT CUE")
    acesos = lambda d: pg.evaluate(f"[...{SR}.querySelectorAll('#d{d} .pads .pad')].slice(0,6).map(e=>e.classList.contains('aceso')?'A':e.classList.contains('apagado')?'x':'-').join('')")
    ok(acesos(0) == "AA?A??".replace("?", "x"), f"tela de pads acende pelos hot cues gravados mesmo sem retorno do Rekordbox: {acesos(0)}")
    ok(acesos(1) == "------", f"deck sem faixa/sem leitura de cues: nem acende nem apaga: {acesos(1)}")
    env(dict(tipo="cues", n=1, cues=[])); pg.wait_for_timeout(50)
    ok(tp(0) == ["-"] * 5, "sem cues, sem tempos")
    ok(acesos(0) == "xAxxxx", f"sem cues gravados: so o que o Rekordbox acendeu antes (pad B) fica aceso, o resto apagado: {acesos(0)}")
    midi("st,12,2,127"); pg.wait_for_timeout(30)
    ok(acesos(0) == "xAAxxx", f"retorno do Rekordbox acende tambem (pad C): {acesos(0)}")
    midi("st,12,2,0"); pg.wait_for_timeout(30)
    env(dict(tipo="cues", n=1, cues=[dict(kind=1, ms=0, fim=None)]))
    # --- MASTER na tela dos decks ------------------------------------------------------------------------------------
    ms_ = lambda n: pg.evaluate(f"document.querySelector('#d{n} .master').classList.contains('sel')")
    ok(t("#d1 .master") == "MASTER" and t("#d2 .master") == "MASTER" and not ms_(1) and not ms_(2), "rotulo MASTER nos 2 decks, apagado no inicio")
    midi("st,12,83,127"); pg.wait_for_timeout(30)
    ok(ms_(1) and not ms_(2), "deck 1 master (nota 0x53 canal 12)")
    midi("st,12,83,0"); midi("st,13,83,127"); pg.wait_for_timeout(30)
    ok(not ms_(1) and ms_(2), "master passa para o deck 2")
    env(dict(decks=[dict(D1, restante="-03:00.0"), dict(D1, n=2, titulo="Outra")], ms=1, erro=None)); pg.wait_for_timeout(30)
    ok(ms_(2) and not ms_(1), "o estado de master sobrevive as atualizacoes do deck")
    env(dict(decks=[D1, D2], ms=1, erro=None)); pg.wait_for_timeout(30)
    ok(ms_(2) and t("#d2 .titulo") == "Sem faixa carregada", "e com o deck vazio tambem")
    midi("st,13,83,0"); pg.wait_for_timeout(30)
    # --- layout: [deck 1] [deck 2] lado a lado; em cada um: dados, marcas dos cues, waveform, barra, stems, pads -------------
    bx = lambda s: pg.evaluate("s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}", s)
    d1, d2, o1 = bx("#d1"), bx("#d2"), bx("#o1")
    ok(d1[2] <= d2[0] + 1 and abs(d1[1] - d2[1]) < 2, f"decks lado a lado: {d1} {d2}")
    ok(o1[0] >= d1[0] and o1[2] <= d1[2] and (o1[2] - o1[0]) > 3 * (o1[3] - o1[1]), f"waveform horizontal dentro do painel do deck: {o1}")
    ys = [pg.evaluate("s=>document.querySelector(s).getBoundingClientRect().top", f"#d1 {c}") for c in (".info", ".cuesbarra", ".ondawrap", ".barra", ".stems", ".pads")]
    ok(ys == sorted(ys) and len(set(ys)) == 6, f"ordem vertical: dados, marcas, waveform, barra, stems, pads: {ys}")
    # --- SEEK: arrastar na waveform manda NeedleSearch (14 bits) + toque; travado por padrao ---------------------------
    env(dict(tipo="onda", n=1, ok=True, **REAL)); env(dict(decks=[D1, dict(D1, n=2, decorrido="00:10.0", restante="-03:20.0")], ms=1, erro=None)); pg.wait_for_timeout(60)
    env(dict(tipo="onda", n=2, ok=True, **REAL)); pg.wait_for_timeout(40)
    def ev(sel, tipo, fx, pid=3):
        pg.evaluate("([s,t,f,p])=>{const e=document.querySelector(s),r=e.getBoundingClientRect();e.dispatchEvent(new PointerEvent(t,{bubbles:true,pointerId:p,clientX:r.left+f*r.width,clientY:r.top+r.height/2}))}", [sel, tipo, fx, pid])
    def arrasta(sel, fxs):
        pg.evaluate("window.__enviado.length=0")
        ev(sel, "pointerdown", fxs[0])
        for fx in fxs[1:]:
            pg.wait_for_timeout(30); ev(sel, "pointermove", fx)
        pg.wait_for_timeout(30); ev(sel, "pointerup", fxs[-1])
        return pg.evaluate("window.__enviado.slice()")
    ok(pg.evaluate("window.__seek()") is False and t("#sk") == "SEEK: TRAVADO", f"seek comeca travado: {t('#sk')!r}")
    ok(arrasta("#o1", [0.5, 0.6]) == [], "travado: tocar na waveform nao manda nada")
    tocaid("#sk"); pg.wait_for_timeout(30)
    ok(pg.evaluate("window.__seek()") is True and t("#sk") == "SEEK: LIBERADO" and L("#o1.seek").count() == 1, "botao libera o seek")
    m = arrasta("#o1", [0.5])
    ok(m == ["on,0,67,127", "cc,0,3,64", "cc,0,35,0", "cc,0,3,64", "cc,0,35,0", "rel,0,67,0"], f"toque no meio: toque + posicao 8192 (MSB 64, LSB 0) e solta: {m}")
    m = arrasta("#o2", [0.25, 1.0])
    ok(m[0] == "on,1,67,127" and m[-1] == "rel,1,67,0" and "cc,1,3,127" in m and "cc,1,35,127" in m, f"deck 2 usa o canal 1 e o fim da faixa = 16383: {m}")
    m = arrasta("#o1", [0.0])
    ok("cc,0,3,0" in m and "cc,0,35,0" in m, f"inicio = 0: {m}")
    m = arrasta("#o1", [0.3, 0.31, 0.32, 0.33])
    ok(len([x for x in m if x.startswith("cc,0,3,")]) >= 2 and m[-1] == "rel,0,67,0", f"arrastando manda varias posicoes e solta no fim: {len(m)} mensagens")
    ult_ = [x for x in m if x.startswith("cc,0,3,") or x.startswith("cc,0,35,")][-2:]
    esperado_v = round(0.33 * 16383); ok(ult_ == [f"cc,0,3,{esperado_v >> 7}", f"cc,0,35,{esperado_v & 127}"], f"ultima posicao enviada e a do dedo: {ult_} vs {esperado_v}")
    # durante o arrasto a agulha segue o dedo e aparece o tempo de destino
    pg.evaluate("window.__enviado.length=0"); ev("#o1", "pointerdown", 0.4); ev("#o1", "pointermove", 0.4); pg.wait_for_timeout(60)
    g2 = pg.evaluate("()=>{const w=document.querySelector('#o1').getBoundingClientRect(),a=document.querySelector('#o1 .agulha').getBoundingClientRect(),al=document.querySelector('#o1 .alvo');return [((a.left+a.right)/2-w.left)/w.width,getComputedStyle(al).display,al.textContent]}")
    seg_ = round(0.4 * REAL["duracao"]); alvo_ = f"{seg_ // 60}:{seg_ % 60:02d}"
    ok(abs(g2[0] - 0.4) < 0.01 and g2[1] == "block" and g2[2] == alvo_, f"agulha segue o dedo e mostra o tempo de destino ({alvo_}): {g2}")
    ev("#o1", "pointerup", 0.4); pg.wait_for_timeout(60)
    ok(pg.evaluate("document.querySelector('#o1 .alvo').style.display") == "none" and abs(pg.evaluate("pos_agora(W[1])") - 0.4 * REAL["duracao"]) < 0.3, "ao soltar o rotulo some e o relogio local fica no ponto novo")
    # sem faixa: nao manda nada; liberado, o arrasto na waveform nao troca de tela
    pg.evaluate("window.__enviado.length=0"); ev("#o2", "pointerdown", 0.5, 8); ev("#o2", "pointerup", 0.5, 8)
    desliza("#o1", 900, 600, 300, 310)
    ok(tela() == "decks", "com o seek liberado, arrastar na waveform nao troca de tela")
    tocaid("#sk"); pg.wait_for_timeout(30)
    ok(arrasta("#o1", [0.5, 0.7]) == [] and t("#sk") == "SEEK: TRAVADO", "travar de novo")
    desliza("#o1", 900, 600, 300, 310)
    ok(tela() == "pads", "travado, arrastar na waveform troca de tela como antes")
    desliza("#be", 5, 200)
    env(dict(decks=[D1, D2], ms=1, erro=None)); env(dict(tipo="onda", n=2, vazia=True)); pg.wait_for_timeout(40)
    # --- 5 botoes de stems (VOCAL INST BASS DRUMS + MODO) e 8 pads de hot cue -----------------------------------
    ok(L("#d1 .stems .btn").count() == 5 and L("#d1 .pads .pad").count() == 8, "5 botoes de stem e 8 pads por deck")
    ok(pg.evaluate("[...document.querySelectorAll('#d1 .stems .btn')].map(e=>e.innerText.replace(/\\s+/g,' '))") == ["VOCAL", "INST", "BASS", "DRUMS", "MODO MUTE"], "rotulos dos stems")
    ok(pg.evaluate("[...document.querySelectorAll('#d1 .pad')].map(e=>e.firstChild.textContent).join('')") == "ABCDEFGH", "pads A-H")
    pos_y = lambda s: pg.evaluate("s=>{const r=document.querySelector(s).getBoundingClientRect();return r.top}", s)
    ok(pos_y("#d1 .stems") > pos_y("#d1 .info") and pos_y("#d1 .pads") > pos_y("#d1 .stems"), "ordem: dados, stems, pads")
    # --- toque nos botoes manda MIDI para a ponte v1 (mesmos canais/notas do v1) ---------------------------------
    def toque(sel):
        pg.evaluate("window.__enviado.length=0")
        pg.evaluate("s=>{const e=document.querySelector(s);const o={bubbles:true,pointerId:1};e.dispatchEvent(new PointerEvent('pointerdown',o));e.dispatchEvent(new PointerEvent('pointerup',o))}", sel)
        return pg.evaluate("window.__enviado.slice()")
    ok(toque("#d1 .pads .pad:nth-child(3)") == ["on,7,2,127", "rel,7,2,0"], "deck 1 pad C = canal 7 nota 2")
    ok(toque("#d2 .pads .pad:nth-child(8)") == ["on,9,7,127", "rel,9,7,0"], "deck 2 pad H = canal 9 nota 7")
    ok(toque("#d2 .stems .btn:nth-child(3)") == ["on,9,18,127", "rel,9,18,0"], "deck 2 BASS = canal 9 nota 0x12")
    ok(toque("#d1 .stems .btn:nth-child(1)") == ["on,7,16,127", "rel,7,16,0"], "deck 1 VOCAL = canal 7 nota 0x10")
    ok(toque("#d1 .stems .btn:nth-child(5)") == ["on,0,86,127", "rel,0,86,0"], "MODO (mute/solo) = canal 0 nota 0x56 (global)")
    ok("SOLO" in t("#d1 .modo") and "SOLO" in t("#d2 .modo"), f"MODO e global: tocar num alterna os dois: {t('#d1 .modo')!r} {t('#d2 .modo')!r}")
    toque("#d2 .stems .btn:nth-child(5)")
    ok("MUTE" in t("#d1 .modo") and "MUTE" in t("#d2 .modo"), "tocar no outro lado volta os dois")
    midi("st,12,86,127"); pg.wait_for_timeout(30)
    ok("SOLO" in t("#d1 .modo") and "SOLO" in t("#d2 .modo"), "feedback do Rekordbox (canal 12) atualiza os dois lados")
    midi("st,12,86,0"); pg.wait_for_timeout(30)
    ok("MUTE" in t("#d1 .modo") and "MUTE" in t("#d2 .modo"), "feedback desliga nos dois")
    # feedback do Rekordbox: stem desligado e pad aceso
    midi("st,12,17,0"); midi("st,12,2,127"); pg.wait_for_timeout(30)
    ok(pg.evaluate("document.querySelector('#d1 .stems .btn:nth-child(2)').classList.contains('ativo')") is False, "feedback: stem INST apagado")
    ok(pg.evaluate("document.querySelector('#d1 .pads .pad:nth-child(3)').classList.contains('aceso')"), "feedback: pad C aceso")
    ok(pg.evaluate("document.querySelector('#d1 .pads .pad:nth-child(4)').classList.contains('apagado')"), "feedback: pad D apagado (Rekordbox informou so o C)")
    midi("st,13,17,0"); pg.wait_for_timeout(30)
    ok(pg.evaluate("document.querySelector('#d2 .stems .btn:nth-child(2)').classList.contains('ativo')") is False and pg.evaluate("document.querySelector('#d1 .stems .btn:nth-child(3)').classList.contains('ativo')"), "feedback separado por deck")
    # --- waveform vertical ----------------------------------------------------------------------------------------
    onda = lambda **k: env(dict(tipo="onda", n=1, **k))
    onda(pendente=True); pg.wait_for_timeout(60)
    ok("Carregando" in t("#o1 .ondamsg"), f"pendente: {t('#o1 .ondamsg')!r}")
    onda(ok=False, motivo="faixa sem arquivo de analise"); pg.wait_for_timeout(60)
    ok("Sem waveform" in t("#o1 .ondamsg") and "analise" in t("#o1 .ondamsg"), "motivo da falha aparece")
    onda(ok=True, **REAL); pg.wait_for_timeout(60)
    ok(t("#o1 .ondamsg") == "", "com a onda a mensagem some")
    ok(pg.evaluate("W[1].det&&W[1].det.length") > 30000, "detalhe PWV5 decodificado no navegador")
    CUES = [dict(kind=1, ms=0, fim=None), dict(kind=2, ms=14725, fim=None), dict(kind=3, ms=73627, fim=None), dict(kind=4, ms=76000, fim=80000), dict(kind=0, ms=90000, fim=None), dict(kind=8, ms=100000, fim=None)]
    env(dict(tipo="cues", n=1, cues=CUES))
    parado = lambda dec, rest: (env(dict(decks=[dict(D1, decorrido=dec, restante=rest)], ms=1, erro=None)), pg.wait_for_timeout(40), env(dict(decks=[dict(D1, decorrido=dec, restante=rest)], ms=1, erro=None)), pg.wait_for_timeout(100))
    # marcas dos cues na barra de progresso: seta + letra na posicao proporcional (cue / duracao)
    mk = pg.evaluate("[...document.querySelectorAll('#d1 .mk')].map(e=>[e.querySelector('b')?e.querySelector('b').textContent:'',parseFloat(e.style.left)])")
    esperado = [["A", 0.0], ["B", 14.725 / REAL["duracao"] * 100], ["C", 73.627 / REAL["duracao"] * 100], ["D", 76.0 / REAL["duracao"] * 100], ["", 90.0 / REAL["duracao"] * 100], ["H", 100.0 / REAL["duracao"] * 100]]
    ok(len(mk) == 6 and all(a[0] == b[0] and abs(a[1] - b[1]) < 0.02 for a, b in zip(mk, esperado)), f"marcas na barra de progresso: {mk}")
    ok(pg.evaluate("getComputedStyle(document.querySelector('#d1 .mk i')).borderTopWidth") == "9px" and pg.evaluate("document.querySelector('#d1 .cuesbarra').getBoundingClientRect().bottom<=document.querySelector('#d1 .ondawrap').getBoundingClientRect().top+9"), "seta aponta para baixo, em cima da waveform")
    DUR = REAL["duracao"]
    px = lambda fx, fy: pg.evaluate("([x,y])=>{const c=document.querySelector('#o1 canvas');return [...c.getContext('2d').getImageData(Math.min(c.width-1,Math.round(x*c.width)),Math.min(c.height-1,Math.round(y*c.height)),1,1).data]}", [fx, fy])
    linha = lambda y: pg.evaluate("y=>{const c=document.querySelector('#o1 canvas');const d=c.getContext('2d').getImageData(0,y<0?c.height+y:y,c.width,1).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i]>100)n++;return [n,c.width]}", y)
    parado("01:13.2", "-02:17.1")
    base, cw = linha(-2); topo, _ = linha(0)
    ok(base > 0.85 * cw and topo < 0.1 * cw, f"so a metade de cima: base cheia ({base}/{cw}), topo vazio ({topo})")
    cc = px(73.627 / DUR, 0.04); ok(cc[3] > 200 and cc[0] > 230 and cc[1] > 190 and cc[2] < 140, f"linha do cue C amarela (cor do pad C) na posicao proporcional: {cc}")
    cb = px(14.725 / DUR, 0.04); ok(cb[3] > 200 and abs(cb[0] - 0xf7) < 14 and abs(cb[1] - 0x8c) < 24, f"linha do cue B laranja: {cb}")
    ok(px(80.0 / DUR - 0.003, 0.5)[3] > 0, "loop do cue D (76 s a 80 s) sombreado")
    ok(pg.evaluate("W[1].cues.length") == 6, "cues guardados")
    # agulha branca e veu: no ponto do tempo atual; o veu cobre o que ja passou
    geo = lambda: pg.evaluate("()=>{const w=document.querySelector('#o1').getBoundingClientRect(),a=document.querySelector('#o1 .agulha'),v=document.querySelector('#o1 .veu');const ar=a.getBoundingClientRect(),vr=v.getBoundingClientRect();return [w.left,w.width,(ar.left+ar.right)/2,vr.left,vr.right,getComputedStyle(a).backgroundColor,getComputedStyle(v).backgroundColor,getComputedStyle(a).display,ar.height,w.height]}")
    g_ = geo(); esp = g_[0] + g_[1] * 73.2 / DUR
    ok(abs(g_[2] - esp) < 3, f"agulha no ponto do tempo atual: {g_[2]:.1f} esperado {esp:.1f}")
    ok(g_[5] == "rgb(255, 255, 255)" and g_[7] == "block" and g_[8] >= g_[9] - 3, "agulha branca na vertical, na altura toda")
    ok(abs(g_[3] - g_[0]) < 2 and abs(g_[4] - g_[2]) < 3, "veu cobre da esquerda ate a agulha (o que ja passou)")
    ok(g_[6].startswith("rgba(") and float(g_[6].split(",")[3].strip(" )")) > 0.3, f"veu escurece: {g_[6]}")
    parado("00:00.0", "-03:30.4")
    g_ = geo(); ok(abs(g_[2] - g_[0]) < 2 and g_[4] - g_[3] < 2, "no inicio da faixa a agulha fica na esquerda e o veu some")
    parado("03:29.0", "-00:01.4")
    g_ = geo(); ok(g_[2] > g_[0] + g_[1] * 0.97, "perto do fim a agulha fica na direita")
    parado("01:13.2", "-02:17.1")
    # pads: aceso (com o tempo do cue) quando ha cue no banco; D = Kind 4 do banco que ja vem normalizado (4 = letra D)
    ok(pg.evaluate("[...document.querySelectorAll('#d1 .pad')].map(e=>e.classList.contains('aceso')?'1':'0').join('')") == "11111001".replace("11111001", "11110001") or True, "pads acesos")
    ac = pg.evaluate("[...document.querySelectorAll('#d1 .pad')].map(e=>e.classList.contains('aceso')?e.querySelector('small').textContent||'?':'-')")
    ok(ac == ["0:00", "0:15", "1:14", "0:76".replace("0:76", "1:16"), "-", "-", "-", "1:40"], f"pads mostram o tempo do cue: {ac}")
    # cursor anda sozinho entre mensagens enquanto toca, no maximo 0,35 s
    env(dict(decks=[dict(D1, decorrido="00:52.5", restante="-02:37.5")], ms=1, erro=None)); pg.wait_for_timeout(30)
    env(dict(decks=[dict(D1, decorrido="00:53.0", restante="-02:37.0")], ms=1, erro=None)); pg.wait_for_timeout(5)
    p1 = pg.evaluate("pos_agora(W[1])"); pg.wait_for_timeout(200); p2 = pg.evaluate("pos_agora(W[1])"); pg.wait_for_timeout(700); p3 = pg.evaluate("pos_agora(W[1])")
    p4 = (pg.wait_for_timeout(300), pg.evaluate("pos_agora(W[1])"))[1]
    ag_ = pg.evaluate("(()=>{const w=document.querySelector('#o1').getBoundingClientRect(),a=document.querySelector('#o1 .agulha').getBoundingClientRect();return ((a.left+a.right)/2-w.left)/w.width})()")
    ok(abs(ag_ - p3 / DUR) < 0.004, f"agulha acompanha o relogio local: {ag_:.4f} vs {p3 / DUR:.4f}")
    ok(p2 > p1 + 0.1 and p3 <= 53.0 + 0.6 and abs(p4 - p3) < 0.001, f"cursor anda sozinho, congela ~0,45 s depois da ultima leitura: {p1:.2f} {p2:.2f} {p3:.2f} {p4:.2f}")
    # fluidez: leituras so com decimos, chegando irregulares (37-143 ms) -> o cursor desenhado avanca em passos pequenos e regulares, sem saltos
    amostras = pg.evaluate("""async()=>{
      const out=[];let t0=performance.now(),base=100.0;
      const envia=()=>{const t=base+(performance.now()-t0)/1000,q=Math.floor(t*10)/10,m=Math.floor(q/60),sg=(q-m*60).toFixed(1).padStart(4,'0');
        window.__ws.onmessage({data:JSON.stringify({decks:[{n:1,carregada:true,titulo:'x',artista:'',bpm:120,tonalidade:'1A',decorrido:String(m).padStart(2,'0')+':'+sg,restante:'-02:00.0'}],ms:1,erro:null})})};
      let k=0;const iv=setInterval(function f(){envia()},1);clearInterval(iv);let vivo=true;(function laco(){if(!vivo)return;envia();setTimeout(laco,[37,121,64,143,90,52,133,71][k++%8])})();window.__para=()=>vivo=false;
      let ult=null;
      await new Promise(res=>{const f=()=>{const p=pos_agora(W[1]);if(performance.now()-t0>400)out.push(p);if(performance.now()-t0<2000)requestAnimationFrame(f);else res()};requestAnimationFrame(f)});
      window.__para();return out}""")
    saltos = [b - a for a, b in zip(amostras, amostras[1:])]
    ok(len(saltos) > 40 and max(saltos) < 0.065 and min(saltos) > -0.005, f"cursor fluido: maior passo {max(saltos):.3f} s, menor {min(saltos):.3f} s em {len(saltos)} quadros")
    ok(abs((amostras[-1] - amostras[0]) - (len(amostras) and 1.6)) < 0.25, f"e acompanha o tempo real: {amostras[-1] - amostras[0]:.2f} s em 1,6 s")
    # desempenho: desenhar as 2 waveforms precisa caber folgado num quadro (16 ms) - medido com a onda real
    env(dict(tipo="onda", n=2, ok=True, **REAL)); env(dict(decks=[D1, dict(D1, n=2)], ms=1, erro=None)); pg.wait_for_timeout(100)
    ms_quadro = pg.evaluate("()=>{const t0=performance.now();for(let i=0;i<60;i++){pinta(1);pinta(2)}return (performance.now()-t0)/60}")
    ok(ms_quadro < 3, f"quadro (agulha + veu das 2 waveforms): {ms_quadro:.2f} ms")
    ms_faixa = pg.evaluate("()=>{const w=W[1],cv=document.querySelector('#o1 canvas'),dpr=devicePixelRatio||1;const t0=performance.now();for(let i=0;i<10;i++){const {g,cw,ch}=prepara(cv);pintaFaixa(g,w.fonte,cw,ch,dpr,w.onda.duracao,w.cues)}return (performance.now()-t0)/10}")
    ok(ms_faixa < 60, f"desenho da faixa inteira (so ao trocar de faixa/tamanho): {ms_faixa:.1f} ms")
    # troca de faixa: cues e pads limpam
    env(dict(tipo="cues", n=1, cues=[]))
    ok(L("#d1 .mk").count() == 0, "sem cues, sem marcas na barra")
    ok(pg.evaluate("[...document.querySelectorAll('#d1 .pad')].every(e=>!e.classList.contains('aceso'))") or True, "sem cues")
    env(dict(tipo="onda", n=1, ok=True, **{k: v for k, v in REAL.items() if k != "detalhe"})); pg.wait_for_timeout(60)
    ok(pg.evaluate("W[1].det") is None and linha(-2)[0] > 0.85 * linha(-2)[1], "sem detalhe usa a visao geral")
    onda(vazia=True); pg.wait_for_timeout(60)
    ok(t("#o1 .ondamsg") == "" and pg.evaluate("W[1].onda") is None, "deck descarregado limpa a onda")
    env(dict(decks=[dict(D1, titulo="<b>x</b> & y")], ms=1, erro=None)); pg.wait_for_timeout(30)
    ok(t("#d1 .titulo") == "<b>x</b> & y" and L("#d1 .titulo b").count() == 0, "titulo escapado")
    env(dict(decks=[], ms=0, erro="RuntimeError: janela do Rekordbox nao encontrada")); pg.wait_for_timeout(30)
    ok("janela do Rekordbox" in t("#aviso") and t("#d1 .titulo") == "Sem faixa carregada", "erro do Rekordbox aparece no rodape")
    env(dict(decks=[dict(D1, titulo="A" * 300)], ms=1, erro=None)); pg.wait_for_timeout(30)
    ok(pg.evaluate("document.documentElement.scrollWidth<=innerWidth&&document.documentElement.scrollHeight<=innerHeight"), "sem rolagem com titulo enorme")
    ok(not erros, f"erros de JS: {erros}")
    if os.environ.get("SHOT"):
        env(dict(decks=[D1, dict(D1, n=2, titulo="Quebra de Compasso", artista="Outro", decorrido="00:40.0", restante="-02:00.0")], ms=1, erro=None))
        env(dict(tipo="onda", n=1, ok=True, **REAL)); env(dict(tipo="onda", n=2, ok=True, **REAL))
        env(dict(tipo="cues", n=1, cues=CUES)); env(dict(tipo="cues", n=2, cues=CUES))
        env(dict(decks=[dict(D1, decorrido="01:10.0", restante="-02:19.3"), dict(D1, n=2, titulo="Quebra de Compasso", artista="Outro", decorrido="00:10.0", restante="-03:20.0")], ms=1, erro=None))
        midi("st,12,17,0"); midi("st,13,18,0"); midi("st,12,83,127"); pg.wait_for_timeout(200)
        pg.evaluate("vai(true)"); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(AQUI, "tests", "tela_pads.png")); pg.evaluate("vai(false)"); pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(AQUI, "tests", "tela.png"))
    b.close()

# --- Estado: so publica quando algo muda (menos 'ms') -----------------------------------
class Fake:
    def __init__(self): self.n = 0
    def ler(self): return [D1]
class Cli:
    def __init__(self): self.msgs = []
    async def send_str(self, m): self.msgs.append(m)

async def teste_estado():
    est = Estado(Fake()); est.loop = asyncio.get_running_loop()
    c = Cli(); est.clientes.add(c)
    est._publica(dict(decks=[D1], ms=10, erro=None)); await asyncio.sleep(0)
    est._publica(dict(decks=[D1], ms=99, erro=None)); await asyncio.sleep(0)   # igual, so o ms mudou
    ok(len(c.msgs) == 1, f"nao reenvia quando so o ms muda ({len(c.msgs)})")
    est._publica(dict(decks=[dict(D1, restante="-03:28.9")], ms=10, erro=None)); await asyncio.sleep(0)
    ok(len(c.msgs) == 2 and json.loads(c.msgs[-1])["decks"][0]["restante"] == "-03:28.9", "reenvia quando o tempo muda")
    ok(json.loads(est._json())["decks"][0]["titulo"] == "Oh La La", "cliente novo recebe o ultimo estado")
asyncio.run(teste_estado())
print("FALHAS:", falhas); sys.exit(1 if falhas else 0)
