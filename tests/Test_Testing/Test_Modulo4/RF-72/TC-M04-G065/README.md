# TC-M04-G065 — APROBADO (RUN oficial RUN-G065-V1-20261029-023258; revisión QA de TC-M04-224)

[Informe oficial](Resultados/RUN-G065-V1-20261029-023258/TC-M04-G065_resultado.md): los cuatro casos APROBADOS por decisión del responsable QA de 2026-10-29. TC-M04-224 tiene la observación OBS-M04-G065-224: HTTP 400 en lugar del 422 recomendado; el rechazo completo y la ausencia de persistencia se comprobaron. `resultado.json` conserva el veredicto RECHAZADO y la incidencia históricos del ejecutor como evidencia nativa intacta.

Preparación local de las cuatro comprobaciones API de la fila `TC-M04-G065` en `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv` (Windows-1252, `;`). Casos originales: TC-M04-198, 199, 223 y 224. No hay comprobación UI. En esta fase no se ejecuta TEST ni se crea RUN.

## Oráculos preservados

| Caso | Registro y comprobación |
|---|---|
| 198 | Dos `CORRECTO`, uno con texto clínico de prueba (tildes, ñ, signos y salto de línea) y otro sin el campo. Ambos HTTP 201; historial conserva exactamente el texto y muestra nulo al omitir. |
| 199 | Cuatro `INCORRECTO` con diagnóstico activo, uno por `OBSERVACION_DIRECTA`, `LABORATORIO`, `HISTORIAL_CLINICO`, `OTRO`. Cuatro HTTP 201; fuente igual y marca falsa en respuesta y snapshot de auditoría. |
| 223 | `INCORRECTO` y `PARCIAL` sin fuente, y `PARCIAL` con fuente como contraste. Tres HTTP 201; marca verdadera en los omitidos y falsa en el contraste, corroborada por auditoría. Si la auditoría no expone la marca, `NO_CONCLUYENTE`. |
| 224 | `INCORRECTO` con `RESONANCIA_MAGNETICA`: rechazo con `fuente_diagnostico` y los cuatro valores admitidos; ausencia de registro en historial y auditoría. La matriz G065 escribió HTTP 422; RF-72 no lo fija para esta fuente. HTTP 400 con rechazo completo se aprueba con observación. |

RF-72: prioridad por fuente en líneas 4033–4041; trazabilidad y marca en 4118–4120; entradas opcionales en 4164 y 4167; fases 4–6 en 4186–4215; salida en 4314–4317; CA-4/CA-5 en 4365–4367 de `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`. La matriz decide que `fuente_diagnostico` es dominio cerrado y escribió HTTP 422 para el cuarto caso; por decisión QA, el código queda recomendado, pues RF-72 no lo fija para esta fuente. La comparación de persistencia usa lecturas públicas, sin SQL.

## Contrato consultado en `origin/test` (`daefc3a5`)

- `src/prediction/infrastructure/dto/registrar_retroalimentacion_dto.py:11-17`: ambos campos opcionales.
- `src/prediction/domain/entities/retroalimentacion_clinica.py:12,61-71,86-94`: catálogo, validación, cálculo de marca y snapshot. `src/prediction/infrastructure/schema/retroalimentacion_clinica_schema.py:18-19,36-37` expone fuente y marca.
- `src/prediction/infrastructure/repositories/historial_diagnostico_repository.py:167-180`: historial expone observaciones y estado, sin fuente ni marca.
- `src/prediction/application/use_cases/retroalimentacion/registrar_retroalimentacion_use_case.py:132-169`: crea la entidad antes de guardar (145) y audita el snapshot tras guardar (160–169). El 422/400 de validación ocurre antes de ambos. `src/prediction/infrastructure/routers/auditoria_m04_router.py:59-109` publica la lectura; `src/prediction/infrastructure/schema/evento_auditoria_m04_schema.py:15-24` expone `payload_evento`.
- La entidad lanza `ValidationError` en `retroalimentacion_clinica.py:62-67`; `src/shared/errors.py:69-77` define `status_code = 400`, y `src/shared/error_handlers.py:76-104` lo propaga. El RUN autorizado confirmó HTTP 400 y rechazo completo sin persistencia. El ensayo loopback acepta 400 con observación y 422 cuando ambos cumplen el rechazo; la hipótesis técnica no establece causa raíz.

## Semilla y presupuesto

El runner descubre activos `INDIVIDUAL`, historial de 88 días con cursor, versiones de modelo y patologías activas. Filtra resultados de `MODELO_ESPECIES_MEDIANAS` o `MODELO_ESPECIES_GRANDES` sin retroalimentación previa del Veterinario. Usa diez resultados distintos, en orden 224 (1), 223 (3), 199 (4), 198 (2), para preservar los casos más valiosos si escasean datos. La semilla permanente descrita por QA contiene 14 resultados del activo 885, modelo individual versión 43; el ejecutor no fija esos IDs ni crea referencias. Un 409 por duplicado o 422 por ventana puede reemplazar una vez el resultado, con diagnóstico saneado de datos. Datos insuficientes dejan `NO_CONCLUYENTE` solo los casos afectados.

Constante única `PRESUPUESTO.solicitudes_totales = 244`: 1 login, 4 páginas de activos, 128 páginas de historial de descubrimiento, 8 versiones, 1 catálogo, hasta 20 POST (10 iniciales + 10 reemplazos), 30 páginas de verificación, 10 lecturas de auditoría, 1 login de Administrador si hace falta, 10 relecturas de auditoría, 1 DELETE y 30 páginas de historial poscierre. Son máximos; la ejecución normal hace 10 POST, 9 con 201 y uno rechazado con 400 o 422. Timeout de login: 120 s; resto: 30 s; duración máxima: 900 s. Las solicitudes van en serie. El DELETE se intenta siempre tras el login, incluso si hay corte; el rollback se afirma solo con ausencia en lecturas públicas poscierre.

## Ejecución y efectos para la SOL

`node g065.mjs --capacidades`, `node g065.mjs --comprobar`, `node pruebas/g065_env.test.mjs`, `node pruebas/g065_ensayo.mjs` son locales. El ensayo usa servidor loopback y directorios temporales; sus resultados no son evidencias TEST. El lanzador externo aporta contexto, autorización humana particular y `.env.qa`; el ejecutor comprueba la API canónica, la colección y Newman antes de cualquier petición. Nunca ejecutar autónomamente contra TEST. No registrar valores de credenciales. Los POST evaluados, incluidos reemplazos, se ejecutan con la colección Newman y sus aserciones de código HTTP y eco de RUN; el ejecutor toma de Newman el HTTP, cuerpo y duración para los veredictos. Para TC-M04-224 admite HTTP 400 o 422 si el rechazo completo y la ausencia de persistencia se verifican. Login, descubrimiento, lecturas de comprobación y cierre usan fetch. Cada POST produce JSON y HTML saneados dentro de `newman/` del RUN, referenciados en `resultado.json` y el informe. No hay reintentos de Newman; el único reemplazo posible responde a un dato no apto (409 por duplicado o 422 por ventana). El presupuesto sigue siendo 244 solicitudes.

Para la SOL, declarar login; lecturas de descubrimiento que crean `HISTORIAL_CONSULTADO` dentro del sandbox; nueve retroalimentaciones válidas y sus eventos `RETROALIMENTACION_REGISTRADA`, revertidos por DELETE; solicitud inválida sin persistencia esperada; lecturas poscierre que pueden crear `HISTORIAL_CONSULTADO` fuera del sandbox. No hay correos, archivos ni cambios de semilla. La auditoría puede usar Administrador si el Veterinario carece de lectura. Un 403 de clave o tres 5xx consecutivos bloquean técnicamente; un POST sin respuesta exige conciliación. Un 5xx del POST rechaza su caso. Las incidencias de producto se agrupan por causa observable y se orientan inicialmente a Desarrollo; problemas de automatización se consignan aparte. No se infiere causa raíz.

La salida oficial futura va únicamente dentro de `Resultados/RUN-G065-V1-<fecha>-<hora>/` o, por decisión explícita de reevaluación, `EvaluacionV2/Resultados/RUN-G065-V2-<fecha>-<hora>/`, con `preflight.json`, `resultado.json`, `newman/*.json`, `newman/*.html` e informe `TC-M04-G065_resultado.md` o `TC-M04-G065_reevaluacion_V2.md`. No se crea ese directorio en la preparación.
