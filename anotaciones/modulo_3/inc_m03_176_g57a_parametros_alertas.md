# INC-M03-176-G57A — Parámetros y reglas del sistema de alertas configurables (RF-57)

**RF:** RF-57, Restricción 3 ("Las reglas y umbrales no deben estar codificados de forma rígida; deben poder
modificarse sin despliegues de software") y Restricción 12. **Issue:** #755.
**Depende de:** G76 (#747), que parte de G75 (#745) y este de G73 (#744). Esta rama parte de G76.
**Estado:** parámetros **completos** entre esta rama y las anteriores de la serie. El **CRUD de reglas de
alertas** queda como tarea aparte, por decisión del equipo.

## Mapa de lo que pide QA

| Punto de QA | Dónde se resuelve | Cómo |
|---|---|---|
| **1.** Umbral de confianza Edge/IA (N35) y confianza mínima de CA-2 (G73 2.1) | **G73 (#744) + G76 (#747)** | `umbral_confianza_edge_ia` (valor base 0.85) y `rf57_umbral_confianza_minimo` (valor base 0.75), en `GET/PATCH /configuracion/parametros-alertas` |
| **2.** Tormenta N_sistema y N_unidad (N36) | **G76 (#747)** | `rf57_tormenta_alertas_por_minuto` y `…_unidad`, en el mismo endpoint |
| **3a.** Ventana de reevaluación de IA (G75 N17) | **G75 (#745) + G76** | `rf57_ventana_reevaluacion_min` (valor base 60) |
| **3b.** Ventana de deduplicación (N37) | **Este PR** | `rf57_ventana_deduplicacion_min` (valor base 30), usada por `GenararAlertaUseCase` (E4) |
| **3c.** Plazos SLA por severidad (G57B N44) | **Este PR** | `rf57_sla_critico_min`, `rf57_sla_moderado_min` y `rf57_sla_leve_min` (valores base 5, 30 y 120). Calculan `fecha_vencimiento` al crear la alerta (y la alerta reevaluada de G75). El worker de vencimiento (DEV-31) los respeta, porque compara con esa fecha |
| **4.** CRUD de reglas de alertas | **Pendiente (tarea aparte)** | Ver abajo |

**Todos los parámetros:**
- Se ven y se cambian con `GET` y `PATCH /configuracion/parametros-alertas`: recurso 21, Administrador.
- La escritura usa la validación y el lock de DEV-14, y deja el autor en `id_usuario_modificador`.
- Sin configurar, rigen los **valores base que publica el RF**; un valor inválido responde 400 al
  cambiarlo, o 503 si ya está guardado.

## Cambios de este PR

- `parametro_mlops.py`: `RF57_VENTANA_DEDUPLICACION` (base 30) y `RF57_SLA_*` (base 5, 30 y 120).
- `configurar_parametros_mlops_use_case.py`: límites y validación (entero ≥ 1).
- `ParametrosAlertasPort` y su adaptador: `obtener_ventana_deduplicacion_min` y `obtener_sla_minutos`.
- `Alerta.calcular_fecha_vencimiento(sla_minutos=None)`: usa los plazos configurados, o los valores base.
- `generar_alerta_use_case.py`: la deduplicación usa la ventana configurada y el vencimiento, el SLA
  configurado. `reevaluar_alerta_use_case.py`: la alerta reevaluada también usa el SLA configurado.
- `parametros_alertas_use_case.py` (G76): los cuatro parámetros nuevos en `GET/PATCH`.
- `tests/configuration/test_dev14_parametros_dinamicos.py`: dos pruebas afirmaban que, sin conflicto con la
  IA, **no se consultaba ningún parámetro**. Ahora la alerta lee la ventana y los SLA, que es lo que pide el
  ticket. Las pruebas conservan su intención: verifican que **no se consulte el umbral de confianza**.
- `anotaciones/modulo_9/dev14_parametros_operativos.md`: los parámetros nuevos.

**Notas:**
- **Cambios a futuro:** un cambio de SLA afecta a las alertas **nuevas**. Las ya creadas conservan el
  `fecha_vencimiento` con el que se generaron, porque es un dato inmutable de la alerta.
- **Escalamiento:** las reglas de escalamiento (a quién se escala: Veterinario o Administrador) siguen fijas
  en `VencerAlertasSlaUseCase`. No se piden como parámetro numérico y quedan con el CRUD de reglas.

## Pendiente: CRUD de reglas de alertas (tarea aparte)

Existe `modulo3.reglas_alertas`, pero hoy el motor de RF-57 del backend **no evalúa con esas reglas**. Solo
se sincronizan al Edge (DEV-08). Además, sus datos en DEV son inconsistentes (ver G68). Un CRUD útil
requiere antes definir:
1. **Uso:** si el backend debe evaluar con `reglas_alertas` (reemplazando las bandas base de G68) o si las
   reglas son solo del Edge.
2. **Formato:** el de `umbrales_severidad` (hoy, claves ALTA, MEDIA, BAJA y CRITICA mezcladas).
3. **Permisos:** RBAC, con el conflicto de roles de G57A, #754.

## Evidencia

**Pruebas unitarias.** `tests/telemetry/test_inc_m03_176_g57a_parametros_dedup_sla.py`, sin BD:
- **Adaptador:** sin configurar devuelve los valores base (30; 5, 30 y 120); configurado prevalece; un valor
  inválido falla.
- **Vencimiento:** usa el SLA dado o el base.
- **Caso de uso:** usa la ventana y el SLA del puerto.

**Pruebas de integración.** `tests/integration/test_inc_m03_176_g57a_parametros_dedup_sla.py`, por API y con
PostgreSQL real:

| Caso de QA | Prueba | Resultado |
|---|---|---|
| N37 | `test_n37_consulta_y_cambio_de_la_ventana_de_deduplicacion` | `GET` muestra la ventana `VALOR_BASE` 30. Una alerta de hace 10 min **se consolida**. Con `PATCH` a 5, la misma situación **crea una alerta nueva** |
| G57B N44 | `test_n44_plazos_sla_configurados_se_aplican_al_vencimiento` | Con `PATCH` de SLA 2, 15 y 45, las alertas CRITICO, MODERADO y LEVE vencen a +2, +15 y +45 min |
| Base | `test_sin_configurar_el_vencimiento_usa_los_plazos_del_rf` | CRITICO vence a +5 min |
| Validación | `test_valores_invalidos_son_400[...]` | 0, 2.5 y `"x"` → 400 |

### Ejecución (2026-10-28)

- **BD efímera:** `pruebas_g57a_test` en el PostgreSQL 18 local, con `alembic upgrade head` hasta
  `ebbb160365e5`, en un contenedor con la imagen del backend. Se borró al terminar.
- **Resultados:**

```
Unitarias (G57A + G76 + G75 + G73 + DEV-14, DEV-49, DEV-41)              136 passed
Integración (G57A + G76 + G75 + G73 + DEV-14, DEV-49, DEV-30)            72 passed, 6 skipped
Suite completa (sin red): 2316 passed; mismos 4 failed / 25 errors preexistentes que la base
```

## Para QA

- **N35, N36, N37, G57B N44 y G75 N17:** se ejecutan con `GET` y `PATCH /configuracion/parametros-alertas`,
  usando un usuario Administrador. Para probar el vencimiento en una corrida corta, basta con bajar los SLA.
- **Reglas de alertas:** quedan pendientes de la tarea aparte.
