# TC-M03-G63 / TC-M03-125 — nota técnica (TLS)

**RF-56** / CU-02. Seguridad de transporte hacia el motor de inferencia.

## Limitación

No hay en `src/telemetry` control de TLS ni rechazo de HTTP plano hacia M04.
El envío a M04 es `MotorInferenciaStubAdapter.enviar_paquete`, que no abre socket.

`POST /inferencia` no existe. El contrato Dev es `POST /iot/eventos-edge`.

Comprobar TLS del despliegue Dokploy implicaría inspeccionar o alterar la
configuración del servidor, o generar tráfico HTTP plano contra un entorno
compartido. Eso queda fuera de esta etapa.

## Componente que falta

Cliente real de M04 con política de canal (TLS ≥ versión acordada) y un
entorno autorizado para la prueba de transporte.

## Qué no se hizo

- No se creó colección Newman que fuerce HTTP.
- No se cambió configuración TLS.
- No se marcó el caso como PASS.
