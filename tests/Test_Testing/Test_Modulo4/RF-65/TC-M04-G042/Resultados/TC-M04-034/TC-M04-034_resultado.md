# TC-M04-034 — Informe de ejecución (G042)

Fecha: 2026-10-25. Rama `laura` @ `f0ca7248`. Responsable matriz: Laura Lopez.  
Estado inicial registrado: No ejecutado.  
Capa exigida por matriz: **API / Postman**. CU-02. Prioridad Alta. Tipo: Funcional / Negativa.

**No se usó el identificador TC-M04-004 como ID de este informe.** TC-M04-004 queda como referencia histórica del script `test_tc_m04_g042.py` y de `Resultados/TC-M04-004/` (no se sobrescribió).

Sin commit, push ni cambios en `src/` ni en el script de pruebas.

---

## 1. Identificación

| Campo | Valor |
|---|---|
| Grupo | **TC-M04-G042** |
| Subcaso matriz | **TC-M04-034** |
| RF registrado en matriz | RF-65 |
| Caso | Validar pesos del modelo de contagio en la configuración (Wfs, Wfa, Wfd) |
| Endpoint Dev asociado | `POST /prediccion/motor-ia` (CU-02) |
| Script existente (ID interno erróneo) | `test_tc_m04_g042.py` — funciones `test_tc_m04_004_*` |

---

## 2. Trazabilidad RF-65 vs RF-68

**RF-65 (ficha):** no hay ficha versionada en el workspace. No se encontró el texto Wfs/Wfa/Wfd en entradas, restricciones, proceso ni criterios de RF-65.

**Código CU-02 (carpeta RF-65 / motor):** sí existen `w_factor_sanitario`, `w_factor_ambiental`, `w_factor_densidad` en DTO, entidad, ORM `modulo4.configuraciones_motor_ia` y `ConfigurarMotorUseCase._validar_comunes` (suma = 1.0 ± 0.001 → `PESOS_CONTAGIO_INVALIDOS`, atributo HTTP 422). Los curls Dev (`anotaciones/modulo_4/curls_m04_cu02_configurar_motor_ia.md`) documentan ese 422. **No** hay rango individual 0–1 en el use case. RFC-009 no menciona estos pesos.

**RF-68:** `anotaciones/implementacion_rfc006_rfc009_rfc011.md` §5: RF-68 v1.1 pide `definicion_fs` e `id_area_productiva` en la salida de riesgo de contagio; **no implementado** (mock IA). **No** nombra Wfs/Wfa/Wfd ni `w_factor_*`.

**Hipótesis matriz (pesos = RF-68):** **no confirmada.** Falta la ficha RF-65 y la ficha RF-68 que definan Wfs/Wfa/Wfd, rangos 0–1 y dueño del criterio.

Campos Dev ≈ nombres de matriz: Wfs ↔ `w_factor_sanitario`, Wfa ↔ `w_factor_ambiental`, Wfd ↔ `w_factor_densidad` (equivalencia de implementación, no de ficha).

---

## 3. Capa API / Postman — no ejecutada

| Intento | Resultado |
|---|---|
| Colección Postman G042 / TC-M04-034 | No existe bajo `Test_Modulo4` |
| `GET http://127.0.0.1:8000/docs` | Sin API local (timeout) |
| `POST /prediccion/motor-ia` contra PostgreSQL | **No ejecutado** (escribiría configuración compartida; sin autorización) |

No hay códigos HTTP de endpoint. El 422 citado más abajo es **atributo** de `BusinessRuleError`, no respuesta Postman.

Los pytest **no** se contabilizan como API.

---

## 4. Escenarios (unitario auxiliar / use case en memoria)

Comando pytest (EXIT=0, 3 passed; **no aprueba el caso**):

```
python -m pytest --noconftest -p no:cacheprovider -v -rs --tb=short
  tests/Test_Testing/Test_Modulo4/RF-65/TC-M04-G042/test_tc_m04_g042.py
```

Evidencia: `evidencias/ejecucion-2026-10-25/g042-unitario.{txt,html,xml}`

Escenarios extra (mismo use case + dobles; `evidencias/ejecucion-2026-10-25/escenarios-use-case.txt`):

| Escenario matriz | Esperado (si RF-65/matriz 0–1 y suma 1, API) | Observado (use case, no HTTP) |
|---|---|---|
| Wfs=0.4, Wfa=0.3, Wfd=0.3, suma 1.0 | Aceptar y persistir (API 201/200) | Memoria: persiste 0.400/0.300/0.300, `config_version` pasa a 2 en update. **Sin API** |
| Valor < 0 | Rechazo API; vigente intacta | **Acepta** −0.100+0.600+0.500 (suma 1) y persiste en el doble |
| Valor > 1 | Rechazo API; vigente intacta | **Acepta** 1.200+(−0.100)+(−0.100) (suma 1) |
| Suma ≠ 1.0 (0.5+0.3+0.3) | Rechazo | `PESOS_CONTAGIO_INVALIDOS`, `http_attr=422`; pesos y versión vigentes sin cambio **en memoria** |
| Wfs=1.1, Wfa=0, Wfd=0 (suma 1.1) | Rechazo | Igual: error suma; vigente intacta en memoria |
| Persistencia válida / PostgreSQL | BD real | **No ejecutada** |

Pytest interno usa ID `004` en el nombre de función; el subcaso de matriz sigue siendo **034**.

---

## 5. Evidencias (esta ejecución)

- `tests/Test_Testing/Test_Modulo4/RF-65/TC-M04-G042/Resultados/TC-M04-034/TC-M04-034_resultado.md` (este archivo)
- `.../TC-M04-034/evidencias/ejecucion-2026-10-25/g042-unitario.txt`
- `.../g042-unitario.html`
- `.../g042-unitario.xml`
- `.../escenarios-use-case.txt`

Histórico **no tocado:** `Resultados/TC-M04-004/` y `HALLAZGO_ALCANCE_TC-M04-004_pesos_Wfs.md`.

---

## 6. Errores, discrepancias, limitaciones

1. **Capa obligatoria API/Postman no cubierta** → el caso no puede ser APROBADO.
2. **Dueño RF-65 vs RF-68 no resuelto** (fichas ausentes; RF-68 documentado como mock de `definicion_fs`, no de Wfs).
3. **ID:** script y reportes viejos dicen TC-M04-004; matriz: **TC-M04-034**.
4. Si se aplicara el criterio de rango 0–1 de la matriz al código CU-02, el use case **acepta** pesos &lt; 0 y &gt; 1 cuando la suma es 1. Eso **no** se declara defecto de RF-65: el requisito de rango no está en ficha versionada aquí. Queda como hallazgo de implementación vs matriz, pendiente de dueño.
5. Dev sí rechaza suma ≠ 1 (`PESOS_CONTAGIO_INVALIDOS` / 422 lógico).

---

## 7. Estado final (solo APROBADO / RECHAZADO / BLOQUEADO)

| Ámbito | Estado | Motivo |
|---|---|---|
| **TC-M04-034** | **BLOQUEADO** | Sin ficha que fije dueño y criterios; sin ejecución API/Postman. Pytest en verde no cierra el caso. |
| **TC-M04-G042** | **BLOQUEADO** | El grupo solo contiene este subcaso de matriz; no hay evidencia de capa exigida. |

No APROBADO. No se marca RECHAZADO de RF-65: el incumplimiento de rango 0–1 no está confirmado como criterio de ese RF.

Para desbloquear: fichas RF-65 y/o RF-68; colección Postman o API aislada autorizada; decisión de rangos y de si `w_factor_*` son Wfs/Wfa/Wfd.
