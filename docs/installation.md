# Installation

## Pre requis

- Python 3.10 ou plus recent
- Git
- `pip`
- Un serveur Linux pour les deploiements locaux
- SSH valide pour les deploiements distants

## Installation locale

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Verification rapide

```bash
speeddeploy --help
speeddeploy v2 --help
speeddeploy v2 helpers
```

## Options systeme utiles

```yaml
system_packages:
  install: true

system_user:
  create: false
  shell: /usr/sbin/nologin
  home: /srv/gestiolocative
```

- `system_packages.install: false` laisse le serveur gerer ses paquets manuellement.
- `system_user.create: true` demande a SpeedDeploy de creer l utilisateur avant le deploiement.

