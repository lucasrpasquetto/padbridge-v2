"""Descobre ONDE o Rekordbox guarda o arquivo de analise (waveform) de uma faixa. Somente leitura.

Rode com o Python do rekordbox-mcp (ele ja tem o pyrekordbox):
  C:\\Users\\Lucas\\rekordbox-mcp\\.venv\\Scripts\\python.exe sondas\\achar_analise.py "Oh La La" "2 Eivissa"
"""
import os, sys

if len(sys.argv) < 2:
    sys.exit('uso: achar_analise.py "titulo" ["artista"]')
titulo = sys.argv[1]
artista = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower()

from pyrekordbox import Rekordbox6Database
db = Rekordbox6Database()
achados = [c for c in db.get_content(Title=titulo)]
if artista:
    achados = [c for c in achados if (getattr(c, "ArtistName", "") or "").strip().lower() == artista] or achados
print(f"{len(achados)} faixa(s) com o titulo {titulo!r}")
base = os.path.join(os.environ.get("APPDATA", ""), "Pioneer", "rekordbox", "share")
print("pasta share padrao:", base, "existe:", os.path.isdir(base))
for c in achados[:5]:
    ap = getattr(c, "AnalysisDataPath", None)
    print("-" * 70)
    print("ID:", c.ID, "| Titulo:", c.Title, "| Artista:", getattr(c, "ArtistName", None), "| Length:", getattr(c, "Length", None), "s")
    print("FolderPath:", getattr(c, "FolderPath", None))
    print("AnalysisDataPath:", repr(ap))
    if ap:
        cand = os.path.join(base, ap.lstrip("/\\").replace("/", os.sep))
        print("  -> arquivo:", cand, "existe:", os.path.exists(cand))
    for nome in ("get_anlz_dir", "get_anlz_path"):
        f = getattr(db, nome, None)
        if f:
            try:
                r = f(c) if nome == "get_anlz_dir" else f(c, "DAT")
                print(f"  {nome}:", r, "existe:", os.path.exists(str(r)) if r else None)
            except Exception as e:
                print(f"  {nome}: erro {type(e).__name__}: {e}")
