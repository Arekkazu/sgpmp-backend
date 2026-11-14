-- Rollback de la siembra rf62_* en modulo4.parametros_mlops
-- Ejecutar SOLO si hay que deshacer los cambios de G165.
DELETE FROM modulo4.parametros_mlops
WHERE nombre_parametro IN ('rf62_k','rf62_m','rf62_n','rf62_p','rf62_umbral_drift');