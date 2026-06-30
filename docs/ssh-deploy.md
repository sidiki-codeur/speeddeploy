# Deploiement SSH

## Quand l utiliser

Utilise ce mode quand SpeedDeploy tourne sur ton poste et pilote un VPS distant.

```yaml
connection:
  backend: ssh
  host: 203.0.113.10
  port: 22
  user: root
  identity_file: C:/Users/Administrateur/.ssh/id_ed25519
```

## Bonnes pratiques

- verifier la cle SSH avant de lancer un vrai deploiement
- tester d abord avec `--dry-run`
- utiliser `speeddeploy v2 audit <project>` avant le premier `deploy`

## Commandes utiles

```bash
speeddeploy v2 audit gestiolocative
speeddeploy v2 plan gestiolocative
speeddeploy v2 --dry-run deploy gestiolocative
speeddeploy v2 deploy gestiolocative
```

