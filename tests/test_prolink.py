import os, sys, collections
AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(AQUI, "sondas"))
import prolink_sniff as ps
falhas = 0
def ok(c, m):
    global falhas
    if not c: falhas += 1; print("FALHA:", m)

def pacote(tipo, nome=b"rekordbox", dev=0x11, tam=0x40):
    b = bytearray(tam); b[:10] = ps.MAGIC; b[0x0A] = tipo; b[0x0B:0x0B + len(nome)] = nome; b[0x21] = dev
    return bytes(b)

i = ps.decodifica(50002, pacote(0x0A))
ok(i["tipo"] == 0x0A and i["nome"] == "rekordbox" and i["dev"] == 0x11 and "status" in i["rotulo"], f"cabecalho: {i}")
ok(ps.decodifica(50000, b"nada aqui") is None and ps.decodifica(50000, ps.MAGIC) is None, "lixo e pacote curto viram None")
st = bytearray(pacote(0x0A, tam=0xD4)); st[0x28] = 3; st[0x29] = 2; st[0x2C:0x30] = (1234).to_bytes(4, "big"); st[0x7B] = 0x7A; st[0x92:0x94] = (12800).to_bytes(2, "big")
c = ps.campos_status(bytes(st))
ok(c["player_fonte"] == 3 and c["id_rekordbox"] == 1234 and c["bpm_faixa"] == 128.0 and c["estado_play"] == 0x7A, f"campos de status: {c}")
ok(ps.campos_status(pacote(0x0A)) == {}, "status curto nao quebra")
resumo, am = collections.Counter(), []
for _ in range(10): ps.processa(50002, bytes(st), "192.168.0.7", resumo, am)
ps.processa(50000, b"lixo", "10.0.0.1", resumo, am)
ok(sum(resumo.values()) == 11 and len(am) == 4, f"resumo/amostras: {sum(resumo.values())} {len(am)} (3 amostras + 1 lixo)")
ok("campos_documentados" in am[0] and "hex" in am[0], "amostra guarda hex e campos")
ps.imprime(resumo)
print("FALHAS:", falhas); sys.exit(1 if falhas else 0)
