"""Sonda PASSIVA do PRO DJ LINK: captura (sem enviar nada) os pacotes UDP 50000-50002 que o Rekordbox emite na rede.

Requisitos (uma vez):
  1. Instalar o Npcap (https://npcap.com) marcando "Install Npcap in WinPcap API-compatible Mode"
  2. pip install scapy
Uso (Windows, terminal como Administrador; Rekordbox aberto com o botao LINK ligado e um deck tocando):
  python sondas/prolink_sniff.py --listar              # mostra as placas de rede
  python sondas/prolink_sniff.py --seg 60              # captura 60 s em todas as placas
  python sondas/prolink_sniff.py --seg 60 --iface "Wi-Fi"
Grava sondas/saida_prolink.jsonl (primeiros pacotes de cada tipo, em hexadecimal) e imprime um resumo.

Os rotulos de tipo abaixo vem de documentacao publica de terceiros (Deep Symmetry, dysentery) e
precisam ser confirmados com o que o Rekordbox 7 realmente manda: o arquivo gravado serve para isso.
"""
import argparse, collections, json, os, sys, time

MAGIC = bytes.fromhex("5173707431576d4a4f4c")          # "Qspt1WmJOL"
ROTULOS = {
    (50000, 0x06): "keep-alive / anuncio do aparelho",
    (50000, 0x0A): "keep-alive / anuncio do aparelho (variante)",
    (50000, 0x00): "descoberta: etapa 1",
    (50000, 0x02): "descoberta: etapa 2",
    (50000, 0x04): "descoberta: etapa 3",
    (50001, 0x28): "batida (beat)",
    (50001, 0x03): "on-air / canais",
    (50001, 0x2B): "posicao precisa",
    (50002, 0x0A): "status do player (faixa, tempo, BPM)",
    (50002, 0x29): "status do mixer",
}


def decodifica(porta, d):
    """Cabecalho comum. Devolve dict ou None se nao for pacote Pro DJ Link."""
    if not d.startswith(MAGIC) or len(d) < 0x22:
        return None
    return dict(
        porta=porta, tipo=d[0x0A], nome=d[0x0B:0x1F].split(b"\0")[0].decode("latin1", "replace"),
        dev=d[0x21], tamanho=len(d), rotulo=ROTULOS.get((porta, d[0x0A]), "desconhecido"),
    )


def campos_status(d):
    """Campos do status de player (0x0A em 50002) segundo a documentacao de terceiros. NAO confirmados no Rekordbox 7."""
    if len(d) < 0x9A:
        return {}
    return dict(
        player_fonte=d[0x28], slot=d[0x29], tipo_faixa=d[0x2A],
        id_rekordbox=int.from_bytes(d[0x2C:0x30], "big"),
        estado_play=d[0x7B], bpm_faixa=int.from_bytes(d[0x92:0x94], "big") / 100,
    )


def processa(porta, d, ip, resumo, amostras, max_amostras=3):
    i = decodifica(porta, d)
    chave = (porta, ip, i["tipo"], i["nome"], i["dev"], i["tamanho"]) if i else (porta, ip, None, "?", None, len(d))
    resumo[chave] += 1
    if resumo[chave] <= max_amostras:
        reg = dict(ip=ip, hex=d.hex(), **(i or dict(porta=porta)))
        if i and porta == 50002 and i["tipo"] == 0x0A:
            reg["campos_documentados"] = campos_status(d)
        amostras.append(reg)


def imprime(resumo):
    print("\nporta  origem          tipo  nome-do-aparelho      dev  tamanho  pacotes  significado (a confirmar)")
    if not resumo:
        print("(nada capturado: LINK desligado no Rekordbox, placa errada, Npcap sem modo WinPcap, ou o Rekordbox nao publica nesta rede)")
    for (p, ip, tipo, nome, dev, n), c in sorted(resumo.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        rot = ROTULOS.get((p, tipo), "desconhecido") if tipo is not None else "nao e Pro DJ Link"
        print(f"{p}  {ip:<15} {('0x%02x' % tipo) if tipo is not None else '-':<5} {nome:<21} {dev if dev is not None else '-':<4} {n:<8} {c:<8} {rot}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", type=int, default=60)
    ap.add_argument("--iface", default=None)
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--diag", action="store_true", help="captura todo UDP e mostra as portas mais ativas (para ver se a captura funciona)")
    a = ap.parse_args()
    try:
        from scapy.all import sniff, UDP, IP, get_if_list, conf
    except ImportError:
        sys.exit("Instale antes:  pip install scapy   (e o Npcap, veja o topo deste arquivo)")
    if a.listar:
        for n in get_if_list():
            print(n)
        return
    resumo, amostras, vistos = collections.Counter(), [], collections.Counter()
    ifaces = [a.iface] if a.iface else list(get_if_list())          # scapy no Windows so escuta a placa padrao se nao receber a lista

    def cb(pkt):
        vistos["pacotes (qualquer tipo)"] += 1
        if UDP in pkt and IP in pkt:
            if a.diag:
                vistos[f"UDP {pkt[IP].src} -> porta {int(pkt[UDP].dport)}"] += 1
            processa(int(pkt[UDP].dport), bytes(pkt[UDP].payload), pkt[IP].src, resumo, amostras)

    filtro = "udp" if a.diag else "udp portrange 50000-50002"
    print(f"capturando '{filtro}' por {a.seg}s em {len(ifaces)} placa(s) ...")
    try:
        sniff(filter=filtro, prn=cb, store=False, timeout=a.seg, iface=ifaces if len(ifaces) > 1 else ifaces[0])
    except Exception as e:
        sys.exit(f"falha ao capturar: {e}\n(abra o terminal como Administrador e confirme que o Npcap esta instalado)")
    print(f"total capturado: {vistos['pacotes (qualquer tipo)']} pacotes")
    if a.diag:
        for k, c in vistos.most_common(16):
            print(f"  {c:>6}  {k}")
    aqui = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(aqui, "saida_prolink.jsonl"), "w", encoding="utf-8") as f:
        for r in amostras:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    imprime(resumo)
    print(f"\n{len(amostras)} amostras gravadas em sondas/saida_prolink.jsonl")


if __name__ == "__main__":
    main()
