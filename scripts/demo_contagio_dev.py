# | Fecha      | Nombre   | Que se hizo                                                       |
# |------------|----------|-------------------------------------------------------------------|
# | 2026-11-02 | Arekkazu | RFC-021: script de la demostración de contagio entre áreas en DEV |
"""Demostración del contagio entre áreas en DEV (finca 1), operando los Edge simulados de oracle-server.

Escenario, áreas y aristas: anotaciones/modulo_4/plan_implementacion_modelos_ia_dev.md §9. Solo toca los
contenedores `edge-sim-*`; el Estanque Checho (área 1, sensores reales) no se toca.

    python scripts/demo_contagio_dev.py foco pot1    # BOV-001 (Potrero 1) con fiebre
    python scripts/demo_contagio_dev.py foco cor1    # TER-001 (Corral 1) con fiebre
    python scripts/demo_contagio_dev.py calor pot2   # 33–36 °C y 85–95 % en el área (pot1, cor1, pot2)
    python scripts/demo_contagio_dev.py normal       # los tres simuladores a valores normales y 5 min
    python scripts/demo_contagio_dev.py estado       # última predicción y contagio de cada área

`foco` y `calor` bajan la captura y la transmisión del simulador de 5 a 1 min: el Edge guarda cada
lectura hasta la siguiente transmisión, así que con 5 min la fiebre tarda de 5 a 10 min en llegar al
modelo; con 1 min, 1 a 2. `normal` lo devuelve a 5. Con `DEMO_DATABASE_URL` (basta solo lectura)
`foco` muestra el estado cada 30 s hasta que el foco llega a ALTO.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

SSH = "oracle-server"
IMAGEN = "edge-sim-bov:2dd79e7-ntp"
#: clave → (contenedor, id_infraestructura, nombre del área)
AREAS = {"pot1": ("edge-sim-bov", 2, "Potrero 1"), "cor1": ("edge-sim-ter", 3, "Corral 1"),
         "pot2": ("edge-sim-pot2", 4, "Potrero 2")}
#: Rangos de EDGE_FAKE_VARIABLES ("variable:unidad" → "min:max"). Potrero 2 no tiene modelo: no hace foco.
FIEBRE = {"pot1": {"Frecuencia Cardiaca:bpm": "90:100", "Temperatura Corporal:°C": "40.2:40.8"},
          "cor1": {"Frecuencia Cardiaca:bpm": "118:128", "Temperatura Corporal:°C": "40.8:41.3"}}
CALOR = {"Temperatura Ambiental:°C": "33:36", "Humedad Relativa:%": "85:95"}
RAPIDO = ("s/^EDGE_FRECUENCIA_CAPTURA_MIN=.*/EDGE_FRECUENCIA_CAPTURA_MIN=1/;"
          "s/^EDGE_INTERVALO_TRANSMISION_MIN=.*/EDGE_INTERVALO_TRANSMISION_MIN=1/")

ESTADO_SQL = """
SELECT a.nombre, ab.identificador,
       (SELECT r.nivel_riesgo || ' ' || coalesce(p.nombre, '-') || ' ' || round(r.confianza_global * 100) || '% '
               || to_char(r.fecha_inferencia AT TIME ZONE 'America/Bogota', 'HH12:MI:SS AM')
          FROM modulo4.resultados_inferencia r LEFT JOIN modulo9.patologias p USING (id_patologia)
         WHERE r.id_activo_biologico = ab.id_activo_biologico ORDER BY r.fecha_inferencia DESC LIMIT 1),
       c.nivel, c.texto, c.fecha_calculo
FROM modulo2.activos_biologicos ab
JOIN modulo9.infraestructuras a USING (id_infraestructura)
LEFT JOIN LATERAL (
    SELECT (ARRAY['BAJO', 'MEDIO', 'ALTO'])[x.nivel_riesgo_contagio + 1] AS nivel, x.fecha_calculo,
           round(x.probabilidad_contagio * 100, 1) || '%'
           || coalesce(' Fv ' || (x.variables_ambientales_snap -> 'exposicion' ->> 'fv'), '')
           || ' ' || to_char(x.fecha_calculo AT TIME ZONE 'America/Bogota', 'HH12:MI:SS AM') AS texto
      FROM modulo4.resultados_riesgo_contagio x
     WHERE x.id_activo_biologico = ab.id_activo_biologico ORDER BY x.fecha_calculo DESC LIMIT 1) c ON true
WHERE ab.id_infraestructura IN (2, 3, 4)
ORDER BY ab.id_infraestructura
"""


def _ssh(comando: str) -> None:
    subprocess.run(["ssh", "-o", "BatchMode=yes", SSH, comando], check=True, timeout=120)


def _editar(rangos: dict[str, str]) -> str:
    """Expresión sed que cambia el min:max de cada variable en EDGE_FAKE_VARIABLES."""
    return ";".join(f"s#({v}:)[^:]+:[^:]+:#\\1{r}:#" for v, r in rangos.items())


def _recrear(contenedor: str, preparar: str) -> None:
    env = f"~/{contenedor}/edge-agent.env"
    etiqueta = contenedor.replace("edge-sim-", "simulador-") + "-demo-contagio"
    _ssh(f"set -e; {preparar.format(env=env)}; docker rm -f {contenedor} >/dev/null; "
         f"docker run -d --name {contenedor} --restart unless-stopped --network host --env-file {env} "
         f"-v {contenedor}-data:/var/lib/sgpmp-edge --label sgpmp.proposito={etiqueta} {IMAGEN} >/dev/null")


def _filas():
    url = os.environ.get("DEMO_DATABASE_URL")
    if not url:
        return None
    from sqlalchemy import create_engine, text

    motor = create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})
    with motor.connect() as cx:
        return cx.execute(text(ESTADO_SQL)).all()


def estado() -> None:
    filas = _filas()
    if filas is None:
        sys.exit("Falta DEMO_DATABASE_URL (BD de DEV, basta solo lectura).")
    for area, animal, rf66, _, contagio, _ in filas:
        print(f"{area:10} {animal:13} RF-66: {rf66 or 'sin predicción':38} Contagio: {contagio or '-'}")
    print()


def foco(clave: str) -> None:
    contenedor, id_area, nombre = AREAS[clave]
    _recrear(contenedor, f"sed -i -E '{_editar(FIEBRE[clave])};{RAPIDO}' {{env}}")
    inicio = datetime.now(timezone.utc)
    print(f"{nombre}: fiebre activada; el modelo la ve en 1 a 2 min.")
    for _ in range(10):
        time.sleep(30)
        filas = _filas()
        if filas is None:
            return
        estado()
        if any(f[0] == nombre and f[3] == "ALTO" and f[5] >= inicio for f in filas):
            return


def calor(clave: str) -> None:
    contenedor, _, nombre = AREAS[clave]
    _recrear(contenedor, f"sed -i -E '{_editar(CALOR)};{RAPIDO}' {{env}}")
    print(f"{nombre}: calor activado (33–36 °C, 85–95 %).")


def normal() -> None:
    for contenedor, _, nombre in AREAS.values():
        _recrear(contenedor, f"cp ~/{contenedor}/edge-agent.env.normal {{env}}")
        print(f"{nombre}: valores normales, 5 min.")


if __name__ == "__main__":
    acciones = {"foco": foco, "calor": calor, "normal": normal, "estado": estado}
    if len(sys.argv) < 2 or sys.argv[1] not in acciones:
        sys.exit(__doc__)
    acciones[sys.argv[1]](*sys.argv[2:])
