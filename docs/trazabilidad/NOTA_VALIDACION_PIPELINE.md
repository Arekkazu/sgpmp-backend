# Validación del pipeline de versionamiento

Commit trivial (`chore`, no genera versión) solo para disparar
`release.yml` sobre el `dev` actual y confirmar que el tag
`v1.0.0-rc.1` se crea limpio ahora que el tag manual viejo ya se borró
del todo (git tag, no solo el GitHub Release).
