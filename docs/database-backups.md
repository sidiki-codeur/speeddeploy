# Sauvegardes de base

## Configuration

```yaml
database:
  engine: postgres
  name: gestiolocative
  user: django
  password: secret
  host: localhost
  port: 5432
  keep: 5
```

## Notes

- les sauvegardes sont faites avant les migrations
- le mot de passe passe par un fichier temporaire securise
- les fichiers sont conserves dans `backups/`

## Commande utile

```bash
speeddeploy v2 backup gestiolocative
```

