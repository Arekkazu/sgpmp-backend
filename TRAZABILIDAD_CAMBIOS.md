# Trazabilidad de cambios a main

Este archivo se genera y actualiza automáticamente en cada release (ver
`scripts/append_trazabilidad.js`, invocado desde `.releaserc.json`). No editar
a mano — cualquier cambio manual se sobrescribe en el siguiente release.

Cada fila corresponde a una versión publicada en `main` y resume, sin
intervención humana, qué requerimientos (RF/RNF), solicitudes de cambio (RFC)
y defectos (BUG) quedaron incluidos, con el detalle de los commits que los
implementaron.

Esta tabla es el insumo que el área de Análisis entrega al director para
sustentar la trazabilidad de lo que llega a producción — es el reflejo
automático de la RTM y del historial de Git, no un reporte aparte que alguien
arma después.

| Versión | Tag | Fecha | RF/RNF | RFC | Bugs | Commits incluidos |
|---|---|---|---|---|---|---|
