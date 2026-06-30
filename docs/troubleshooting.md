# Depannage

## Outils de diagnostic

```bash
speeddeploy v2 doctor gestiolocative
speeddeploy v2 audit gestiolocative
speeddeploy v2 diagnose gestiolocative
speeddeploy v2 info gestiolocative
speeddeploy v2 logs gestiolocative
speeddeploy v2 status gestiolocative
```

## Problemes courants

- `STATIC_ROOT` manquant: ajouter la variable dans les settings Django
- certificat SSL non emis: verifier le DNS et l acces a `certbot`
- service systemd en echec: consulter `logs` puis `status`
- rollback bloque: verifier que la release cible existe dans `releases/`
