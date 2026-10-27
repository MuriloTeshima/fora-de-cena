"""One source for recognition modes, onboarding copy and optional illustrations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class GestureGuide:
    kind: str
    title: str
    instruction: str
    steps: tuple[str, ...]
    image: str
    motion: bool = False


GUIDES: dict[str, GestureGuide] = {
    'anime': GestureGuide('forehead','Dois dedos na testa','Junte indicador e médio na testa e mantenha a posição.',
        ('Mostre uma mão e seu rosto.','Junte indicador e médio na testa; dobre os outros dedos.','Segure até completar a barra. Baixe a mão antes de repetir.'),'teleporte.png'),
    'puff': GestureGuide('ninja','Selo ninja de uma mão','Mostre uma mão com indicador e médio juntos para cima; dobre anular e mínimo.',
        ('Mostre uma mão perto do rosto ou à frente do peito, sem cobrir a face.','Estenda indicador e médio juntos para cima; dobre anular e mínimo, com o polegar relaxado sobre eles.','Segure até completar a barra. Baixe ou relaxe a mão antes de repetir.'),'selo-uma-mao.png'),
    'dust': GestureGuide('snap','Estalo de dedos','Encoste polegar e médio brevemente; estale, dobrando o médio em direção à palma.',
        ('Mostre uma mão perto do rosto, sem cobri-lo.','Encoste polegar e médio por um instante (aproximadamente 0,1–0,8 s).','Estale: separe os dedos e leve o médio à palma. O app observa o movimento, sem ouvir som.'),'poeira.png',True),
    'digital': GestureGuide('pinch','Pinça digital','Encoste polegar e indicador; abra os dois dedos para liberar os pixels.',
        ('Mostre uma mão de frente para a câmera.','Encoste polegar e indicador brevemente (aproximadamente 0,1–0,9 s).','Abra a pinça mantendo a mão no lugar. Solte antes de repetir.'),'digital.png',True),
    'cartoon': GestureGuide('palm','Palma de despedida','Mostre uma palma aberta para a câmera e mantenha parada, sem precisar acenar.',
        ('Mostre uma mão aberta ao lado do rosto, com a palma voltada para a câmera.','Deixe os dedos confortavelmente estendidos e mantenha a mão parada até completar a barra.','Baixe ou feche a mão antes de repetir. Não é preciso acenar.'),'palma.png'),
    'portal': GestureGuide('palms','Abrir o portal','Mostre as duas palmas abertas, uma de cada lado do rosto.',
        ('Mostre as duas mãos abertas para a câmera.','Deixe uma mão de cada lado do rosto, sem cobri-lo.','Segure até completar a barra; baixe as mãos antes de repetir.'),'portal.png'),
    'instant': GestureGuide('manual','Ativação manual','Use Ativar efeito ou Reaparecer. F8 sempre restaura a imagem.',
        ('Prepare e confirme o fundo vazio.','Clique Ativar efeito para desaparecer e Reaparecer para voltar.','Este modo não dispara por gestos. Restaurar ou F8 devolve a imagem ao vivo.'),'manual.png'),
}
GUIDES['goku'] = GUIDES['anime']


def guide_for(effect: str) -> GestureGuide:
    return GUIDES.get(effect, GUIDES['instant'])


def illustration_size(size: tuple[int, int], limit: int) -> tuple[int, int]:
    """Fit tutorials without squeezing horizontal sequences into a square."""
    width,height=size
    if min(width,height,limit)<=0:
        raise ValueError('Dimensões da ilustração devem ser positivas.')
    scale=limit/max(width,height)
    return max(1,round(width*scale)),max(1,round(height*scale))
