# Django + Nginx

## Usage

```yaml
target:
  web_server: nginx
  app_server: gunicorn
  ssl_provider: certbot
```

## Points pratiques

- Nginx agit comme reverse proxy vers le socket Unix Gunicorn
- Les timeouts sont augmentes pour les uploads et les requetes longues
- `client_max_body_size` est configure pour les fichiers volumineux

## Commandes utiles

```bash
speeddeploy v2 plan gestiolocative
speeddeploy v2 deploy gestiolocative
speeddeploy v2 update-conf gestiolocative
speeddeploy v2 info gestiolocative
```

