"""Valida sin red los cuerpos de las unicas escrituras permitidas en G92."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

GRUPO = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[6]
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))

from src.configuration.infrastructure.dto.registrar_sensor_dto import RegistrarSensorDTO  # noqa: E402
from src.telemetry.infrastructure.dto.ingerir_telemetria_dto import IngerirTelemetriaDTO  # noqa: E402
from src.telemetry.infrastructure.dto.procesar_evento_alerta_dto import EventoAlertaExternoDTO  # noqa: E402
from src.telemetry.domain.entities.reglas_base_rf57 import condicion_minima, evaluar_evento  # noqa: E402

codigo = """
import { relojServidor } from './g92.mjs';
import { cuerpoSensor, cuerpoTelemetria, cuerpoAlerta } from './lib/g92_escenario.mjs';
const servidor = process.argv[1];
let transcurrido = 0;
const reloj = relojServidor({ ahora: () => transcurrido });
reloj.observar(servidor);
reloj.fijarInicio(servidor);
transcurrido = 10000;
reloj.observar(new Date(Date.parse(servidor) + transcurrido).toISOString());
const asociacion = '2026-10-30T01:44:00.000Z';
const calibracion = '2026-10-30T00:00:00.000Z';
const marcas = [];
for (let i = 0; i < 65; i++) marcas.push(await reloj.marca({ asociacion, calibracion }));
const base = { dispositivo: 785, sensor: 1196, serial: 'SERIAL_LOCAL_FICTICIO', marca: marcas[0] };
const salida = {
  tiempo: { servidor, asociacion, calibracion, marcas },
  sensor: cuerpoSensor('RLS'),
  telemetrias: [1202, 1203, 1204, 1196].map((sensor, i) =>
    cuerpoTelemetria({ ...base, sensor, marca: marcas[i], color: 'VERDE' })),
  alertas: [
    cuerpoAlerta({ dispositivo: 786, sensor: 1204, serial: base.serial,
      marca: marcas[63], telemetria: 401, color: 'ROJO' }),
    cuerpoAlerta({ dispositivo: 785, sensor: 1196, serial: base.serial,
      marca: marcas[64], telemetria: 402, color: 'ROJO' })]
};
console.log(JSON.stringify(salida));
"""
marca = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
salida = subprocess.run(
    ["node", "--input-type=module", "-e", codigo, marca], cwd=GRUPO,
    check=True, capture_output=True, text=True, encoding="utf-8",
)
cuerpos = json.loads(salida.stdout)
tiempo = cuerpos["tiempo"]
servidor_dt = datetime.fromisoformat(tiempo["servidor"].replace("Z", "+00:00"))
asociacion_dt = datetime.fromisoformat(tiempo["asociacion"].replace("Z", "+00:00"))
calibracion_dt = datetime.fromisoformat(tiempo["calibracion"].replace("Z", "+00:00"))
marcas_dt = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in tiempo["marcas"]]
assert len(marcas_dt) == 65
assert marcas_dt[0] == servidor_dt - timedelta(seconds=60)
assert marcas_dt[-1] == servidor_dt - timedelta(seconds=44)
assert all(
    max(asociacion_dt, calibracion_dt) <= x <= servidor_dt - timedelta(seconds=43)
    for x in marcas_dt
)
assert all(b - a == timedelta(milliseconds=250) for a, b in
           zip(marcas_dt, marcas_dt[1:], strict=False))
RegistrarSensorDTO.model_validate(cuerpos["sensor"])
for i, cuerpo in enumerate(cuerpos["telemetrias"]):
    IngerirTelemetriaDTO.model_validate(cuerpo)
    assert cuerpo["valor"] == 25
    assert cuerpo["timestamp_captura"] == tiempo["marcas"][i]
for cuerpo, severidad in zip(cuerpos["alertas"], ("CRITICO", "CRITICO"), strict=True):
    dto = EventoAlertaExternoDTO.model_validate(cuerpo)
    assert condicion_minima("ESTRES_TERMICO", dto.tipo_variable, dto.valor, dto.correlacion_variables) is None
    assert evaluar_evento(dto.tipo_variable, dto.valor, dto.correlacion_variables).severidad == severidad
print("OK G92: sensor RLS, 65 marcas, 4 lecturas a 25 C y 2 alertas RF-57; sin red")
