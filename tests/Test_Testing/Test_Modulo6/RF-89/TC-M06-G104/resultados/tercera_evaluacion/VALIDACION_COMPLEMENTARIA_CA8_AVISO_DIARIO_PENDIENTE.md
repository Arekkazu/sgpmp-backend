# Validación complementaria pendiente — CA-8 / FA-5 (aviso diario)

**RF:** RF-89 v1.2 · FA-5 · CA-8 (RFC-024 C24.5)  
**Relación con TC-M06-29:** **fuera del alcance de cierre** del subcaso; obligación normativa vigente no demostrada  
**Escenario de referencia:** precio **492**, especie **544**, vencimiento **2026-11-10**  
**Estado:** **PENDIENTE DE EVIDENCIA**

## Qué exige

El Contador recibe el aviso diario de que el precio **venció sin reemplazo**.

## Qué se sabe (evidencia existente)

- `GET /notificaciones` (Contador): sin aviso identificable ligado al 492 (`tercera_evaluacion/evidencia_verificacion_lectura_tc_m06_29.json` y campañas posteriores de solo lectura).  
- No hay confirmación de ejecución del job diario el 2026-11-11 UTC ni de fallo de persistencia.

Detalle técnico y borrador de solicitud a Dev/Ops: carpeta local `_archivo_trabajo_local/informes_intermedios/` (no publicada).

## Qué no se afirma

- Que el aviso se generó.  
- Que el job corrió.  
- Que CA-8 está APROBADO.

## Trazabilidad sugerida al retomar

Reabrir verificación CA-8 con evidencia Dev/Ops o vincular a la línea de avisos (p. ej. TC-M06-G109) sin reabrir criterios v1.0 de TC-M06-29.
