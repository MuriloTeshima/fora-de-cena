# OpenCV enxuto — candidato Mac Apple Silicon, 27/10/2026

**Atualização de validação:** no retorno de 27/10, o proprietário reportou teste
manual geral positivo do DMG SHA-256
`8f7f6d536592a63d40fb9c2dd2bc9b67613503147be17b1cbdcdccec870f78da`.
USB/MJPEG não foi confirmado individualmente. O ambiente atual informado no
retorno é M1/macOS 27.2; o primeiro registro histórico era macOS 15.5, sem data
independente para a atualização. O mínimo binário permanece macOS 15.0.
Os relatórios sintéticos anteriores não foram alterados para simular teste físico.

O runtime do aplicativo e as correções M1 anteriores foram preservados. Integração
seletiva dos quatro arquivos recebidos; nada publicado. O venv e DMG antigos
continuam disponíveis. Este candidato usa um único opencv-contrib-python 4.14.0.94
próprio, não a wheel oficial, com NumPy 2.5.4 e MediaPipe 1.1.1 inalterados.

## Receita

Python 3.14 ARM64 com Tk (Homebrew python-tk@3.14, autorizado pelo proprietário).
Crie .venv-opencv-build e .venv-opencv-test separados; instale requirements-opencv-build.txt
somente no primeiro. Não copie .pth nem configurações entre ambientes.
Baixe o sdist da URL/hash em packaging/opencv-minimal-profile.json, confira SHA256
antes de extrair em work/opencv-minimal/source/. Aplique packaging/opencv-minimal-source.patch
na raiz extraída com git apply (não faz commit). O patch corrige o gerador de tipagem
para módulos opcionais ausentes e remove caminhos da máquina da configuração embutida.
Execute no venv de build:

```
python tools/build_minimal_opencv.py --source work/opencv-minimal/source/opencv_contrib_python-4.14.0.94
```

A pasta de wheels deve estar vazia; não reutilizar caches ou wheels de outro perfil.
A receita fixa CMake/Ninja/NumPy de build, arquitetura, mínimo 15.0 e paralelismo4.
KleidiCV 26.03 é download adicional fixado por versão/MD5 upstream e SHA256 revisado.
FFmpeg/GStreamer/HighGUI/Qt/GTK desativados; AVFoundation/JPEG/PNG preservados.
Sem RPATH de instalação local. Os prefixos C/C++ e relatórios embutidos são remapeados.

No venv de teste, instale a wheel local explicitamente junto com requirements.lock.txt
e requirements-build.txt, sem --no-deps, depois execute pip check, suíte Python,
node --test tests/meet_extension.test.mjs e main.py --self-test --report <arquivo-local>.
FDC_TEST_MINIMAL_OPENCV=1 ativa o teste específico de backends/símbolos.
Os testes da ponte Meet precisam abrir portas apenas em 127.0.0.1; os diagnósticos
não abrem webcam ou chamada. HOME/caches de teste devem ficar em work/.

Compile no mesmo venv de teste:

```
python tools/build_unix.py --python-license /opt/homebrew/opt/python@3.14/LICENSE --opencv-wheel work/opencv-minimal/wheels/opencv_contrib_python-4.14.0.94-cp314-cp314-macosx_15_0_arm64.whl --opencv-provenance work/opencv-minimal/provenance.json
```

O gerador verifica hash/receita/provedor único/direct_url e os bytes nativos instalados.
Manifesto identifica custom_build=true e distribution_ready=false; os avisos próprios
acompanham o app e pacote de licenças. Sem os dois argumentos explícitos, o fluxo
anterior continua disponível, inclusive para Windows/Linux.

## Teste físico do candidato novo

1. Abra a cópia nova separadamente e confirme câmera interna; USB/MJPEG, se disponível.
2. Capture fundo vazio, calibre gestos e teste os seis efeitos, inclusive as primeiras
   ativações de teleporte. Confira fluidez e restauração por botão/F8.
3. Abra/feche Configurar várias vezes, redimensione e confira a prévia.
4. Teste OBS Virtual Camera e selecione-a no Meet. No macOS15+: Ajustes → Geral →
   Itens de Início e Extensões → Extensões de Câmera; autorize a extensão OBS se necessário
   e reabra o navegador. Não alterar Gatekeeper/SIP. Consulte MAC_LINUX.md para abertura
   de app ad hoc e documentação oficial OBS.

O mínimo real continua macOS15/Apple Silicon. O retorno do proprietário passou
a incluir este candidato enxuto; a lista acima serve para registrar a cobertura
por cenário e validar futuros builds. USB/MJPEG segue sem confirmação específica.
Sem suporte anunciado para Intel/macOS13/14 ou nova validação Linux.

## Publicação ainda bloqueada

Revisão scoped OpenCV e avisos em packaging/notices/opencv-minimal/; preservam-se
as obrigações GPL do auxiliar independente e seus fontes correspondentes. Ainda
faltam a revisão final das demais bibliotecas e a verificação de rede/métricas
do MediaPipe. O teste manual geral deste candidato foi reportado como positivo,
com cobertura não individualizada. Não afirmar ausência de telemetria.
Autorização do proprietário para publicar também é necessária.
