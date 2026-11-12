Corrida oficial lanzada en evidencias/run-20261111-213418 y creada la nota de archivo en LEEME_ARCHIVADA.md. Esperando a que finalice la ejecución para analizar los resultados, limpiar __pycache__, generar INFORME_REINTENTO1_G38.txt y ejecutar el escaneo de secretos.

Se aplicaron las correcciones al script y generador con D08_MODO = retirar, se archivó la corrida previa inválida en LEEME_ARCHIVADA.md apuntando a run-20261111-213418, y se ejecutó una sola vez ejecutar_tc_m05_g38.ps1 -Reintento 1 con resultado 12/12 aprobados (Veredicto: Aprobado, 14.77s pytest / 18.71s runner).

Sin promoción a resultados/, sin git add/commit y sin creación de INC.

1. Cambios aplicados, SHA-256 y verificación estática (Punto 5)
test_tc_m05_g38.py:
Partida -> Actual: EAC25DA0A6CD3B9F779ADC737A53429F24591DE00B7E31A21BF528E5C7781934 -> 8136678FCB496F0ACF13BB9E8D558FDC4320DB3F04BA8F17091AFA54B64B1214 (1030 líneas, 44825 bytes).
Cambios: reemplazo de _consultar_sql / /test-control/query por _leer_estado_auditoria_api en test_t00_linea_base y test_t99_inocuidad; eliminación de las 4 lecturas SQL en test_d07_sin_permiso sustituida por observación sin aserción vía GET /suministros/auditoria y GET /auditoria/ (auditoria_routers.py); retiro de test_d08_permisos_contador_y_revisor_fiscal con nota en el docstring del módulo; actualización de cabecera.
generar_artefactos_run_g38.py:
Partida -> Actual: F11323B6B7D8242126E05F287C32D6ABBC2D16BE67DDD2F8816FF9758FEF6951 -> 6228973AAC06A3A75000F708C79988112148B0B815C488561D9059DC48145E29 (331 líneas, 15044 bytes).
Cambios: retiro de test_d08_permisos_contador_y_revisor_fiscal en TEST_METADATA y cabecera.
ejecutar_tc_m05_g38.ps1: sin modificaciones (46FDED59421630714CCC3319B55B6856D347AC6C1D717E31F7F9586FAF3BC23F, 243 líneas, HasBOM=False, NonAscii=0, Parser::ParseFile 0 errores).
Verificación estática y búsqueda (Punto 5): py_compile OK en ambos .py; pytest --collect-only = 12 tests collected in 1.05s; búsqueda de test-control/query, _consultar_sql, SELECT, modulo5., modulo1.:
test_tc_m05_g38.py: únicamente L369 (docstring explicativo pedido en test_t00_linea_base), 0 llamadas ejecutables.
ejecutar_tc_m05_g38.ps1: 0 coincidencias.
generar_artefactos_run_g38.py: únicamente etiqueta "paso" en L28.
2. Resultados oficiales (run-20261111-213418) y observaciones
Resumen: 12 passed (0 fallos) en resultado_TC-M05-G38_reintento1.json: T00, C01, C02, D01, D02, D03, D04, D05, D06, D07, T98, T99 todos OK. (Alcance retirado por D08_MODO = retirar: D08 Contador y Revisor Fiscal pendiente para ronda posterior cuando .env.test cuente con credenciales).
Observaciones registradas:
D06 (mensaje "sin eventos" y auditoría de consulta): GET /suministros/auditoria sobre id_activo_biologico=1855 (X-Request-Id=ceec6888-f50d-47af-900c-51ddf11304b8) devolvió HTTP 200 con claves ['total', 'pagina', 'registros_por_pagina', 'items'], total=0, items=[] (sin campo "mensaje" ni texto "sin eventos"). El total global en bitácora M05 se mantuvo en 69274 (64166654-...) -> 69274 (25f4e9ca-...), delta = 0.
D07 (403 y totales observados M05 / M01): Productor y Veterinario obtuvieron 6 HTTP 403 ACCESO_DENEGADO sin clave items (1ce43630-..., 75d844f3-..., 3f147853-..., 6d4d6169-..., 59ccb441-..., d435c801-...). Observación por API:
M05 (GET /suministros/auditoria): 69274 (HTTP 200, 64b62d31-...) -> 69274 (HTTP 200, 9381e6b1-...), delta = 0.
M01 (GET /auditoria/?pagina=1&tamano=1): 73802 (HTTP 206, d94bdfad-...) -> 73803 (HTTP 206, 8a1edbfe-...), delta = +1 (correspondiente a la propia auto-auditoría TIPO_CONSULTA_AUDITORIA que registra ConsultarAuditoriaUseCase.execute al consultar GET /auditoria/, no a los 6 rechazos 403).
Inocuidad verificada (T00 -> T98 -> T99):
T00 (tc-m05-g38-inobase-b2fe4f9c): total=69267, ultimo_id=75494 (e8d6cfd8-...), cierre DELETE -> 200 (13c348e5-...).
T98 (tc-m05-g38-adm-d99f905f): DELETE -> HTTP 200 {"status": "Rollback exitoso"} (a0860a8d-...).
T99 (tc-m05-g38-inofin-f36bb14e): GET /suministros/auditoria -> 200 total=69267, ultimo_id=75494 (7726585e-...); GET /activos-biologicos/1854 -> 404 (991168e5-...); GET /suministros/costeo-directo/acumulado/activo/1854 -> 404 (54c00bce-...); GET /activos-biologicos/1855 -> 404 (c0009afc-...); cierre DELETE -> 200 (8d2f7029-...).
3. Entregable, resultados/, limpieza y escaneo de secretos
Informe final en staging: INFORME_REINTENTO1_G38.txt (35066 bytes, SHA-256=D5F493F64ED55005223FC555C719B8E73F1DE9CDC22390A8A3EE614707C54723) junto con los 7 artefactos generados en run-20261111-213418.
resultados/ intacto: .gitkeep (E3B0C442...), resultado_TC-M05-G38.html (DC37B665...), resultado_TC-M05-G38.json (3AA003B7...).
__pycache__/.pyc: eliminados (PYC_REMAINING: []).
Escaneo final de secretos (valores de .env.test en memoria: contraseñas ADMIN, PRODUCER, VET, FIELD_ENGINEER, DB, TEST_SANDBOX_SECRET, BROKER_SERVICE_TOKEN, últimos 20 caracteres de cada uno y prefijo JWT) en los 8 archivos de run-20261111-213418 y LEEME_ARCHIVADA.md: no encontrado para todos los patrones en todos los archivos (TOTAL_HALLAZGOS: 0).