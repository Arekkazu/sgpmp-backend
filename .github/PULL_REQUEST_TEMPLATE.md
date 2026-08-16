## Resumen

<!-- Qué cambia y por qué, en 2-3 líneas -->

## Trazabilidad (obligatorio)

- Requerimiento(s): RF-___ / RNF-___
- RFC asociado (si aplica, o "N/A" si es implementación directa de un RF ya aprobado en la RTM): RFC-___
- Módulo(s) afectado(s): identity_access / biological_assets / telemetry / prediction / supplies / configuration
- Bug(s) que corrige (si aplica): BUG-___

## Tipo de cambio

- [ ] feat — nueva funcionalidad
- [ ] fix — corrección de defecto
- [ ] refactor — sin cambio de comportamiento
- [ ] docs — solo documentación
- [ ] chore/test/perf/style

## Checklist antes de pedir revisión

- [ ] El commit / título del PR sigue el formato `tipo(módulo): descripción (RF-XXX)`
- [ ] El RF referenciado existe en la RTM y su estado permite este cambio
- [ ] Si el cambio toca identity_access, biological_assets o prediction (criticidad Alta), el RFC está aprobado por el comité
- [ ] Pruebas unitarias/integración agregadas o actualizadas (`pytest`)
- [ ] Documentación (manual técnico / manual de usuario) actualizada si el cambio afecta un flujo visible
- [ ] No quedan credenciales, endpoints internos o datos sensibles en el diff
- [ ] Pedí revisión ("Request review") a las personas correctas según el destino de este PR:
      → hacia `dev`: Líder de Desarrollo + Líder de IoT (si aplica)
      → hacia `main`: Líder de Pruebas + Líder de Proyecto
- [ ] (opcional) Etiqueté a Líder de Análisis para visibilidad — su revisión no bloquea el merge

## Impacto

- ¿Rompe compatibilidad con algo ya desplegado? Sí / No — explicar
- ¿Requiere migración de base de datos o cambio de configuración? Sí / No — explicar

## Evidencia de pruebas

<!-- Capturas, logs o link al pipeline en verde -->
