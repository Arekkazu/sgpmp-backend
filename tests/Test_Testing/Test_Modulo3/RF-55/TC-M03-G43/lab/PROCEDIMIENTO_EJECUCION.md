# Procedimiento de ejecución G43 — una lectura por caso

**No ejecutar hasta autorización expresa** (laboratorio arrancado y aislamiento validado).

Firmware: worktree `.worktrees/sgpmp-rf55-validation`, clasificador `evaluar_simple`, `EDGE_SOURCE=fake`.  
Serial: `G43-LAB-001`. Umbral fixture 18–32 °C (no umbral 65).  
E6: 076 cuenta para el límite 60/min; un disparo único no debe 429.

## Por caso

| Caso | EDGE_FAKE_VARIABLES | Esperado MQTT/HTTP/PG |
|---|---|---|
| TC-M03-076 | `temperatura_ambiente:C:21:21` | `NORMAL`, sin `severidad`, 201, 1 fila |
| TC-M03-077 | `temperatura_ambiente:C:35:35` | `DESVIACION_SIMPLE` / `CRITICO`, 201, 1 fila |
| TC-M03-078 | `temperatura_ambiente:C:10:10` | igual 077, valor 10.0 |

Cada arranque de agente = **una** captura (o `EDGE_FRECUENCIA_CAPTURA_MIN` alto y un solo tick). Nuevo `id_evento` cada vez.

## Verificaciones (después de cada caso)

1. MQTT: un mensaje `sgpmp/G43-LAB-001/evento` (suscriptor de lab con usuario gateway, solo lectura).
2. HTTP: un POST `/iot/eventos-edge` (log del gateway / access log del backend).
3. Status **201**.
4. SQL **SELECT** (no UPDATE/DELETE):

```sql
SELECT id_evento_edge_computing, id_evento_edge, clasificacion_rf55, severidad
  FROM modulo3.eventos_edge_computing
 WHERE id_evento_edge = :id_del_mqtt;
```

Una fila. Valor en JSON/variables coherente.

5. `clasificacion_rf55` y valor según la tabla.
6. `count(*)` por `id_evento_edge` = 1.
7. Cero publicaciones a `sgpmp/+/command` (ACL deny + captura de topics).

Correlación: `metadata_edge.id_evento` = `id_evento_edge` = columna PG.

## Orden futuro sugerido

1. `validar-aislamiento.ps1`
2. Compose **solo** postgres + mosquitto de este archivo.
3. Restore + migraciones + semilla (otro permiso).
4. Backend `127.0.0.1:18043` con `DATABASE_URL` G43.
5. Gateway local: `MQTT_HOST=127.0.0.1` `MQTT_PORT=1884` `BACKEND_URL=http://127.0.0.1:18043`.
6. Suscriptor MQTT de evidencia.
7. Agente fake, un caso, parar.
8. Guardar evidencias en `Resultados/G43-OFICIAL/` (carpeta nueva de run), sin pisar PR1 ni offline 30-10.

Prohibido: POST DTO fabricado como clasificador; Raspberry; brokers G38/G41.
