"""Stable effect identifiers shared by UI, pipeline and preferences."""
from .effects import AnimeTeleportEffect, TeleportEffect
from .creative_effects import CartoonExitEffect, DigitalEffect, DustEffect, PortalEffect, PuffEffect

EFFECTS: dict[str, type[TeleportEffect]] = {
    'anime': AnimeTeleportEffect, 'goku': TeleportEffect, 'puff': PuffEffect,
    'digital': DigitalEffect, 'dust': DustEffect, 'cartoon': CartoonExitEffect, 'portal': PortalEffect,
}
LABELS: dict[str, str] = {
    'Teleporte anime': 'anime', 'Puf! · fumaça': 'puff', 'Saída digital': 'digital',
    'Virar poeira': 'dust', 'Saída de cena': 'cartoon', 'Portal': 'portal',
    'Suave · rastro': 'goku', 'Instantâneo': 'instant',
}
DESCRIPTIONS: dict[str, str] = {
    'anime': 'Linhas de velocidade e um corte rápido, com acabamento de animação.',
    'puff': 'Uma nuvem de fumaça desenhada cobre sua saída.',
    'digital': 'Seu recorte se desfaz em blocos de videogame.',
    'dust': 'Seu recorte se dissolve em pequenas partículas levadas para o lado.',
    'cartoon': 'Uma arrancada para o lado, com deformação e rastro.',
    'portal': 'Um portal luminoso recolhe seu recorte e se fecha.',
    'goku': 'Distorção suave com rastro luminoso.',
    'instant': 'Troca imediata pelo fundo preparado. É o modo mais leve.',
}
