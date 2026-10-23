"""PadBridge num programa so: decks (v2) + ponte MIDI e pads (v1), com um icone na bandeja do Windows."""
import ctypes, os, subprocess, sys, threading, webbrowser

NOME = "PadBridge v2"
CORES = {"verde": (46, 204, 113), "amarelo": (241, 196, 15), "vermelho": (231, 76, 60)}


def pasta_programa():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


def ja_esta_rodando():
    if os.name != "nt":
        return False
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\PadBridge2")
    return ctypes.windll.kernel32.GetLastError() == 183


def aviso(texto):
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, texto, NOME, 0x40)
    else:
        print(texto)


def icone(cor):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(28, 30, 38, 255))
    for x in (12, 36):                                   # duas "ondas" verticais = os 2 decks
        d.rounded_rectangle((x, 8, x + 16, 40), radius=3, fill=(70, 74, 92, 255))
        d.rounded_rectangle((x + 5, 14, x + 11, 40), radius=2, fill=(120, 170, 255, 255))
    d.ellipse((38, 38, 60, 60), fill=CORES[cor] + (255,), outline=(255, 255, 255, 255), width=2)
    return img


def roda_unico(leitor, porta, biblioteca, argv_v1=()):
    """Um programa so: sobe o servidor dos decks (v2) numa thread e entrega o resto ao programa do v1
    (ponte MIDI + servidor de pads + icone da bandeja). Se o v1 nao estiver junto, cai no servidor simples."""
    import logging
    from .servidor import cria_app, ip_local, _prepara_loop
    try:
        from padbridge import app as v1
    except ImportError:
        from .servidor import roda
        roda(leitor, porta, biblioteca)
        return
    from aiohttp import web
    if porta not in v1.PORTAS_EXTRA:
        v1.PORTAS_EXTRA.append(porta)           # o 'adb reverse' do v1 passa a cobrir tambem a porta dos decks
    app = cria_app(leitor, biblioteca=biblioteca)

    def servidor():
        try:
            web.run_app(app, host="0.0.0.0", port=porta, print=None, loop=_prepara_loop(), handle_signals=False)
        except Exception:
            logging.exception("servidor dos decks parou (porta %s ocupada?)", porta)

    threading.Thread(target=servidor, daemon=True).start()
    logging.info("decks (v2): http://%s:%s", ip_local(), porta)
    try:
        v1.main(list(argv_v1))
    finally:
        if biblioteca is not None:
            biblioteca.fecha()
