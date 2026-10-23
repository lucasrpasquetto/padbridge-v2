"""Embute a tela de pads do PadBridge v1 dentro de padbridge2/web/index.html (sem quadro/iframe).

A tela do v1 vai para um Shadow DOM (o CSS dela nao mistura com o do v2) e o JS dela roda numa funcao propria; a unica
mudanca e que o MIDI sai/entra pela conexao do v2 (window.__midiEnviar / window.__padsFeedback) em vez de abrir outro WebSocket.
Uso:  python tools/gera_pads.py [caminho/do/v1/padbridge/web/index.html]
Rode de novo sempre que o v1 mudar (python tools/gerar.py no v1 regenera o HTML dele)."""
import os, re, sys

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(AQUI, "padbridge2", "web", "index.html")
INI, FIM = "/*PADS_INICIO*/", "/*PADS_FIM*/"


def transforma(v1):
    css = re.search(r"<style>(.*?)</style>", v1, re.S).group(1)
    corpo = re.search(r"<body>(.*?)<script>", v1, re.S).group(1).strip()
    js = re.search(r"<script>(.*?)</script>", v1, re.S).group(1)
    # --- CSS: html/body/:root viram :host; o resto fica igual (o Shadow DOM isola) ---
    css = css.replace(":root{", ":host{", 1)
    css = css.replace("html,body{", ":host{display:block;", 1)
    css = css.replace("body.dbg #ult", ":host(.dbg) #ult")
    css = css.replace("#rod{position:fixed", "#rod{position:absolute").replace("#gire{display:none;position:fixed", "#gire{display:none;position:absolute")   # a tela desliza (transform): fixed sairia do lugar
    assert "`" not in css and "${" not in css and "</style" not in css
    # --- JS ---
    ini = js.index("let ws=null;")
    fim = js.index("function enviar(")
    ponte = ("const stEl=document.getElementById('st'),rod=document.getElementById('rod'),ult=document.getElementById('ult');\n"
             "window.__padsFeedback=feedback;      // o v2 repassa aqui o estado vindo do Rekordbox\n"
             "setInterval(()=>{const on=window.__midiOk&&window.__midiOk();rod.className=on?'ok':'';stEl.textContent=on?'conectado':'sem conexao'},500);\n")
    js = js[:ini] + ponte + js[fim:]
    velho = "if(ws&&ws.readyState===1)ws.send(t+','+ch+','+nota+','+vel);"
    assert velho in js
    js = js.replace(velho, "if(window.__midiEnviar)window.__midiEnviar(t,ch,nota,vel);")
    assert js.count("\nconectar();") == 1
    js = js.replace("\nconectar();", "\n")
    js = js.replace("document.body.classList", "R.host.classList").replace("observe(document.body", "observe(R")
    for f in ("getElementById", "querySelectorAll", "querySelector"):
        js = js.replace("document." + f + "(", "R." + f + "(")
    assert "document.body" not in js and not re.search(r"\bws\b", js)
    return css, corpo, js


def monta(css, corpo, js):
    return (INI + "\n(function(){\nconst R=document.getElementById('padshost').attachShadow({mode:'open'});\n"
            "R.innerHTML=`<style>" + css + "</style>" + corpo.replace("`", "'") + "`;\n" + js + "\n})();\n" + FIM)


def main(caminho_v1=None):
    caminho_v1 = caminho_v1 or os.path.join(AQUI, "..", "PadBridge", "padbridge", "web", "index.html")
    v1 = open(caminho_v1, encoding="utf-8").read()
    bloco = monta(*transforma(v1))
    v2 = open(V2, encoding="utf-8").read()
    if INI in v2:
        a, b = v2.index(INI), v2.index(FIM) + len(FIM)
        v2 = v2[:a] + bloco + v2[b:]
    else:
        gancho = "// tela cheia: entra e sai;"
        assert gancho in v2
        v2 = v2.replace(gancho, bloco + "\n" + gancho, 1)
    open(V2, "w", encoding="utf-8").write(v2)
    print("tela de pads do v1 embutida em", V2, f"({len(bloco)} bytes)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
