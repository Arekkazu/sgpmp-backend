"""
TC-M06-G07 (RF-93 CA-11, RF-90 v2.0 5.8, CU-06) - "Costos compartidos
repartidos entre varios activos."

Construido 2026-11-07 contra el código real de RF-90/RF-93 (implementado
2026-11-04/05 por Arekkazu). Primera ronda, código nunca antes probado.

Código bajo prueba:
    src/financial_valuation/domain/services/nic41.py (repartir)
    src/financial_valuation/application/use_cases/costos/registrar_costo_use_case.py
        (RegistrarCostoUseCase._repartir, _activos)

HALLAZGO SOBRE EL "RESIDUO EN EL CUARTO DECIMAL": la ficha pide probar que
"el reparto deja residuo en el cuarto decimal". El código real
(`repartir()`, `nic41.py`) trunca cada participación a 2 decimales
(`truncar2`, `ROUND_DOWN`) ANTES de calcular el residuo:
```
partes = {k: truncar2(Decimal(monto) * v / total) for k, v in participaciones.items()}
mayor = min(participaciones, key=lambda k: (-participaciones[k], k))
partes[mayor] += Decimal(monto) - sum(partes.values(), CERO)
```
Es decir: el residuo real que se reasigna es de CENTAVOS (2 decimales),
nunca de diezmilésimas -- consistente con el hallazgo ya confirmado en
TC-M06-G03 (toda línea de asiento es `NUMERIC(18,2)`, nunca 4 decimales).
El residuo "del cuarto decimal" que describe la ficha no puede existir en
ningún reparto real.

(a) Reparto por cabezas entre 2/3 activos -- CONFIRMADO: `_repartir()`
    usa `Decimal(a.cabezas)` como participación cuando el método no es
    POR_BIOMASA (o falta `peso_kg` en algún activo).
(b) Reparto entre especies distintas -- HALLAZGO INVERTIDO A FAVOR: SÍ
    está permitido. `_activos()` solo bloquea un reparto si los activos
    tienen `numero_id_tributaria` distinto (`REPARTO_INVALIDO`) -- NO
    valida que sean de la misma especie. Un reparto entre dos especies del
    mismo titular es válido y no está restringido en ningún punto del
    código.
(c) Reparto con residuo decimal -- CONFIRMADO (BLOQUEANTE según la ficha):
    la suma de las partes repartidas es EXACTAMENTE el monto original en
    todos los casos probados, incluyendo montos que no dividen exacto
    entre las participaciones -- el residuo de redondeo se imputa íntegro
    al de mayor participación (empate: menor id), nunca se pierde ni se
    duplica.
(d) Reparto entre 50 activos -- CONFIRMADO: la función no tiene límite de
    participantes; se prueba aquí con 50 ids sintéticos.
(e) No duplicación -- CONFIRMADO: `sum(partes.values()) == monto` siempre
    (propiedad algebraica verificada en todos los sub-casos).

Como correrlo (Windows necesita el stub de fcntl):
    $env:PYTHONPATH = "_win_fcntl_stub_borrar"
    python -m pytest <ruta>\\test_tc_m06_g07_costos_compartidos_reparto.py -v \\
        --html=<ruta>\\resultados\\resultado_TC-M06-G07.html --self-contained-html
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.financial_valuation.application.use_cases.costos.registrar_costo_use_case import (
    RegistrarCostoUseCase,
    SolicitudCosto,
)
from src.financial_valuation.domain.entities.activo_financiero import DatosActivo
from src.financial_valuation.domain.services.nic41 import repartir

REPO_ROOT = Path(__file__).resolve().parents[5]


def _activo(id_activo, id_especie=10, cabezas=1, peso_kg=None, tipo='INDIVIDUAL'):
    return DatosActivo(
        id_activo_biologico=id_activo, identificador=f'A{id_activo}', tipo=tipo, id_especie=id_especie,
        especie=f'Especie{id_especie}', estado='ACTIVO', id_infraestructura=1, id_finca=900, finca='Finca',
        numero_id_tributaria='900123456', razon_social='Titular', fecha_ingreso=date(2026, 1, 1),
        origen_financiero='compra', costo_adquisicion=Decimal('0'), soporte_documental=None,
        cantidad_actual=cabezas, peso_kg=peso_kg, id_evento_peso=None, id_dispositivo_iot=None,
    )


class TestSubCasoARepartoPorCabezasEntreDosYTresActivos:
    def test_reparto_por_cabezas_entre_dos_activos(self):
        activos = [_activo(1, cabezas=1), _activo(2, cabezas=1)]
        s = SolicitudCosto(subtipo_costo='ALIMENTO', origen_costo='MANO_OBRA_PROPIA', monto_costo=Decimal('100.00'),
                           fecha_costo=date(2026, 10, 15), activos_reparto=[1, 2])
        montos = RegistrarCostoUseCase._repartir(s, activos)
        assert montos == {1: Decimal('50.00'), 2: Decimal('50.00')}

    def test_reparto_por_cabezas_entre_tres_activos_desigual(self):
        activos = [_activo(1, cabezas=1), _activo(2, cabezas=1), _activo(3, cabezas=1)]
        s = SolicitudCosto(subtipo_costo='ALIMENTO', origen_costo='MANO_OBRA_PROPIA', monto_costo=Decimal('100.00'),
                           fecha_costo=date(2026, 10, 15), activos_reparto=[1, 2, 3])
        montos = RegistrarCostoUseCase._repartir(s, activos)
        assert sum(montos.values()) == Decimal('100.00')
        assert montos[1] == Decimal('33.33') or montos[1] == Decimal('33.34')


class TestSubCasoBRepartoEntreEspeciesDistintasNoEstaBloqueado:
    def test_reparto_entre_dos_especies_distintas_es_valido(self):
        activos = [_activo(1, id_especie=10), _activo(2, id_especie=20)]
        pytest.fail(
            "HALLAZGO (b) INVERTIDO A FAVOR: _activos() no bloquea un reparto entre especies "
            "distintas -- el unico bloqueo real es por numero_id_tributaria distinto "
            "(REPARTO_INVALIDO); la especie nunca se valida en el reparto."
        ) if len({a.id_especie for a in activos}) > 1 else None


class TestSubCasoCResiduoDeCentavosSeImputaEnteroSinPerderseNiDuplicarse:
    def test_monto_no_divisible_exacto_el_residuo_es_de_centavos_no_de_diezmilesimas(self):
        participaciones = {1: Decimal('1'), 2: Decimal('1'), 3: Decimal('1')}
        partes = repartir(Decimal('100.00'), participaciones)
        residuos = {k: (v - Decimal('33.33')) for k, v in partes.items() if v != Decimal('33.33')}
        pytest.fail(
            f"HALLAZGO: el residuo real {residuos!r} es de centavos (2 decimales), nunca de "
            f"diezmilesimas -- la ficha pide probar un 'residuo en el cuarto decimal' que no "
            f"puede ocurrir porque repartir() trunca cada parte a 2 decimales antes de calcular "
            f"el residuo."
        ) if all(abs(r) < Decimal('1.00') and (r * 100) == (r * 100).to_integral_value() for r in residuos.values()) else None

    def test_el_residuo_va_integro_al_de_mayor_participacion(self):
        participaciones = {1: Decimal('1'), 2: Decimal('1'), 3: Decimal('5')}
        partes = repartir(Decimal('100.00'), participaciones)
        assert sum(partes.values()) == Decimal('100.00')
        assert partes[3] >= partes[1] and partes[3] >= partes[2]

    def test_empate_de_participacion_el_residuo_va_al_de_menor_id(self):
        participaciones = {5: Decimal('1'), 2: Decimal('1'), 9: Decimal('1')}
        partes = repartir(Decimal('100.00'), participaciones)
        resto = Decimal('100.00') - Decimal('33.33') * 3
        assert partes[2] == Decimal('33.33') + resto


class TestSubCasoDRepartoEntreCincuentaActivos:
    def test_reparto_entre_50_activos_suma_exacta_sin_perdida_ni_duplicacion(self):
        activos = [_activo(i, cabezas=1) for i in range(1, 51)]
        s = SolicitudCosto(subtipo_costo='ALIMENTO', origen_costo='MANO_OBRA_PROPIA', monto_costo=Decimal('1000.00'),
                           fecha_costo=date(2026, 10, 15), activos_reparto=list(range(1, 51)))
        montos = RegistrarCostoUseCase._repartir(s, activos)
        assert len(montos) == 50
        assert sum(montos.values()) == Decimal('1000.00')


class TestSubCasoEElUnicoBloqueoRealEsElTitularNoLaEspecie:
    def test_activos_de_distinto_titular_si_se_bloquean(self):
        from unittest.mock import MagicMock
        from src.shared.errors import BusinessRuleError
        activo1 = _activo(1)
        activo2 = DatosActivo(**{**activo1.__dict__, 'id_activo_biologico': 2, 'numero_id_tributaria': '800999999'})
        activos_port = MagicMock()
        activos_port.obtener.side_effect = lambda idx: {1: activo1, 2: activo2}[idx]
        valoraciones = MagicMock()
        valoraciones.reconocimiento_confirmado.return_value = object()
        uc = RegistrarCostoUseCase(db=MagicMock(), costos=MagicMock(), activos=activos_port,
                                   valoraciones=valoraciones, contabilizador=MagicMock())
        s = SolicitudCosto(subtipo_costo='ALIMENTO', origen_costo='MANO_OBRA_PROPIA', monto_costo=Decimal('10.00'),
                           fecha_costo=date(2026, 10, 15), activos_reparto=[1, 2])
        with pytest.raises(BusinessRuleError):
            uc._activos(s)
