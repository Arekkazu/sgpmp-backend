"""Valida sin red los cuerpos reales de G89 contra DTO y reglas RF-57 locales."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


GRUPO = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[6]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))

from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import (  # noqa: E402
    EventoAlertaExternoDTO,
    ProcesarEventoAlertaDTO,
)
from src.telemetry.domain.entities.reglas_base_rf57 import (  # noqa: E402
    calcular_thi,
    companera_faltante,
    condicion_minima,
    evaluar_evento,
)


marca = datetime.now(timezone.utc).isoformat()
codigo = """
import { cuerpoAlerta } from './lib/g89_escenario.mjs';
const cuerpos = ['CRITICO', 'LEVE', 'MODERADO'].map((severidad) =>
  cuerpoAlerta({serial: 'SERIAL_LOCAL_FICTICIO', severidad,
    idTelemetria: 101, timestampEvento: process.argv[1]}));
console.log(JSON.stringify(cuerpos));
"""
salida = subprocess.run(
    ["node", "--input-type=module", "-e", codigo, marca],
    cwd=GRUPO,
    check=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
)
cuerpos = json.loads(salida.stdout)
for cuerpo, esperada in zip(cuerpos, ("CRITICO", "LEVE", "MODERADO"), strict=True):
    interno = ProcesarEventoAlertaDTO.model_validate(cuerpo)
    externo = EventoAlertaExternoDTO.model_validate(cuerpo)
    assert interno.tipo_variable == externo.tipo_variable == "TEMPERATURA_AMBIENTAL"
    assert externo.id_telemetria == 101
    assert companera_faltante(externo.tipo_variable, externo.correlacion_variables) is None
    thi = calcular_thi(externo.valor, Decimal("40"))
    evaluacion = evaluar_evento(
        externo.tipo_variable, externo.valor, externo.correlacion_variables
    )
    assert evaluacion.evaluable and evaluacion.severidad == esperada
    assert evaluacion.detalle["thi"] == str(thi)
    assert condicion_minima(
        "ESTRES_TERMICO", externo.tipo_variable, externo.valor,
        externo.correlacion_variables,
    ) is None
    print(f"{esperada}: temperatura={externo.valor}, THI={thi}, DTO=OK, condición=OK")
