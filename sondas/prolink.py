"""Sonda PRO DJ LINK: escuta (somente leitura) as portas UDP 50000/50001/50002 e mostra o que a rede traz.

Uso (no PC, com o Rekordbox aberto e com o PRO DJ LINK / LINK ativado, tocando uma faixa):
    python sondas/prolink.py            # roda 60 s e imprime um resumo
    python sondas/prolink.py --seg 120 --hex

Nao envia nada. Serve para descobrir se o Rekordbox 7 publica na rede o estado dos decks
(faixa carregada, tempo, BPM, play/pause), que e o que precisamos para nome da musica e waveform em tempo real.
"""
import argparse, collections, socket, struct, threading, time

MAGIC = bytes.fromhex("5173707431576d4a4f4c")   # "Qspt1WmJOL", cabecalho dos pacotes Pro DJ Link
PORTAS = {50000: "descoberta/keepalive", 50001: "beat/sync", 50002: "status dos players"}


def decodifica(d: bytes):
    if not d.startswith(MAGIC) or len(d) < 0x21:
        return None
    tipo = d[0x0A]
    nome = d[0x0B:0x1F].split(b"\0")[0].decode("latin1", "replace")
    dev = d[0x21] if len(d) > 0x21 else None
    return tipo, nome, dev


def escuta(porta, ev, dados, trava, mostrar_hex):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        s.bind(("", porta))
    except OSError as e:
        print(f"[{porta}] nao consegui abrir: {e}")
        return
    s.settimeout(0.5)
    while not ev.is_set():
        try:
            d, (ip, _) = s.recvfrom(4096)
        except socket.timeout:
            continue
        info = decodifica(d)
        with trava:
            chave = (porta, ip, info[0] if info else None, info[1] if info else "?", info[2] if info else None, len(d))
            dados[chave] += 1
            if mostrar_hex and dados[chave] == 1:
                print(f"[{porta}] {ip} {len(d)} bytes: {d[:48].hex()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", type=int, default=60)
    ap.add_argument("--hex", action="store_true", help="mostra os primeiros bytes de cada tipo novo de pacote")
    a = ap.parse_args()
    ev, dados, trava = threading.Event(), collections.Counter(), threading.Lock()
    ts = [threading.Thread(target=escuta, args=(p, ev, dados, trava, a.hex), daemon=True) for p in PORTAS]
    [t.start() for t in ts]
    print(f"escutando {', '.join(f'{p} ({n})' for p, n in PORTAS.items())} por {a.seg}s ...")
    try:
        time.sleep(a.seg)
    except KeyboardInterrupt:
        pass
    ev.set()
    print("\nporta  origem          tipo  nome-do-aparelho      dev  tamanho  pacotes")
    if not dados:
        print("(nada recebido: PRO DJ LINK desligado, outra placa de rede, firewall bloqueando UDP ou o Rekordbox nao publica)")
    for (p, ip, tipo, nome, dev, n), c in sorted(dados.items()):
        print(f"{p}  {ip:<15} {tipo if tipo is not None else '-':<5} {nome:<21} {dev if dev is not None else '-':<4} {n:<8} {c}")


if __name__ == "__main__":
    main()
