# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-10-26 | Arekkazu | INC-M04-196-G026 RF-68: modelo de estimación de riesgo de contagio |
"""RF-68 — Modelo 4: probabilidad de contagio de un lote.

    P_contagio = W_fs·Fs + W_fa·Fa + W_fd·Fd

Lógica pura (sin BD): el caso de uso le entrega los datos y la configuración de RF-65.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

#: Discretización (Salida): 0 Bajo, 1 Medio, 2 Alto. Las fronteras exactas del 50 % y
#: 70 % (TC-M04-G027) caen en la clase superior.
FRONTERA_MEDIO = Decimal("0.50")
FRONTERA_ALTO = Decimal("0.70")
NIVELES = {0: "BAJO", 1: "MEDIO", 2: "ALTO"}

#: Un individuo cuenta como enfermo con P(Riesgo Alto) > 0.70 (Entradas: n_enfermos_detectados).
PROBABILIDAD_ENFERMO = Decimal("0.70")

#: Sincronización temporal (Precondición 5 / CA-8, CA-11, CA-13): ≤ 30 s normal,
#: hasta 35 s degradado (jitter), más no se ejecuta.
SINCRONIA_NORMAL = timedelta(seconds=30)
SINCRONIA_MAXIMA = timedelta(seconds=35)
#: E5/E9: inferencias de RF-66 de más de 30 min no se usan; ambiente de más de 10 min, sin Fa.
VIGENCIA_INFERENCIA = timedelta(minutes=30)
VIGENCIA_AMBIENTAL = timedelta(minutes=10)
#: E1: con RF-66 para menos del 50 % del lote se calcula sin Fs.
COBERTURA_MINIMA_FS = Decimal("0.50")
#: E4 / Validación de Modelo: con menos del 60 % de sensores operativos no se ejecuta.
SENSORES_MINIMOS_PCT = Decimal("60")
#: Paso 5: data_quality_score < 0.6 → modo degradado.
CALIDAD_MINIMA = Decimal("0.6")

PESOS_POR_DEFECTO = {"fs": Decimal("0.5"), "fa": Decimal("0.3"), "fd": Decimal("0.2")}

CONTEO_INDIVIDUAL = "CONTEO_INDIVIDUAL"
SCORE_POBLACIONAL = "SCORE_POBLACIONAL"


class DatosContagioError(Exception):
    """El modelo no se ejecuta. ``codigo`` es el evento de RF-73 que corresponde."""

    def __init__(self, codigo: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


@dataclass(frozen=True)
class SalidaInferencia:
    """Una salida de RF-66 de un individuo del lote."""
    probabilidad_riesgo_alto: Decimal
    fecha_inferencia: datetime
    id_activo_biologico: Optional[int] = None


@dataclass(frozen=True)
class LecturaAmbiental:
    temperatura: Optional[Decimal]
    humedad_relativa: Optional[Decimal]
    fecha_captura: datetime


@dataclass(frozen=True)
class ParametrosContagio:
    """Lo que RF-68 toma de la configuración activa de RF-65."""
    w_fs: Decimal
    w_fa: Decimal
    w_fd: Decimal
    temp_min: Optional[Decimal]
    temp_max: Optional[Decimal]
    hr_min: Optional[Decimal]
    hr_max: Optional[Decimal]
    densidad_maxima: Optional[Decimal]


@dataclass
class ResultadoRiesgoContagio:
    id_lote: int
    probabilidad_contagio: Decimal
    nivel_riesgo_contagio: int
    confianza_baja: bool
    data_quality_score: Decimal
    factor_sanitario: Optional[Decimal]
    factor_ambiental: Optional[Decimal]
    factor_densidad: Optional[Decimal]
    pesos_aplicados: dict[str, Decimal]
    factores_ausentes: list[str]
    motivos_degradacion: list[str]
    definicion_fs: Optional[str]
    n_enfermos_detectados: Optional[int]
    total_activos_lote: Optional[int]
    porcentaje_sensores_activos: Decimal
    densidad_asumida: bool
    fecha_calculo: datetime
    id_resultado_contagio: Optional[int] = None
    id_configuracion_motor: Optional[int] = None
    config_version: Optional[int] = None
    id_area_productiva: Optional[int] = None
    alerta_id: Optional[int] = None
    desde_cache: bool = False
    huella_entradas: str = ""
    variables_ambientales: dict = field(default_factory=dict)

    @property
    def nivel_texto(self) -> str:
        return NIVELES[self.nivel_riesgo_contagio]

    @property
    def modo_ejecucion(self) -> str:
        return "DEGRADADO" if self.confianza_baja else "NORMAL"


def _acotar(valor: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), valor))


def _normalizar(actual: Decimal, minimo: Decimal, maximo: Decimal) -> Decimal:
    return _acotar((actual - minimo) / (maximo - minimo))


def _q(valor: Decimal, digitos: str = "0.0001") -> Decimal:
    return valor.quantize(Decimal(digitos), rounding=ROUND_HALF_UP)


def validar_pesos(p: ParametrosContagio) -> None:
    """Paso 5.2: cada peso en [0, 1] y suma 1.0 antes de calcular (ERROR_CONFIGURACION_PESOS)."""
    pesos = (p.w_fs, p.w_fa, p.w_fd)
    if any(w < 0 or w > 1 for w in pesos) or abs(sum(pesos) - Decimal("1")) >= Decimal("0.001"):
        raise DatosContagioError(
            "ERROR_CONFIGURACION_PESOS",
            "Los pesos de contagio de RF-65 deben estar entre 0 y 1 y sumar 1.0.",
        )


def discretizar(probabilidad: Decimal) -> int:
    if probabilidad >= FRONTERA_ALTO:
        return 2
    if probabilidad >= FRONTERA_MEDIO:
        return 1
    return 0


def calcular_riesgo_contagio(
    *,
    id_lote: int,
    parametros: ParametrosContagio,
    ahora: datetime,
    salidas_rf66: list[SalidaInferencia],
    total_activos_lote: Optional[int],
    n_enfermos_detectados: Optional[int] = None,
    score_anomalia: Optional[Decimal] = None,
    ambiente: Optional[LecturaAmbiental] = None,
    densidad_poblacional: Optional[Decimal] = None,
    porcentaje_sensores_activos: Decimal = Decimal("100"),
) -> ResultadoRiesgoContagio:
    """RF-68 pasos 1–7 con sus flujos alternos. Lanza ``DatosContagioError`` cuando no se ejecuta."""
    validar_pesos(parametros)

    # E4: menos del 60 % de sensores operativos.
    if porcentaje_sensores_activos < SENSORES_MINIMOS_PCT:
        raise DatosContagioError(
            "ERROR_DATOS_INSUFICIENTES",
            f"Solo el {porcentaje_sensores_activos}% de los sensores del lote está operativo (mínimo 60%).",
        )

    motivos: list[str] = []

    # E5: inferencias de más de 30 min se descartan.
    vigentes = [s for s in salidas_rf66 if ahora - s.fecha_inferencia <= VIGENCIA_INFERENCIA]
    if salidas_rf66 and not vigentes and score_anomalia is None:
        raise DatosContagioError(
            "ERROR_DATOS_INSUFICIENTES",
            "Las salidas de RF-66 tienen más de 30 minutos: no se ejecuta el modelo.",
        )
    if len(vigentes) < len(salidas_rf66):
        motivos.append("INFERENCIAS_DESACTUALIZADAS_DESCARTADAS")

    # Precondición 5 / CA-8: sincronización entre las salidas y el dato ambiental.
    instantes = [s.fecha_inferencia for s in vigentes]
    ambiente_vigente = ambiente is not None and ahora - ambiente.fecha_captura <= VIGENCIA_AMBIENTAL
    if ambiente_vigente:
        instantes.append(ambiente.fecha_captura)
    if len(instantes) > 1:
        desfase = max(instantes) - min(instantes)
        if desfase > SINCRONIA_MAXIMA:
            raise DatosContagioError(
                "ERROR_DATOS_DESINCRONIZADOS",
                f"Las entradas difieren {desfase.total_seconds():.0f} s (máximo 35 s): no se ejecuta el modelo.",
            )
        if desfase > SINCRONIA_NORMAL:
            motivos.append("DATOS_NO_SINCRONIZADOS")

    # Fs: proporción de enfermos (RF-66) o score de anomalía del área (POBLACIONAL, RFC-009).
    fs: Optional[Decimal] = None
    definicion_fs: Optional[str] = None
    total = total_activos_lote or (len(vigentes) or None)
    enfermos = n_enfermos_detectados
    if score_anomalia is not None:
        fs, definicion_fs = _acotar(Decimal(score_anomalia)), SCORE_POBLACIONAL
    elif vigentes and total:
        if enfermos is None:
            enfermos = sum(1 for s in vigentes if s.probabilidad_riesgo_alto > PROBABILIDAD_ENFERMO)
        cobertura = Decimal(len(vigentes)) / Decimal(total)
        if cobertura >= COBERTURA_MINIMA_FS:
            fs, definicion_fs = _acotar(Decimal(enfermos) / Decimal(total)), CONTEO_INDIVIDUAL
        else:
            motivos.append("COBERTURA_RF66_MENOR_AL_50")  # E1
    else:
        motivos.append("SIN_SALIDAS_RF66")  # CA-5

    # Fa: temperatura y humedad normalizadas con los rangos de RF-65 (CA-12).
    fa: Optional[Decimal] = None
    if ambiente is not None and not ambiente_vigente:
        motivos.append("DATOS_AMBIENTALES_DESACTUALIZADOS")  # E9
    elif ambiente is not None:
        partes = []
        if ambiente.temperatura is not None and None not in (parametros.temp_min, parametros.temp_max) \
                and parametros.temp_max > parametros.temp_min:
            partes.append(_normalizar(ambiente.temperatura, parametros.temp_min, parametros.temp_max))
        if ambiente.humedad_relativa is not None and None not in (parametros.hr_min, parametros.hr_max) \
                and parametros.hr_max > parametros.hr_min:
            partes.append(_normalizar(ambiente.humedad_relativa, parametros.hr_min, parametros.hr_max))
        if len(partes) == 2:
            fa = (partes[0] + partes[1]) / 2
        else:
            motivos.append("DATOS_AMBIENTALES_INCOMPLETOS")  # E3
    else:
        motivos.append("DATOS_AMBIENTALES_INCOMPLETOS")  # E3

    # Fd: densidad / densidad máxima. Densidad desconocida → capacidad máxima (preventivo).
    fd: Optional[Decimal] = None
    densidad_asumida = False
    if parametros.densidad_maxima and parametros.densidad_maxima > 0:
        if densidad_poblacional is None:
            fd, densidad_asumida = Decimal("1"), True
        else:
            fd = _acotar(Decimal(densidad_poblacional) / parametros.densidad_maxima)
    else:
        motivos.append("DENSIDAD_MAXIMA_NO_CONFIGURADA")

    factores = {"fs": fs, "fa": fa, "fd": fd}
    pesos_config = {"fs": parametros.w_fs, "fa": parametros.w_fa, "fd": parametros.w_fd}
    disponibles = {k for k, v in factores.items() if v is not None}
    if not disponibles:
        raise DatosContagioError("ERROR_DATOS_INSUFICIENTES", "No hay ningún factor disponible para el lote.")
    ausentes = sorted(set(factores) - disponibles)
    # Si falta algún factor, los pesos de los disponibles se recalculan proporcionalmente.
    suma_disponible = sum(pesos_config[k] for k in disponibles)
    if suma_disponible == 0:
        pesos = {k: (Decimal("1") / len(disponibles) if k in disponibles else Decimal("0")) for k in factores}
    else:
        pesos = {k: (pesos_config[k] / suma_disponible if k in disponibles else Decimal("0")) for k in factores}

    probabilidad = _acotar(sum(pesos[k] * factores[k] for k in disponibles))
    nivel = discretizar(probabilidad)
    # Consistencia con la inferencia individual (CA-7, E6, RNF-03).
    if fs is not None and definicion_fs == CONTEO_INDIVIDUAL:
        if fs > FRONTERA_ALTO:
            nivel = 2
        elif fs > FRONTERA_MEDIO:
            nivel = max(nivel, 1)

    # Paso 5: calidad de datos (cobertura, sensores, frescura, completitud).
    cobertura = Decimal("1") if score_anomalia is not None else (
        min(Decimal("1"), Decimal(len(vigentes)) / Decimal(total)) if total else Decimal("0")
    )
    frescura = Decimal("1") if ambiente_vigente and "DATOS_NO_SINCRONIZADOS" not in motivos else Decimal("0.5")
    completitud = Decimal(len(disponibles)) / Decimal(3)
    calidad = _q((cobertura + _acotar(porcentaje_sensores_activos / 100) + frescura + completitud) / 4, "0.001")
    if calidad < CALIDAD_MINIMA:
        motivos.append("CALIDAD_DATOS_BAJA")

    return ResultadoRiesgoContagio(
        id_lote=id_lote,
        probabilidad_contagio=_q(probabilidad),
        nivel_riesgo_contagio=nivel,
        confianza_baja=bool(ausentes) or bool(motivos),
        data_quality_score=calidad,
        factor_sanitario=_q(fs) if fs is not None else None,
        factor_ambiental=_q(fa) if fa is not None else None,
        factor_densidad=_q(fd) if fd is not None else None,
        pesos_aplicados={k: _q(v, "0.001") for k, v in pesos.items()},
        factores_ausentes=ausentes,
        motivos_degradacion=motivos,
        definicion_fs=definicion_fs,
        n_enfermos_detectados=enfermos,
        total_activos_lote=total,
        porcentaje_sensores_activos=porcentaje_sensores_activos,
        densidad_asumida=densidad_asumida,
        fecha_calculo=ahora,
    )
