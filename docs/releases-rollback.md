# Releases et rollback

## Activation

```yaml
releases:
  enabled: true
  keep: 5
```

## Ce que cela change

- chaque deploiement cree une nouvelle release
- `current` pointe vers la release active
- les fichiers partages vivent sous `shared/`
- les anciens deploiements peuvent etre relances sans refaire le clone

## Etat persistant

SpeedDeploy ecrit un fichier `shared/.speeddeploy/state.json` avec:

- la branche
- la strategie
- la release active
- la release precedente
- le statut du dernier deploiement

## Commandes utiles

```bash
speeddeploy v2 releases gestiolocative
speeddeploy v2 rollback gestiolocative
speeddeploy v2 rollback gestiolocative --to 20260628-150000
speeddeploy v2 info gestiolocative
```

