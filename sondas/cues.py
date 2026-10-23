"""Mostra os cues (hot cues A-H, memory cues, loops) que o Rekordbox guardou no banco para uma faixa. Somente leitura.

  C:\\Users\\Lucas\\rekordbox-mcp\\.venv\\Scripts\\python.exe sondas\\cues.py "Oh La La" "2 Eivissa"
"""
import sys, warnings
warnings.filterwarnings("ignore")
if len(sys.argv) < 2:
    sys.exit('uso: cues.py "titulo" ["artista"]')
titulo = sys.argv[1]
artista = (sys.argv[2] if len(sys.argv) > 2 else "").strip().lower()

try:
    from pyrekordbox.masterdb import MasterDatabase as DB
except Exception:
    from pyrekordbox import Rekordbox6Database as DB
db = DB()
achados = list(db.get_content(Title=titulo))
if artista:
    achados = [c for c in achados if (getattr(c, "ArtistName", "") or "").strip().lower() == artista] or achados
for c in achados[:5]:
    print("=" * 70)
    print("faixa", c.ID, "|", c.Title, "|", getattr(c, "ArtistName", ""), "| BPM", (c.BPM or 0) / 100, "|", c.Length, "s")
    try:
        cues = list(db.get_cue(ContentID=c.ID))
    except Exception as e:
        cues = list(getattr(c, "Cues", []) or [])
        print("(get_cue falhou:", type(e).__name__, e, ")")
    print(len(cues), "cue(s)")
    for q in cues:
        cols = {k.name: getattr(q, k.name, None) for k in q.__table__.columns}
        uteis = {k: v for k, v in cols.items() if v not in (None, "", -1) and k not in ("UUID", "rb_data_status", "rb_local_data_status", "rb_local_deleted", "rb_local_synced", "usn", "rb_local_usn", "created_at", "updated_at")}
        print("  ", uteis)
