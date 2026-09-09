"""
TC-M02-G60 (parte Pytest) - Rechazo de reasignacion de madre/padre a una
cria ya existente (TC-M02-237).

RF relacionado: RF-42, CU08 Gestionar eventos reproductivos
Categoria: Pruebas de validacion

Criterio de aceptacion (segun la ficha, sub-caso 3):
    "Cada cria debe tener exactamente 1 madre y 1 padre (N:1); no se
    permite sobreescritura genealogica." Precondicion: "Cria con relacion
    genealogica (madre y/o padre) ya registrada previamente." Paso:
    "Intentar registrar/asociar una segunda madre o un segundo padre a una
    cria que ya tiene relacion genealogica registrada." Resultado esperado:
    "El sistema rechaza la operacion, preservando la relacion genealogica
    original de la cria (1 madre y 1 padre maximo)."

Por que Pytest con dobles de prueba y no Newman contra el backend en vivo
(mismo criterio que TC-M02-G56/G58): cualquier escritura real en
modulo2.eventos_reproductivos hoy responde 500 por el bug de
db_error_translator ya documentado en TC-M02-G53/G55/G57/G58, lo que
haria indistinguible "el sistema rechazo la reasignacion" de "el sistema
fallo por el bug ya conocido". Aislando el use case con dobles de prueba
se puede verificar si el codigo siquiera intenta detectar una reasignacion,
sin ese ruido.

Hallazgo (leido en registrar_evento_reproductivo_use_case.py completo):
no existe ningun mecanismo de "cria" como entidad individual -- ver
tambien TC-M02-G58 (TC-M02-229), donde se documenta que 'numero_crias' es
un entero agregado en un unico evento, sin registros por-cria. Por lo
tanto tampoco existe ningun concepto de "reasignar la madre/padre de una
cria ya existente": el unico dato que se fija por evento es el
`id_padre`/`id_madre` DEL EVENTO EN SI (la hembra tratada, no una cria
individual). El use case no consulta si el activo ya tiene un
servicio/inseminacion previo con un padre DISTINTO antes de aceptar uno
nuevo -- simplemente inserta el nuevo evento sin comparar contra eventos
anteriores del mismo activo. Registrar una segunda inseminacion con un
id_padre diferente sobre la misma hembra se acepta sin ninguna
verificacion de conflicto.

Se deja la prueba afirmando el comportamiento CORRECTO esperado por el RF
(rechazo de la segunda inseminacion con un padre distinto) en vez de
ajustarse al comportamiento actual: un Pytest en rojo aqui es la evidencia
documentada, mismo criterio aplicado en TC-M02-G53/G55/G56/G58.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_237_reasignacion_genealogica.py -v \
        --html=Resultados/reporte-TC-M02-237.html --self-contained-html
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.biological_assets.application.use_cases.gestion.registrar_evento_reproductivo_use_case import (
    RegistrarEventoReproductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoReproductivo,
)
from src.biological_assets.infrastructure.dto.registrar_evento_reproductivo_dto import (
    RegistrarEventoReproductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_MADRE = 500
ID_PADRE_ORIGINAL = 501
ID_PADRE_NUEVO = 502


def _activo(id_activo_biologico: int) -> ActivoBiologico:
    return ActivoBiologico(
        id_especie=10,
        tipo='INDIVIDUAL',
        origen_financiero='compra',
        id_infraestructura=3,
        id_estado=1,
        id_usuario=1,
        id_activo_biologico=id_activo_biologico,
        fecha_creacion=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestTCM02237ReasignacionGenealogica:

    def test_use_case_no_rechaza_segunda_inseminacion_con_padre_distinto(self):
        """
        RF-42: una vez que una hembra ya tiene una relacion genealogica
        establecida (una inseminacion con un padre valido), el sistema debe
        rechazar un intento de asociarle un SEGUNDO padre distinto (evitar
        sobreescritura de la relacion N:1 original).
        """
        madre = _activo(ID_MADRE)
        padre_original = _activo(ID_PADRE_ORIGINAL)
        padre_nuevo = _activo(ID_PADRE_NUEVO)

        def _obtener_por_id(id_activo):
            if id_activo == ID_MADRE:
                return madre
            if id_activo == ID_PADRE_ORIGINAL:
                return padre_original
            if id_activo == ID_PADRE_NUEVO:
                return padre_nuevo
            return None

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.side_effect = _obtener_por_id

        evento_repo = MagicMock()
        evento_repo.obtener_ultima_fecha.return_value = None
        # Simula que la madre YA tiene una inseminacion previa registrada
        # con padre_original (precondicion de la ficha: "relacion
        # genealogica ya registrada previamente").
        evento_repo.tiene_servicio_o_inseminacion_previa.return_value = True

        db = MagicMock()
        use_case = RegistrarEventoReproductivoUseCase(
            db=db, activo_repo=activo_repo, evento_repo=evento_repo, bitacora_repo=MagicMock(),
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=2, id_estado_cuenta=2)

        # Intento de "reasignar" el padre: una segunda inseminacion sobre
        # la MISMA madre, ahora con un padre DISTINTO.
        evento_repo.guardar.return_value = EventoActivo(
            id_activo_biologico=ID_MADRE,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=701,
            reproductivo=EventoReproductivo(
                categoria='inseminacion', resultado='exitoso', id_padre=ID_PADRE_NUEVO,
            ),
        )
        dto_reasignacion = RegistrarEventoReproductivoDTO(
            categoria='inseminacion', resultado='exitoso', id_padre=ID_PADRE_NUEVO,
        )

        excepcion_lanzada = None
        try:
            use_case.execute(ID_MADRE, dto_reasignacion, usuario_actual)
        except Exception as exc:
            excepcion_lanzada = exc

        assert excepcion_lanzada is not None, (
            "RF-42 exige que una segunda inseminacion con un padre distinto "
            "sobre una hembra que ya tiene una relacion genealogica "
            "establecida sea rechazada, preservando la relacion original "
            "(1 madre y 1 padre maximo). El use case no lanzo ninguna "
            "excepcion -- de hecho, nunca consulta si el activo ya tiene un "
            "servicio/inseminacion previo con un padre DISTINTO antes de "
            "aceptar uno nuevo; solo verifica que el nuevo id_padre exista "
            "y este ACTIVO (lineas 62-79), sin comparar contra eventos "
            "anteriores del mismo activo."
        )
