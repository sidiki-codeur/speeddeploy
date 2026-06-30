# SSL avec Certbot

## Configuration

```yaml
ssl:
  enabled: true
  email: admin@example.com
  redirect: true
  staging: false
  agree_tos: true
```

## Comportement

- la commande Certbot est lancee en mode non interactif
- `--agree-tos` est ajoute automatiquement si active
- `--redirect` force la redirection HTTP vers HTTPS
- `--staging` peut etre active pour tester sans consommer des quotas lets encrypt

## Commandes utiles

```bash
speeddeploy v2 ssl gestiolocative
speeddeploy v2 update-cert gestiolocative
```

