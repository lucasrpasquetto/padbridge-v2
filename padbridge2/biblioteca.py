"""Acha a faixa carregada no banco do Rekordbox e le a waveform dela.

O banco so abre com o pyrekordbox, que pode nao estar no Python do PadBridge: por isso roda num processo ajudante
(`ajudante_db.py`) com o Python que o tem (padrao: o venv do rekordbox-mcp). Tudo aqui e bloqueante: chame de uma thread.
"""
import json, os, queue, subprocess, sys, threading

from . import anlz

AQUI = os.path.dirname(os.path.abspath(__file__))


def python_padrao():
    """PADBRIDGE_PYTHON_DB, ou o venv do rekordbox-mcp na pasta do usuario."""
    env = os.environ.get("PADBRIDGE_PYTHON_DB")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), "rekordbox-mcp", ".venv", "Scripts", "python.exe")


class Biblioteca:
    def __init__(self, comando=None, timeout=30):
        self.comando = comando or [python_padrao(), os.path.join(AQUI, "ajudante_db.py")]
        self.timeout = timeout
        self._p = None
        self._q = queue.Queue()
        self._trava = threading.Lock()
        self._n = 0
        self._cache = {}

    def _inicia(self):
        self._p = subprocess.Popen(self.comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, encoding="utf-8", bufsize=1)
        threading.Thread(target=self._le, args=(self._p,), daemon=True).start()
        self._q.get(timeout=self.timeout)       # {"pronto": true}

    def _le(self, p):
        for linha in p.stdout:
            try:
                self._q.put(json.loads(linha))
            except ValueError:
                pass
        self._q.put({"morreu": True})

    def _pergunta(self, ped):
        with self._trava:
            if self._p is None or self._p.poll() is not None:
                while not self._q.empty():
                    self._q.get_nowait()
                self._inicia()
            self._n += 1
            ped = dict(ped, id=self._n)
            self._p.stdin.write(json.dumps(ped, ensure_ascii=False) + "\n")
            self._p.stdin.flush()
            while True:
                r = self._q.get(timeout=self.timeout)
                if r.get("morreu"):
                    raise RuntimeError("o ajudante de banco encerrou")
                if r.get("id") == self._n:
                    return r

    def onda(self, titulo, artista="", bpm=None, tom=None):
        """{"ok": True, "onda": {...}} ou {"ok": False, "motivo": "..."}. Resultados ficam em cache."""
        chave = (titulo, artista or "", bpm, tom)
        if chave in self._cache:
            return self._cache[chave]
        try:
            r = self._pergunta(dict(titulo=titulo, artista=artista, bpm=bpm, tom=tom))
            if r.get("ok"):
                res = {"ok": True, "faixa": r["faixa"], "onda": anlz.carrega(r["dat"], r.get("ext"))}
            else:
                res = {"ok": False, "motivo": r.get("motivo", "?")}
        except Exception as e:
            res = {"ok": False, "motivo": f"{type(e).__name__}: {e}"[:200]}
            self.fecha()
            return res                          # erro de infraestrutura nao vai para o cache
        self._cache[chave] = res
        return res

    def cues(self, faixa):
        """Lista de cues da faixa (sem cache: o usuario cria/apaga cues durante o set). None se der erro."""
        try:
            r = self._pergunta(dict(cmd="cues", faixa=faixa))
            return r["cues"] if r.get("ok") else None
        except Exception:
            self.fecha()
            return None

    def fecha(self):
        p, self._p = self._p, None
        if p is None:
            return
        for f in (p.stdin,):
            try:
                f.close()
            except OSError:
                pass                            # pipe ja quebrado: o ajudante morreu
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=3)
        except Exception:
            p.kill()
        try:
            p.stdout.close()
        except OSError:
            pass
