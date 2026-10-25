"""
TC-M02-G61 (parte Pytest) - Registro exitoso de evento productivo valido
(TC-M02-106).

RF relacionado: RF-43, CU09 Gestionar eventos productivos y bajas
Categoria: Pruebas funcionales

Criterio de aceptacion (segun la ficha, sub-caso 1):
    Precondicion: "Activo ACTIVO en fase que habilita el tipo de producto
    (ej. PRODUCCION para LECHE)." Paso: "Registrar tipo_producto=LECHE,
    cantidad_producida=20, unidad_medida=litros." Resultado esperado:
    "HTTP 201. El evento queda registrado de forma inmutable, disponible
    para RF-51 y M06."

Por que Pytest con dobles de prueba y no Newman contra el backend en vivo:
la precondicion "activo en fase que habilita el tipo de producto" exige
haber llamado antes POST /activos-biologicos/{id}/fases (RF-37) al menos
una vez para ese activo. Confirmado en vivo contra TEST (dos veces, con
dos activos y dos ciclos productivos distintos) que ESE ENDPOINT SIEMPRE
responde 500: en cambiar_fase_use_case.py linea 72,
`self.repo.cerrar_gestion_activa(id_activo, ahora, dto.motivo_cambio or '')`
omite el cuarto parametro `usuario_id`, que tanto el puerto
(domain/repositories/activo_biologico_repository.py:56) como la
implementacion SQLAlchemy exigen como obligatorio -- un TypeError de
Python no relacionado con ningun trigger de BD, que igualmente cae en el
catch-all de error_handlers.py y sale como 500 ERROR_INTERNO. Esto bloquea
por completo la unica forma de llegar a la precondicion del RF-43 vía API:
ningun activo, de ninguna especie, puede llegar a tener una fase
productiva activa hoy en TEST. Ese hallazgo se documenta aparte con
Newman (tc_m02_g61.postman_collection.json, sub-caso 1 pasos 2 y 3),
mostrando ademas que sin ese precondicion el endpoint SI responde
correctamente 422 SIN_FASE_PRODUCTIVA_ACTIVA (validacion correcta, no es
el bug).

Este test aisla la logica propia de RF-43 (catalogo RF-16 por especie,
coincidencia de unidad de medida, habilitacion por ciclo, fechas,
duplicados) de ese bloqueo de infraestructura: con dobles de prueba se
simula una fase activa valida (equivalente a la que RF-37 deberia poder
crear) para verificar que, UNA VEZ satisfecha la precondicion, el camino
feliz de RF-43 funciona como exige el RF.

Datos usados (equivalentes a los reales de TEST, ver anotaciones en el
collection): especie Cachama Blanca (id_especie=4), unica especie con un
metrica de catalogo ya seedeada en TEST (id_metrica_produccion=16,
tipo_medicion=PESO, unidad_medida=kg, aplica_a_tipo_activo=AMBOS) --
Tilapia (id_especie=10) no tiene ninguna metrica seedeada, por lo que
Cachama es la unica especie viable para este camino feliz. `tipo_producto`
se envia en minuscula ("peso") porque el DTO lo normaliza a mayuscula
antes de comparar contra el catalogo.

Como correrlo (desde la raiz del repo, con las env vars seteadas):
    $env:DATABASE_URL = "postgresql://user:pass@localhost:5432/db"
    python -m pytest <ruta>\\test_tc_m02_106_evento_productivo_valido.py -v \
        --html=Resultados/reporte-TC-M02-106.html --self-contained-html
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from src.biological_assets.application.use_cases.gestion.registrar_evento_productivo_use_case import (
    RegistrarEventoProductivoUseCase,
)
from src.biological_assets.domain.entities.activo_biologico import (
    ActivoBiologico,
    EventoActivo,
    EventoProductivo,
    GestionFase,
)
from src.biological_assets.domain.repositories.parametros_especie_port import MetricaProductiva
from src.biological_assets.infrastructure.dto.registrar_evento_productivo_dto import (
    RegistrarEventoProductivoDTO,
)
from src.identity_access.infrastructure.dependencies import UsuarioActual

ID_ACTIVO = 152  # Cachama INDIVIDUAL, mismo id creado en la exploracion en vivo
ID_ESPECIE_CACHAMA = 4
ID_METRICA_PESO = 16
ID_CICLO_PRODUCTIVO_CACHAMA = 4


class TestTCM02106EventoProductivoValido:

    def test_registrar_evento_productivo_camino_feliz(self):
        """
        RF-43: con un activo ACTIVO, catalogo RF-16 valido para su especie
        y una fase productiva activa que habilita esa metrica, registrar
        un evento productivo (tipo_producto=PESO, cantidad=20, unidad=kg)
        debe aceptarse y quedar disponible para RF-51/M06.
        """
        activo = ActivoBiologico(
            id_especie=ID_ESPECIE_CACHAMA,
            tipo='INDIVIDUAL',
            origen_financiero='compra',
            id_infraestructura=6,
            id_estado=1,  # ACTIVO
            id_usuario=1,
            id_activo_biologico=ID_ACTIVO,
            fecha_inicio_ciclo=date(2026, 8, 1),
            fecha_creacion=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        fase_activa = GestionFase(
            id_gestion_fases=1,
            id_activo_biologico=ID_ACTIVO,
            id_ciclo_productiva=ID_CICLO_PRODUCTIVO_CACHAMA,
            nombre_ciclo='Ciclo completo cachama 2025-A',
            nombre_fase_actual='Fase juvenil cachama',
            paso_actual=1,
            total_pasos=2,
            fecha_inicio=datetime(2026, 8, 1, tzinfo=timezone.utc),
            fecha_finalizacion=None,
            es_activa=True,
            id_usuario=1,
        )

        metrica = MetricaProductiva(
            id_metrica_produccion=ID_METRICA_PESO,
            tipo_producto='PESO',
            unidad_medida='kg',
            aplica_a_tipo_activo='AMBOS',
        )

        activo_repo = MagicMock()
        activo_repo.obtener_por_id.return_value = activo
        activo_repo.obtener_fase_activa.return_value = fase_activa

        parametros_port = MagicMock()
        parametros_port.obtener_metrica_productiva.return_value = metrica

        ciclo_port = MagicMock()
        ciclo_port.metrica_habilitada_en_ciclo.return_value = True

        evento_repo = MagicMock()
        evento_repo.existe_productivo_duplicado.return_value = False
        evento_guardado = EventoActivo(
            id_activo_biologico=ID_ACTIVO,
            fecha=datetime(2026, 9, 9, tzinfo=timezone.utc),
            id_usuario=1,
            id_eventos=901,
            productivo=EventoProductivo(
                cantidad=Decimal('20'),
                id_metrica_produccion=ID_METRICA_PESO,
                id_ciclo_productivo=ID_CICLO_PRODUCTIVO_CACHAMA,
                tipo_producto='PESO',
                unidad_medida='kg',
            ),
        )
        evento_repo.guardar.return_value = evento_guardado

        db = MagicMock()
        use_case = RegistrarEventoProductivoUseCase(
            db=db,
            activo_repo=activo_repo,
            evento_repo=evento_repo,
            parametros_port=parametros_port,
            ciclo_port=ciclo_port,
            bitacora_repo=MagicMock(),
        )
        usuario_actual = UsuarioActual(id_usuario=1, id_token=1, id_rol=1, id_estado_cuenta=2)

        dto = RegistrarEventoProductivoDTO(
            tipo_producto='peso',
            cantidad_producida=Decimal('20'),
            unidad_medida='kg',
            fecha_evento=date(2026, 9, 9),
        )

        resultado = use_case.execute(ID_ACTIVO, dto, usuario_actual)

        assert resultado is evento_guardado, (
            'RF-43 exige que un evento productivo valido (activo ACTIVO, '
            'tipo_producto catalogado para la especie, unidad de medida '
            'correcta, fase productiva activa que habilita esa metrica, '
            'fecha valida y sin duplicados) sea aceptado y devuelto por '
            'el use case.'
        )
        assert resultado.productivo.cantidad == Decimal('20')
        assert resultado.productivo.tipo_producto == 'PESO'
        assert resultado.productivo.unidad_medida == 'kg'
        db.commit.assert_called()
        evento_repo.guardar.assert_called_once()
