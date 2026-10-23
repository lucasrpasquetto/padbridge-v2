"""Servidor da v2: le os decks do Rekordbox continuamente e envia ao tablet por WebSocket.

- GET /      -> tela (web/index.html)
- GET /ws    -> WebSocket; cada mensagem e um JSON {"decks":[...], "ms":123, "erro":null}
Um cliente novo recebe de imediato o ultimo estado. So envia quando algo muda.
"""
import asyncio, json, os, socket, threading, time

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class Estado:
    """Guarda o ultimo estado lido e avisa os clientes quando muda. A leitura roda numa thread (UIA e bloqueante)."""

    def __init__(self, leitor, intervalo=0.08, biblioteca=None, cue_intervalo=2.0):
        self.leitor, self.intervalo, self.biblioteca = leitor, intervalo, biblioteca
        self.cue_intervalo = cue_intervalo
        self.cues = {}                   # n do deck -> ultima lista de cues enviada
        self._faixa_id = {}              # n do deck -> id da faixa no banco (depois que a waveform chegou)
        self._cue_t, self._cue_ocupado = {}, set()
        self.ondas = {}                  # n do deck -> ultima mensagem de waveform (para clientes novos)
        self._faixa_vista = {}           # n do deck -> (titulo, artista) ja tratado
        self._pool = None
        self.atual = {"decks": [], "ms": 0, "erro": "iniciando..."}
        self.clientes = set()
        self.loop = None
        self._parar = threading.Event()

    def _json(self):
        return json.dumps(self.atual, ensure_ascii=False)

    def _publica(self, novo):
        # compara sem o tempo de leitura, que muda sempre
        if {k: v for k, v in novo.items() if k != "ms"} == {k: v for k, v in self.atual.items() if k != "ms"}:
            self.atual["ms"] = novo["ms"]
            return
        self.atual = novo
        msg = self._json()
        for ws in list(self.clientes):
            asyncio.ensure_future(self._envia(ws, msg))

    # --- waveform: busca no banco quando a faixa de um deck muda (em outra thread; o banco e lento) ----------
    def _atualiza_ondas(self, decks):
        if self.biblioteca is None:
            return
        for d in decks:
            n = d["n"]
            chave = (d["titulo"], d["artista"] or "") if d["carregada"] else None
            if chave == self._faixa_vista.get(n):
                continue
            self._faixa_vista[n] = chave
            if chave is None:
                self._avisa(self._publica_onda, n, None, None)
            else:
                self._avisa(self._publica_onda, n, chave, {"pendente": True})
                self._pool.submit(self._busca, n, chave, d.get("bpm_faixa") or d["bpm"], d["tonalidade"])   # BPM da faixa (nao o do pitch) para achar a faixa certa no banco
        agora = time.time()                      # cues mudam durante o set (o DJ cria e apaga): relê de tempos em tempos
        for d in decks:
            n, fid = d["n"], self._faixa_id.get(d["n"])
            if d["carregada"] and fid is not None and n not in self._cue_ocupado and agora - self._cue_t.get(n, 0) >= self.cue_intervalo:
                self._cue_ocupado.add(n)
                self._cue_t[n] = agora
                self._pool.submit(self._busca_cues, n, (d["titulo"], d["artista"] or ""), fid)

    def _busca(self, n, chave, bpm, tom):
        res = self.biblioteca.onda(chave[0], chave[1], bpm, tom)
        self._avisa(self._publica_onda, n, chave, res)

    def _busca_cues(self, n, chave, fid):
        try:
            lista = self.biblioteca.cues(fid)
        finally:
            self._cue_ocupado.discard(n)
        self._avisa(self._publica_cues, n, chave, lista)

    def _publica_cues(self, n, chave, lista):
        if self._faixa_vista.get(n) != chave or lista is None or self.cues.get(n) == lista:
            return
        self.cues[n] = lista
        texto = json.dumps(dict(tipo="cues", n=n, cues=lista), ensure_ascii=False)
        for ws in list(self.clientes):
            asyncio.ensure_future(self._envia(ws, texto))

    def _avisa(self, f, *a):
        try:
            self.loop.call_soon_threadsafe(f, *a)
        except RuntimeError:             # servidor ja fechou
            self._parar.set()

    def _publica_onda(self, n, chave, res):
        if self._faixa_vista.get(n) != chave:
            return                       # a faixa ja mudou de novo; resultado velho
        if res is None or res.get("pendente"):
            self._faixa_id.pop(n, None)
            self._cue_t.pop(n, None)
            if self.cues.pop(n, None):           # cues da faixa anterior somem da tela
                texto = json.dumps(dict(tipo="cues", n=n, cues=[]))
                for ws in list(self.clientes):
                    asyncio.ensure_future(self._envia(ws, texto))
        if res is None:
            msg = dict(tipo="onda", n=n, vazia=True)
        elif res.get("pendente"):
            msg = dict(tipo="onda", n=n, pendente=True)
        elif res["ok"]:
            self._faixa_id[n] = res["faixa"]
            msg = dict(tipo="onda", n=n, ok=True, **res["onda"])
        else:
            msg = dict(tipo="onda", n=n, ok=False, motivo=res["motivo"])
        self.ondas[n] = msg
        texto = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.clientes):
            asyncio.ensure_future(self._envia(ws, texto))

    @staticmethod
    async def _envia(ws, msg):
        try:
            await ws.send_str(msg)
        except Exception:
            pass

    def _laco(self):
        while not self._parar.is_set():
            t0 = time.time()
            try:
                decks, erro = self.leitor.ler(), None
            except Exception as e:           # Rekordbox fechado, janela minimizada...
                decks, erro = [], f"{type(e).__name__}: {e}"[:160]
            novo = {"decks": decks, "ms": round((time.time() - t0) * 1000), "erro": erro, "modo": getattr(self.leitor, "modo", None)}
            self._avisa(self._publica, novo)
            if not erro:
                self._atualiza_ondas(decks)
            self._parar.wait(self.intervalo)

    def inicia(self, loop):
        self.loop = loop
        if self.biblioteca is not None:
            from concurrent.futures import ThreadPoolExecutor
            self._pool = ThreadPoolExecutor(max_workers=1)
        threading.Thread(target=self._laco, daemon=True).start()

    def para(self):
        self._parar.set()
        if self._pool:
            self._pool.shutdown(wait=False, cancel_futures=True)
        if self.biblioteca is not None:
            self.biblioteca.fecha()


async def pagina(_):
    from aiohttp import web
    return web.FileResponse(os.path.join(WEB, "index.html"), headers={"Cache-Control": "no-store"})


async def ws_handler(req):
    from aiohttp import web, WSMsgType
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(req)
    est = req.app["estado"]
    est.clientes.add(ws)
    await ws.send_str(est._json())
    for msg in list(est.ondas.values()):
        await ws.send_str(json.dumps(msg, ensure_ascii=False))
    for n, lista in list(est.cues.items()):
        await ws.send_str(json.dumps(dict(tipo="cues", n=n, cues=lista), ensure_ascii=False))
    try:
        async for m in ws:
            if m.type == WSMsgType.ERROR:
                break
    finally:
        est.clientes.discard(ws)
    return ws


def cria_app(leitor, intervalo=0.08, biblioteca=None):
    from aiohttp import web
    app = web.Application()
    app["estado"] = Estado(leitor, intervalo, biblioteca)
    app.router.add_get("/", pagina)
    app.router.add_get("/ws", ws_handler)

    async def liga(a):
        a["estado"].inicia(asyncio.get_running_loop())

    async def desliga(a):
        a["estado"].para()
    app.on_startup.append(liga)
    app.on_cleanup.append(desliga)
    return app


def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def _prepara_loop():
    """Loop de eventos mais robusto no Windows (o Proactor do Python 3.15 jogou InvalidStateError quando o tablet
    caiu/dormiu) e com erros inesperados registrados em padbridge2.log em vez de derrubar tudo."""
    import logging, sys, warnings
    logging.basicConfig(filename=os.path.join(os.getcwd(), "padbridge2.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    if sys.platform == "win32":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            except Exception:
                pass
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def erro(lp, ctx):
        logging.error("erro no loop: %s", ctx.get("message"), exc_info=ctx.get("exception"))
        print("(erro interno registrado em padbridge2.log:", ctx.get("message"), ")")
    loop.set_exception_handler(erro)
    return loop


def roda(leitor, porta=8766, biblioteca=None):
    from aiohttp import web
    print(f"PadBridge v2 no ar. No tablet abra:\n  USB (com adb reverse tcp:{porta} tcp:{porta}):  http://localhost:{porta}\n  Wi-Fi:  http://{ip_local()}:{porta}")
    web.run_app(cria_app(leitor, biblioteca=biblioteca), host="0.0.0.0", port=porta, print=None, loop=_prepara_loop())
