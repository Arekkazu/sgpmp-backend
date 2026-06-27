"""Adaptador stub de :class:`DependenciaPatologiaPort`.

Retorna ``False`` siempre: mientras M04 (Predicción IA) no esté implementado,
ninguna patología tiene predicciones o alertas asociadas y la desactivación
no se bloquea por ese motivo.
Cuando M04 exista, este stub se reemplaza por la implementación real que
consulta ``vw_rf16_dependencias_patologias``.
"""
from __future__ import annotations

from src.configuration.domain.repositories.dependencia_patologia_port import DependenciaPatologiaPort


class StubDependenciaPatologiaAdapter(DependenciaPatologiaPort):

    def tiene_dependencias_activas(self, id_patologia: int) -> bool:
        return False
