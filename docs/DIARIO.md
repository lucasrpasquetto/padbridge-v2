# Diario de desenvolvimento do PadBridge v2

Registro, passo a passo, de como cada fonte de dado foi testada e escolhida. O guia de uso esta no [README](../README.md).


Recomeco do PadBridge com foco em **dados em tempo real do Rekordbox** (nome da faixa nos decks, depois waveform, BPM, posicao), alem dos pads.
A v1 (pads, stems, LEDs) continua em `..\PadBridge` e serve de referencia.

Regra do projeto: um passo por vez, cada fonte de dado so entra depois de **testada no PC**.
Estudo de base: `TEMPO_REAL.md` do repositorio do v1.

## Passo 1 - de onde vem o nome da faixa carregada em cada deck?
Candidatas (ver `sondas/`):
1. **PRO DJ LINK** (rede, UDP 50001/50002) - `sondas/prolink.py`
2. **Acessibilidade do Windows (UI Automation)** - le os textos que o Rekordbox mostra - `sondas/uia.py`
3. Historico do banco (`master.db`) - plano B, so registra depois de tocar

Rode as sondas 1 e 2 com o Rekordbox aberto e uma faixa carregada em cada deck; o resultado decide a fonte.

## Resultado do passo 1
A sonda UIA mostrou que o Rekordbox expoe, pela acessibilidade do Windows, titulo, artista, BPM, tonalidade e tempos de cada deck (ver `tests/fixtures/uia_dois_decks.txt`).
O PRO DJ LINK ficou como pista (as portas 50000/50001 estao abertas pelo proprio Rekordbox).

## Passo 2 - leitor de decks
```
pip install pywinauto
python -m padbridge2        # imprime os decks e atualiza quando a faixa muda
python tests\test_leitor.py # teste do interpretador contra o dump real
```

## Passo 3 - nome das faixas no tablet
```
pip install -r requirements.txt
python -m padbridge2                 # servidor na porta 8766
```
No tablet:
- USB: `adb reverse tcp:8766 tcp:8766` e abra `http://localhost:8766`
- Wi-Fi: abra o endereco `http://<IP do PC>:8766` que o servidor mostra (libere a porta no Firewall do Windows se pedir)

A tela mostra, para cada deck: titulo, artista, tempo restante com barra de progresso, BPM e tonalidade.
`python tests\test_tela.py` testa a tela e a logica do servidor (a parte de rede so e testada no PC).

## Resultado: PRO DJ LINK
Captura passiva (`sondas/prolink_sniff.py`, Npcap + scapy) com o Rekordbox aberto, botao LINK ligado e deck tocando, sem aparelho Pioneer na rede:
- Portas 50000/50001/50002 (PRO DJ LINK): **nenhum pacote**. O Rekordbox nao publica o estado dos decks sem hardware Pioneer em rede.
- Porta 20808: pacotes `_asdp_v1` = **Ableton Link** (descoberta de pares; o campo `tmln` leva o tempo da sessao). O botao LINK do Rekordbox e o Ableton Link: sincroniza tempo/fase, **nao** tem nome de faixa nem waveform.
- Fonte dos dados dos decks segue sendo a leitura da tela (UI Automation); waveform vira dos arquivos ANLZ.

## Passo 4 - waveform no tablet
Quando a faixa de um deck muda, o servidor acha a faixa no banco do Rekordbox (por titulo + artista, desempatando por BPM e tom),
le o arquivo de analise (`ANLZ0000.DAT/.EXT`, que fica em `D:\PIONEER\Master\share\...`, o banco informa o caminho) e manda a waveform
colorida ao tablet, com um cursor que acompanha o tempo decorrido.

O banco so abre com o `pyrekordbox`, que ja esta no venv do rekordbox-mcp; por isso um processo ajudante (`padbridge2/ajudante_db.py`) roda com aquele Python:
```
python -m padbridge2                                   # usa C:\Users\<voce>\rekordbox-mcp\.venv\Scripts\python.exe
python -m padbridge2 --python-db "C:\caminho\python.exe"
python -m padbridge2 --sem-onda                        # so nomes, sem waveform
```
Testes: `python tests\test_onda.py`, `python tests\test_estado.py`, `python tests\test_tela.py`, `python tests\test_leitor.py`.
`tests/fixtures/anlz/` tem a analise de uma faixa pessoal: nao publique no GitHub.

## Passo 5 - zoom, grade de batidas e cues

Cada deck agora tem:

- **visao geral** (faixa inteira, fina) com o cursor e os marcadores dos cues;
- **waveform ampliada** (12 s em volta do cursor, que fica no centro), desenhada com o detalhe colorido do Rekordbox (150 amostras/s, arquivo `.EXT`);
- **grade de batidas**: linha forte no inicio de cada compasso, tracinho nas demais batidas (do `PQTZ` do `.DAT`);
- **cues**: hot cues A, B, C... com a cor do pad e a letra, memory cues (cinza, "M") e loops (area sombreada).

Os cues nao ficam nos arquivos de analise: vem da tabela `DjmdCue` do `master.db` (mesmo ajudante do passo 4, comando `cues`). O servidor le de novo a cada ~2 s por deck carregado e so manda ao tablet quando algo muda - cue criado ou apagado durante o set aparece sozinho.

Testes: `python tests/test_onda.py`, `test_estado.py`, `test_tela.py` (precisa de `playwright`).

## Passo 6 - tela principal

Layout: `[deck 1: dados, stems, 8 hot cues] [waveform 1 | waveform 2] [deck 2: ...]`.

- As waveforms ficam no centro, **verticais**, lado a lado; o tempo corre de baixo para cima (o futuro entra por baixo, o cursor fica a 30% do topo). Batidas, cues e loops como no passo 5.
- Ao lado de cada waveform: titulo, artista, tempo restante, BPM, tom e barra de progresso; abaixo, os 5 botoes de stems (VOCAL, INST, BASS, DRUMS e MODO mute/solo) e os 8 pads de hot cue (A-H, com o tempo do cue quando existe).
- Os botoes mandam MIDI pela **ponte do PadBridge v1** (a pagina abre um 2o WebSocket em `ws://<pc>:8765/ws`; outra porta: `?midi=PORTA`). Deixe o v1 rodando, com `"wifi": true` no `padbridge_config.json` se o tablet nao estiver por USB.
- Notas: pads = canal 7/9 notas 0-7; stems = canal 7/9 notas 0x10-0x13; MODO = canal 0 nota 0x56 (global, **mapeamento novo**: reimporte `mapping/PadBridge.midi.csv` do v1 no Rekordbox).

Hot cues no banco: A, B, C = `Kind` 1, 2, 3 mas D, E, F... = `Kind` 5, 6, 7... (o 4 nao e hot cue). O ajudante converte.

## Passo 7 - duas telas (decks / pads), no mesmo projeto

A tela inicial e a dos decks. Deslizar o dedo da **borda direita para a esquerda** (ou em qualquer area livre) desliza para a tela de **pads**, que e a tela do PadBridge v1 embutida na propria pagina (Shadow DOM, sem quadro/iframe e sem abrir outra conexao: os pads usam o mesmo MIDI da tela dos decks). Da **borda esquerda para a direita** volta para os decks.

A tela de pads e gerada a partir do HTML do v1: `python tools/gera_pads.py ..\PadBridge\padbridge\web\index.html` (rode de novo se o v1 mudar). A ponte MIDI (loopMIDI -> Rekordbox) continua sendo o PadBridge v1 rodando no PC.
