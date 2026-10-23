"""Ajudante de banco: roda com o Python que tem o pyrekordbox (o do rekordbox-mcp) e responde pedidos por stdin/stdout.

Protocolo (uma linha JSON por mensagem):
  pedido:   {"id": 1, "titulo": "Oh La La", "artista": "2 Eivissa", "bpm": 130.46, "tom": "5A"}
  pedido de cues: {"id": 2, "cmd": "cues", "faixa": 160066392} -> {"id": 2, "ok": true, "cues": [{"kind": 1, "ms": 0, "fim": null, "comentario": ""}]}
                  (kind 0 = memory cue; 1..16 = hot cue A..P; fim != null = loop)
  resposta: {"id": 1, "ok": true, "faixa": 160066392, "dat": "D:\\...\\ANLZ0000.DAT", "ext": "...|null", "candidatos": 2}
         ou {"id": 1, "ok": false, "motivo": "..."}
So le o banco; nao grava nada.
"""
import json, os, sys


def kind_para_hotcue(kind):
    """DjmdCue.Kind -> 0 memory cue, 1..N hot cue A.. ; None = nao e cue do usuario.
    Medido no Rekordbox 7.2: A,B,C = Kind 1,2,3 mas D,E,F,G = Kind 5,6,7,8 (o Kind 4 nao e hot cue), entao Kind >= 5 vale Kind-1."""
    if kind <= 0:
        return 0
    if kind == 4:
        return None
    return kind if kind < 4 else kind - 1


def escolhe(cands, artista="", bpm=None, tom=None):
    """Escolhe a faixa certa entre as de mesmo titulo. cands: lista de dicts com artista, bpm, tom, dat."""
    if not cands:
        return None
    art = (artista or "").strip().casefold()
    lista = [c for c in cands if (c.get("artista") or "").strip().casefold() == art] or cands
    lista = [c for c in lista if c.get("dat")] or lista

    def nota(c):
        s = 0
        if bpm is not None and abs((c.get("bpm") or 0) - bpm) < 0.05:
            s += 2
        if tom and (c.get("tom") or "").strip().upper() == tom.strip().upper():
            s += 1
        return -s                               # menor e melhor; empate mantem a ordem do banco
    return sorted(lista, key=nota)[0]


class BackendPyrekordbox:
    def __init__(self):
        try:
            from pyrekordbox.masterdb import MasterDatabase as DB
        except Exception:
            from pyrekordbox import Rekordbox6Database as DB
        self.db = DB()

    def candidatos(self, titulo):
        out = []
        for c in self.db.get_content(Title=titulo):
            dat = self._caminho(c, "DAT")
            out.append(dict(id=c.ID, artista=getattr(c, "ArtistName", "") or "", bpm=(getattr(c, "BPM", 0) or 0) / 100.0,
                            tom=getattr(c, "KeyName", "") or "", dat=dat, ext=self._caminho(c, "EXT") if dat else None))
        return out

    def cues(self, faixa):
        out = []
        for q in self.db.get_cue(ContentID=str(faixa)):
            if getattr(q, "rb_local_deleted", 0):
                continue
            fim = getattr(q, "OutMsec", None)
            k = kind_para_hotcue(int(q.Kind or 0))
            if k is None:
                continue
            out.append(dict(kind=k, ms=int(q.InMsec or 0), fim=int(fim) if fim not in (None, -1) else None,
                            comentario=getattr(q, "Comment", "") or ""))
        return sorted(out, key=lambda x: (x["ms"], x["kind"]))

    def _caminho(self, c, tipo):
        try:
            p = self.db.get_anlz_path(c, tipo)
            return str(p) if p and os.path.exists(str(p)) else None
        except Exception:
            return None


def responde(backend, ped):
    try:
        if ped.get("cmd") == "cues":
            return dict(id=ped.get("id"), ok=True, cues=backend.cues(ped["faixa"]))
        cands = backend.candidatos(ped["titulo"])
        c = escolhe(cands, ped.get("artista", ""), ped.get("bpm"), ped.get("tom"))
        if c is None:
            return dict(id=ped.get("id"), ok=False, motivo="faixa nao encontrada no banco")
        if not c.get("dat"):
            return dict(id=ped.get("id"), ok=False, motivo="faixa sem arquivo de analise (nao analisada?)")
        return dict(id=ped.get("id"), ok=True, faixa=c["id"], dat=c["dat"], ext=c.get("ext"), candidatos=len(cands))
    except Exception as e:
        return dict(id=ped.get("id"), ok=False, motivo=f"{type(e).__name__}: {e}"[:200])


def main(backend=None):
    backend = backend or BackendPyrekordbox()
    print(json.dumps({"pronto": True}), flush=True)
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        print(json.dumps(responde(backend, json.loads(linha)), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
