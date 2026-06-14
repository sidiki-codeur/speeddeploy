# SpeedDeploy

SpeedDeploy est un outil CLI pour deployer des applications Django sur des serveurs Linux.
Le projet dispose maintenant de deux niveaux :

- V1, le flux local historique
- V2, le moteur moderne avec prise en charge de `local` et `ssh`

V2 est le chemin recommande pour les nouveaux projets.

## Ce que SpeedDeploy automatise

SpeedDeploy prend en charge les etapes repetitives du deploiement Django :

- preparation du dossier cible
- clonage ou mise a jour du depot Git
- creation et mise a jour du virtualenv Python
- execution des migrations Django et de `collectstatic`
- creation et activation du service Gunicorn
- generation de la configuration Apache ou Nginx
- provisionnement SSL avec Certbot
- redemarrage et inspection des services

## Pre-requis

### Machine locale

- Python 3.10 ou plus recent
- `pip`
- Git
- Sous Linux pour un deploiement local direct
- Sous Windows pour generer les configs, preparer les plans, ou deployer via SSH

### Serveur cible

- Un serveur Linux avec `systemd`
- Un depot Git accessible depuis le serveur
- Les droits `sudo` pour installer les paquets et gerer les services
- Pour le SSL, un nom de domaine public pointe vers le serveur

## Installation

Creation et activation de l environnement virtuel :

```bash
python -m venv venv
```

Windows :

```bash
venv\Scripts\activate
```

Linux ou macOS :

```bash
source venv/bin/activate
```

Installation du projet :

```bash
pip install -r requirements.txt
pip install -e .
```

## Arborescence

```text
speeddeploy/
|-- speeddeploy/
|   |-- cli.py
|   |-- config.py
|   |-- deployer.py
|   |-- django.py
|   |-- gunicorn.py
|   |-- apache.py
|   |-- ssl.py
|   |-- runner.py
|   |-- system.py
|   `-- v2/
|       |-- cli.py
|       |-- engine.py
|       |-- executor.py
|       `-- models.py
|
|-- speeddeploy/templates/
|   |-- apache.conf.j2
|   |-- gunicorn.service.j2
|   `-- nginx.conf.j2
|
|-- projects/
|   `-- gestiolocative.yml
|-- README.md
|-- requirements.txt
|-- pyproject.toml
`-- .gitignore
```

## Principe de fonctionnement

SpeedDeploy lit un fichier YAML dans `projects/` par defaut.
Ce fichier decrit le projet Django, la cible serveur et le mode d execution.

Flux general :

1. creer une configuration projet
2. inspecter le plan avec `doctor` ou `plan`
3. lancer un `dry-run`
4. lancer le vrai deploiement
5. activer le SSL si necessaire
6. utiliser `update`, `restart`, `status` et `logs` pour l exploitation quotidienne

## V1 et V2

### V1

V1 conserve le flux simple d origine :

- execution locale
- Apache + Gunicorn
- hypothese Debian/Ubuntu
- demarrage rapide pour des VPS simples

### V2

V2 ajoute un vrai modele de deploiement :

- backend `local` pour Linux et WSL
- backend `ssh` pour l execution distante
- Apache ou Nginx
- plusieurs gestionnaires de paquets
- validation plus stricte des configurations
- moteur d execution plus propre

## Demarrage rapide

### 1. Creer une configuration

Creation interactive de config V2 :

```bash
speeddeploy v2 config new
```

Creation de config V1 :

```bash
speeddeploy config new
```

### 2. Visualiser le plan

```bash
speeddeploy v2 plan gestiolocative
```

### 3. Lancer un test a blanc

```bash
speeddeploy v2 --dry-run deploy gestiolocative
```

### 4. Deployer

```bash
speeddeploy v2 deploy gestiolocative
```

### 5. Activer le SSL

```bash
speeddeploy v2 ssl gestiolocative
```

### 6. Mettre a jour plus tard

```bash
speeddeploy v2 update gestiolocative
```

## Guide de configuration

SpeedDeploy utilise deux blocs de configuration :

- `target` pour le contexte technique de deploiement
- `connection` pour le mode d execution

### Exemple V2

```yaml
project: gestiolocative
domain: locative.emanager.cloud
repo: https://github.com/TON_COMPTE/gestiolocative.git
path: /srv/gestiolocative
user: django
group: www-data
wsgi: config.wsgi:application
python: python3
venv: /srv/gestiolocative/venv
static_dir: /srv/gestiolocative/staticfiles
media_dir: /srv/gestiolocative/media
workers: 3
target:
  os: linux
  init_system: systemd
  web_server: apache
  app_server: gunicorn
  ssl_provider: certbot
  package_manager: apt
connection:
  backend: local
```

### Exemple SSH

```yaml
project: gestiolocative
domain: locative.emanager.cloud
repo: https://github.com/TON_COMPTE/gestiolocative.git
path: /srv/gestiolocative
user: django
group: www-data
wsgi: config.wsgi:application
python: python3
venv: /srv/gestiolocative/venv
static_dir: /srv/gestiolocative/staticfiles
media_dir: /srv/gestiolocative/media
workers: 3
target:
  os: linux
  init_system: systemd
  web_server: nginx
  app_server: gunicorn
  ssl_provider: certbot
  package_manager: apt
connection:
  backend: ssh
  host: 203.0.113.10
  port: 22
  user: root
  identity_file: C:/Users/Administrateur/.ssh/id_ed25519
```

## Champs de configuration

### Champs obligatoires

- `project`
- `domain`
- `repo`
- `path`
- `user`
- `group`
- `wsgi`
- `python`
- `venv`
- `static_dir`
- `media_dir`
- `workers`

### Bloc `target`

- `os` : systeme cible, informatif pour le moment
- `init_system` : actuellement `systemd`
- `web_server` : `apache` ou `nginx`
- `app_server` : actuellement `gunicorn`
- `ssl_provider` : `certbot`, `none` ou `disabled`
- `package_manager` : `apt`, `dnf`, `yum`, `apk` ou `pacman`

### Bloc `connection`

- `backend` : `local` ou `ssh`
- `host` : obligatoire pour SSH
- `port` : port SSH, par defaut `22`
- `user` : utilisateur SSH, optionnel
- `identity_file` : cle privee SSH, optionnelle

## Reference des commandes

### CLI principale

```bash
speeddeploy --help
speeddeploy --dry-run deploy gestiolocative
speeddeploy --projects-dir projects v2 plan gestiolocative
```

### Aide

```bash
speeddeploy helpers
speeddeploy helpers gestiolocative
```

### Creation de configuration

```bash
speeddeploy config new
speeddeploy config new gestiolocative --domain locative.emanager.cloud --repo https://github.com/TON_COMPTE/gestiolocative.git

speeddeploy v2 config new
speeddeploy v2 config new gestiolocative --backend ssh --host 203.0.113.10 --connection-user root
```

### Diagnostic

```bash
speeddeploy doctor gestiolocative
speeddeploy plan gestiolocative
speeddeploy helpers
speeddeploy v2 doctor gestiolocative
speeddeploy v2 plan gestiolocative
speeddeploy v2 helpers
```

### Cycle de deploiement

```bash
speeddeploy init gestiolocative
speeddeploy clone gestiolocative
speeddeploy venv gestiolocative
speeddeploy django gestiolocative
speeddeploy gunicorn gestiolocative
speeddeploy apache gestiolocative
speeddeploy deploy gestiolocative
speeddeploy update gestiolocative
speeddeploy restart gestiolocative
speeddeploy status gestiolocative
speeddeploy logs gestiolocative
speeddeploy ssl gestiolocative
speeddeploy superuser gestiolocative
```

### Cycle V2

```bash
speeddeploy v2 deploy gestiolocative
speeddeploy v2 update gestiolocative
speeddeploy v2 restart gestiolocative
speeddeploy v2 status gestiolocative
speeddeploy v2 logs gestiolocative
speeddeploy v2 ssl gestiolocative
speeddeploy v2 superuser gestiolocative
```

## Flux recommande

Pour un nouveau projet :

1. creer la config V2
2. lancer `speeddeploy v2 doctor <project>`
3. lancer `speeddeploy v2 plan <project>`
4. lancer `speeddeploy v2 --dry-run deploy <project>`
5. lancer `speeddeploy v2 deploy <project>`
6. verifier le site et le SSL
7. utiliser `speeddeploy v2 update <project>` pour les mises a jour

## Backends de deploiement

### Backend local

Utiliser ce mode quand la machine qui lance SpeedDeploy est aussi le serveur cible.
Cela fonctionne sur Linux ou WSL.

### Backend SSH

Utiliser ce mode quand SpeedDeploy tourne sur ton poste et deploie sur un serveur Linux distant.
Il faut :

- un acces SSH
- un hote joignable
- les droits sudo appropries
- un acces Git depuis le serveur distant

## Apache ou Nginx

### Apache

Apache convient bien aux stacks Debian/Ubuntu classiques.
SpeedDeploy genere un vhost et active automatiquement le site.

### Nginx

Nginx convient si tu veux un reverse proxy Nginx devant Gunicorn.
SpeedDeploy genere la configuration du site et recharge Nginx.

## Exploitation quotidienne

### Verifier le statut

```bash
speeddeploy v2 status gestiolocative
```

### Lire les logs

```bash
speeddeploy v2 logs gestiolocative
```

### Redemarrer les services

```bash
speeddeploy v2 restart gestiolocative
```

### Creer un superutilisateur Django

```bash
speeddeploy v2 superuser gestiolocative
```

## Depannage

### "Configuration file not found"

Verifie que le fichier existe dans `projects/` et que tu passes le nom du projet sans extension.

### "Unsupported backend"

Verifie que `connection.backend` vaut `local` ou `ssh`.

### "SSH backend requires `connection.host`"

Ajoute une valeur valide pour `host` dans le bloc `connection`.

### "Unsupported package manager"

Utilise l une de ces valeurs :

- `apt`
- `dnf`
- `yum`
- `apk`
- `pacman`

### "Local deployment only works on Linux/WSL"

Lance la commande sur le serveur Linux cible, ou utilise le backend SSH.

### Erreurs systemd ou sudo

Verifie que l utilisateur cible peut utiliser `sudo` et que `systemd` est bien present sur le serveur.

## Notes de securite

- Ne commit jamais de secrets, de cles privees ou de mots de passe de production.
- Garde les cles SSH hors du depot.
- Verifie les fichiers generes avant d activer le SSL en production.
- Utilise `--dry-run` avant le premier vrai deploiement.

## Notes de developpement

Le code est organise ainsi :

- `speeddeploy/` pour le flux V1
- `speeddeploy/v2/` pour le moteur moderne avec backends

Cette separation permet de faire evoluer l outil sans casser le chemin le plus simple.

## Avant publication GitHub

Avant de publier le projet :

1. verifier tous les fichiers dans `projects/`
2. supprimer toute vraie credential
3. relire les exemples du README
4. lancer les verifications syntaxiques localement
5. tester `speeddeploy v2 config new`
6. tester `speeddeploy v2 --dry-run deploy <project>`

