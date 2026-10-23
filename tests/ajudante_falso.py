"""Ajudante de banco falso para testes: mesmo protocolo, mas com 2 faixas fixas apontando para os ANLZ de teste."""
import os, sys
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from padbridge2 import ajudante_db
F = os.path.join(RAIZ, "tests", "fixtures", "anlz")

class Falso:
    def candidatos(self, titulo):
        if titulo == "Oh La La":
            return [dict(id=1, artista="2 Eivissa", bpm=125.0, tom="1A", dat=os.path.join(F, "ANLZ0000.DAT"), ext=None),
                    dict(id=2, artista="2 Eivissa", bpm=130.46, tom="5A", dat=os.path.join(F, "ANLZ0000.DAT"), ext=os.path.join(F, "ANLZ0000.EXT"))]
        if titulo == "Sem Analise":
            return [dict(id=3, artista="X", bpm=100.0, tom="", dat=None, ext=None)]
        if titulo == "Quebra":
            raise RuntimeError("banco travado")
        return []

    def cues(self, faixa):
        return [dict(kind=1, ms=0, fim=None, comentario=""), dict(kind=2, ms=14725, fim=None, comentario=""), dict(kind=3, ms=73627, fim=None, comentario="")] if faixa == 2 else []

ajudante_db.main(Falso())
