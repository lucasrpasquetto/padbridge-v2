"""Leitor dos arquivos de analise do Rekordbox (ANLZ0000.DAT / .EXT). Somente leitura, sem dependencias.

Formato (documentado publicamente por terceiros e conferido aqui com arquivos reais do Rekordbox 7.2):
  cabecalho 'PMAI' [u32 tam_cabecalho]... depois uma sequencia de tags: [4s nome][u32 tam_cab][u32 tam_total][...]; tudo big-endian
  PQTZ  grade de batidas: apos 12 bytes de cabecalho comum, 3 x u32 (zero, 0x80000, quantidade); entradas de 8 bytes: u16 batida(1-4), u16 BPM*100, u32 tempo(ms)
  PWAV  miniatura: u32 tamanho(400), u32 0x10000, 400 bytes (bits 0-4 altura, 5-7 brilho)
  PWV5  detalhe colorido (no .EXT): u32 bytes_por_entrada(2), u32 quantidade, u32 150/s; entradas de 2 bytes:
        bits 15-13 vermelho, 12-10 verde, 9-7 azul (0-7 cada), 6-2 altura (0-31)
"""
import base64
import struct

ENTRADAS_POR_SEG = 150


def le_tags(dados):
    """{nome: [(cabecalho_extra, corpo), ...]} para todas as tags do arquivo."""
    if dados[:4] != b"PMAI":
        raise ValueError("nao e um arquivo ANLZ (falta PMAI)")
    p = struct.unpack(">I", dados[4:8])[0]
    out = {}
    while p + 12 <= len(dados):
        nome = dados[p:p + 4].decode("latin1")
        cab, tot = struct.unpack(">II", dados[p + 4:p + 12])
        if tot < 12 or p + tot > len(dados):
            break
        out.setdefault(nome, []).append((dados[p + 12:p + cab], dados[p + cab:p + tot]))
        p += tot
    return out


def batidas(tags):
    """[(numero_na_barra, bpm, ms)]"""
    if "PQTZ" not in tags:
        return []
    cab, corpo = tags["PQTZ"][0]
    n = struct.unpack(">I", cab[8:12])[0]
    return [(b, t / 100.0, ms) for b, t, ms in (struct.unpack(">HHI", corpo[i * 8:i * 8 + 8]) for i in range(min(n, len(corpo) // 8)))]


def miniatura(tags):
    """[(altura 0-31, brilho 0-7)] x 400"""
    if "PWAV" not in tags:
        return []
    _, corpo = tags["PWAV"][0]
    return [(b & 0x1F, b >> 5) for b in corpo]


def detalhe_colorido(tags):
    """[(r, g, b, altura)] a 150 entradas/s (r,g,b 0-7; altura 0-31)."""
    if "PWV5" not in tags:
        return []
    cab, corpo = tags["PWV5"][0]
    n = struct.unpack(">I", cab[4:8])[0]
    out = []
    for i in range(min(n, len(corpo) // 2)):
        v = (corpo[i * 2] << 8) | corpo[i * 2 + 1]
        out.append(((v >> 13) & 7, (v >> 10) & 7, (v >> 7) & 7, (v >> 2) & 0x1F))
    return out


def detalhe_bruto(tags):
    """Bytes crus do PWV5 (2 por entrada, 150/s), prontos para ir ao tablet em base64."""
    if "PWV5" not in tags:
        return b""
    cab, corpo = tags["PWV5"][0]
    n = struct.unpack(">I", cab[4:8])[0]
    return corpo[:n * 2]


def resumo_para_tela(detalhe, colunas=600):
    """Reduz o detalhe a `colunas` colunas. Altura = meio-termo entre pico e media do trecho (so o pico deixa tudo
    saturado); cor = media das cores do trecho ponderada pela altura. Devolve {"alturas":[0-31...], "cores":[r*64+g*8+b ...]}"""
    if not detalhe:
        return {"alturas": [], "cores": []}
    n = len(detalhe)
    alturas, cores = [], []
    for c in range(colunas):
        a, b = c * n // colunas, max((c + 1) * n // colunas, c * n // colunas + 1)
        trecho = detalhe[a:b]
        pico = max(e[3] for e in trecho)
        media = sum(e[3] for e in trecho) / len(trecho)
        alturas.append(int(round(0.5 * pico + 0.5 * media)))
        peso = sum(e[3] for e in trecho) or 1
        r, g, bl = (round(sum(e[k] * e[3] for e in trecho) / peso) for k in (0, 1, 2))
        cores.append(min(7, r) * 64 + min(7, g) * 8 + min(7, bl))
    return {"alturas": alturas, "cores": cores}


def carrega(caminho_dat, caminho_ext=None, colunas=600):
    """Le os arquivos e devolve o que a tela precisa. Levanta ValueError/OSError se faltar algo essencial."""
    tags_dat = le_tags(open(caminho_dat, "rb").read())
    tags_ext = le_tags(open(caminho_ext, "rb").read()) if caminho_ext else {}
    det = detalhe_colorido(tags_ext)
    bt = batidas(tags_dat)
    if det:
        resumo = resumo_para_tela(det, colunas)
        dur = len(det) / ENTRADAS_POR_SEG
        fonte = "PWV5 (colorido)"
    else:                                         # sem .EXT: usa a miniatura monocromatica de 400 colunas
        mini = miniatura(tags_dat)
        resumo = {"alturas": [h for h, _ in mini], "cores": [7 * 64 + 7 * 8 + 7] * len(mini)}
        dur = bt[-1][2] / 1000.0 if bt else 0.0
        fonte = "PWAV (miniatura)"
    bruto = detalhe_bruto(tags_ext)
    return dict(duracao=round(dur, 2), fonte=fonte, colunas=len(resumo["alturas"]),
                batidas=[ms for _, _, ms in bt], batida_n=[b for b, _, _ in bt],
                detalhe=base64.b64encode(bruto).decode("ascii"), **resumo)
