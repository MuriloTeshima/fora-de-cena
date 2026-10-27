# Executar, estudar e testar

Este repositório contém os fontes completos do Fora de Cena: aplicativo Windows,
programa independente de saída de vídeo, extensão opcional, testes e ferramentas
de empacotamento. Para apenas usar o aplicativo, baixe o instalador ou executável
na [Release](https://github.com/arantes-gabs/fora-de-cena/releases/tag/v0.4.0).

## Preparar o ambiente

Requisitos: Windows x64, Python **3.14 x64 com Tcl/Tk** e Git para clonar. O suporte
a macOS e Linux está em adaptação experimental: consulte [MAC_LINUX.md](MAC_LINUX.md)
para os requisitos e builds nativos. Node.js 22 ou superior é necessário
somente para os testes da extensão; não faz parte do aplicativo distribuído.

```powershell
git clone https://github.com/arantes-gabs/fora-de-cena.git
cd fora-de-cena
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe setup_models.py
.venv\Scripts\python.exe main.py
```

O download inicial traz três modelos oficiais do Google, com hashes verificados.
Não são necessários tokens nem contas de APIs. Depois de instalar dependências e
modelos, o reconhecimento e os efeitos funcionam localmente.

Como alternativa aos comandos de ambiente, `INSTALAR.bat` usa o comando `python`
e exige que ele aponte para Python 3.14 x64. Depois execute `INICIAR.bat`.
Para gerar pacotes ou executar a suíte completa de testes, instale também
`requirements-build.txt` conforme mostrado acima.

Para enviar o resultado a uma chamada, instale o OBS Studio separadamente e
selecione OBS Virtual Camera no serviço de vídeo. A opção Só prévia funciona sem
OBS. Veja [COMO_USAR.md](COMO_USAR.md) para calibrar o fundo e vincular a extensão.

## Por onde começar a leitura

| Arquivo ou pasta | Responsabilidade |
|---|---|
| `main.py`, `teleport_cam/launcher.py` | Entrada do aplicativo e diagnóstico sem câmera |
| `teleport_cam/app.py`, `theme.py`, `gesture_guides.py` | Interface, tema e ajuda dos gestos |
| `teleport_cam/engine.py` | Captura, processamento e coordenação da sessão |
| `teleport_cam/gesture.py`, `recognition.py` | Geometria, duração das poses e movimentos |
| `teleport_cam/vision.py`, `model_assets.py` | MediaPipe e modelos oficiais com hashes fixados |
| `teleport_cam/scene.py`, `background.py` | Calibração, fundo estático e atualização experimental |
| `teleport_cam/effects.py`, `creative_effects.py` | Composição e animação procedural dos efeitos |
| `teleport_cam/virtual_output.py` | Cliente do processo independente de saída |
| `camera_output/` | Programa GPL de vídeo BGR24 para a câmera virtual |
| `teleport_cam/meet.py`, `meet_extension/` | Vínculo local e saída opcional da aba do Meet |
| `tests/` | Casos sintéticos de gestos, efeitos, protocolo, segurança e distribuição |
| `packaging/`, `tools/` | Receitas de build, avisos, fontes e preparação local |

Fluxo de vídeo: webcam → processamento local e efeitos → quadros BGR24 por pipe
anônimo → programa de saída independente → OBS Virtual Camera → chamada.

A interface permanece na thread principal; o motor executa captura/inferência
fora dela. A saída tem um quadro em trânsito, prazo de resposta e confirmação
após envio à câmera virtual. A extensão não recebe quadros, áudio ou acesso à
webcam: usa uma ponte local autenticada para fechar somente a aba vinculada.
Consulte [SECURITY.md](SECURITY.md) antes de alterar esse protocolo.

## Testes automatizados

Na raiz do repositório, depois de instalar as dependências:

```powershell
.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --test tests/meet_extension.test.mjs
.venv\Scripts\python.exe -m pip check
```

A suíte padrão usa imagens e dados sintéticos e APIs simuladas. Não exige baixar
modelos, abrir a webcam, instalar OBS nem entrar em uma reunião. Algumas provas
iniciam processos e um servidor apenas em loopback, usando portas temporárias.

Depois de baixar os modelos, este diagnóstico adicional executa inferência e
verifica o protocolo do processo de saída sem abrir janela, webcam ou câmera virtual:

```powershell
.venv\Scripts\python.exe -B main.py --self-test --report work/self-test.json
```

O comando não testa o driver real. `smoke_test.py` é outro teste opcional: ele
inicializa a interface, enumera câmeras e pode registrar F8. Não o execute quando
precisar evitar interferência com outros programas.

Para medir somente o compositor com dados sintéticos:

```powershell
.venv\Scripts\python.exe -m tools.benchmark_effects
```

Esses testes não comprovam desempenho ou qualidade em todos os dispositivos.
Valide gestos, calibração, restauração, driver OBS e chamada na máquina de destino.

## Gerar executáveis

As etapas e os requisitos do instalador e do executável único estão em
[DISTRIBUIR.md](DISTRIBUIR.md). O aplicativo não exige Python no computador de quem
baixar os executáveis prontos.

## Arquivos mantidos fora do Git

Modelos baixados, ambientes virtuais, binários, dependências, configurações da
sessão, a chave local do Meet, capturas de webcam, relatórios, prompts de geração
de imagens e rascunhos internos não são necessários para estudar os fontes e não
acompanham o repositório. A instalação gera seus próprios dados locais.

O código principal está sob MIT. O programa independente `camera_output/` está
sob GPL-2.0-only. As dependências preservam suas próprias licenças; consulte
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
