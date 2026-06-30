# Django + Apache

## Usage

Cette recette convient aux serveurs Debian/Ubuntu classiques.

```yaml
target:
  web_server: apache
  app_server: gunicorn
  ssl_provider: certbot
```

## Points pratiques

- Apache sert les fichiers `static` et `media`
- Gunicorn tourne via un service systemd
- Certbot se lance en mode non interactif

## Commandes utiles

```bash
speeddeploy v2 doctor gestiolocative
speeddeploy v2 plan gestiolocative
speeddeploy v2 deploy gestiolocative
speeddeploy v2 info gestiolocative
```

