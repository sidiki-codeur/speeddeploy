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

## Lancement rapide

### Sous Windows

Utilise le fichier `speeddeploy.bat` a la racine du projet :

```bat
speeddeploy.bat v2 plan gestiolocative
speeddeploy.bat v2 deploy gestiolocative
speeddeploy.bat helpers
```

### Sous Linux

Utilise le fichier `speeddeploy.sh` a la racine du projet :

```bash
./speeddeploy.sh v2 plan gestiolocative
./speeddeploy.sh v2 deploy gestiolocative
./speeddeploy.sh helpers
```

Si le fichier n est pas encore executable apres un clone :

```bash
chmod +x speeddeploy.sh
```

Si tu es sur un clone ancien ou si ton shell refuse `./speeddeploy.sh`, utilise :

```bash
bash speeddeploy.sh v2 plan gestiolocative
bash speeddeploy.sh helpers
```

## Mise en route sur un serveur

Cette procédure part d un serveur Linux vierge et va jusqu a la creation du premier fichier de configuration SpeedDeploy.

### 1. Creer le dossier de travail

```bash
sudo mkdir -p /opt/speeddeploy
sudo chown -R $USER:$USER /opt/speeddeploy
cd /opt/speeddeploy
```

### 2. Cloner SpeedDeploy

```bash
git clone https://github.com/TON_COMPTE/speeddeploy.git .
```

Si tu preferes garder le depot dans un sous-dossier :

```bash
git clone https://github.com/TON_COMPTE/speeddeploy.git
cd speeddeploy
```

### 3. Creer l environnement Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 4. Verifier que SpeedDeploy fonctionne

```bash
./speeddeploy.sh --help
```

Ou directement :

```bash
speeddeploy --help
```

### 5. Creer le dossier des projets

```bash
mkdir -p projects
```

### 6. Creer la configuration du projet

Creation interactive locale :

```bash
speeddeploy v2 config new gestiolocative
```

Creation pour un deploiement distant :

```bash
speeddeploy v2 config new gestiolocative --backend ssh --host 203.0.113.10 --connection-user root
```

Le fichier genere sera :

```bash
projects/gestiolocative.yml
```

### 7. Verifier la configuration

```bash
speeddeploy v2 doctor gestiolocative
speeddeploy v2 plan gestiolocative
```

### 8. Lancer un test a blanc

```bash
speeddeploy v2 --dry-run deploy gestiolocative
```

### 9. Lancer le premier deploiement

```bash
speeddeploy v2 deploy gestiolocative
```

## Procedure complete sur le serveur

Cette procedure s applique quand tu installes SpeedDeploy directement sur le serveur Linux cible.

### 1. Cloner SpeedDeploy

```bash
git clone https://github.com/sidiki-codeur/speeddeploy.git
cd speeddeploy
```

### 2. Preparer l environnement Python

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Sur Windows, cette etape sert surtout aux tests locaux ou a la preparation des configurations.
Pour un vrai deploiement serveur, execute SpeedDeploy sur Linux ou via SSH.

### 3. Creer la configuration du projet

```bash
speeddeploy v2 config new gestiolocative
```

Ou en mode ligne :

```bash
speeddeploy v2 config new gestiolocative --backend ssh --host 203.0.113.10 --connection-user root
```

Le fichier est cree dans `projects/gestiolocative.yml`.

### 4. Verifier le plan de deploiement

```bash
speeddeploy v2 plan gestiolocative
```

### 5. Lancer un test a blanc

```bash
speeddeploy v2 --dry-run deploy gestiolocative
```

### 6. Deployer le projet

```bash
speeddeploy v2 deploy gestiolocative
```

### 7. Passer a l exploitation quotidienne

Une fois le premier deploiement termine, le reste du guide presente toutes les commandes SpeedDeploy pour :

- redemarrer les services
- consulter les logs
- mettre a jour le code
- regenerer le SSL
- creer un superutilisateur Django

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
speeddeploy v2 update gestiolocative --keep-local-changes
speeddeploy v2 update gestiolocative --discard-local-changes
speeddeploy v2 update-code gestiolocative
speeddeploy v2 update-code gestiolocative --keep-local-changes
speeddeploy v2 update-code gestiolocative --discard-local-changes
speeddeploy v2 update-conf gestiolocative
speeddeploy v2 update-cert gestiolocative
```

## Guide de configuration

SpeedDeploy utilise deux blocs de configuration :

- `target` pour le contexte technique de deploiement
- `connection` pour le mode d execution

### Configuration en local

La configuration en local sert quand SpeedDeploy est execute directement sur le serveur cible.
Dans ce mode :

- `connection.backend` vaut `local`
- aucun `host` SSH n est requis
- le deploiement s execute sur la machine courante
- ce mode convient a Linux ou WSL

Exemple :

```yaml
connection:
  backend: local
```

Dans ce cas, il faut simplement renseigner le dossier cible, le repo Git, le domaine, le virtualenv et les parametres `target`.

### Configuration en ligne

La configuration en ligne sert quand SpeedDeploy est execute depuis ton poste de travail et pilote un serveur distant.
Dans ce mode :

- `connection.backend` vaut `ssh`
- `connection.host` est obligatoire
- `connection.port` est optionnel
- `connection.user` definit l utilisateur SSH
- `connection.identity_file` peut pointer vers ta cle privee SSH

Exemple :

```yaml
connection:
  backend: ssh
  host: 203.0.113.10
  port: 22
  user: root
  identity_file: C:/Users/Administrateur/.ssh/id_ed25519
```

Ce mode est utile quand :

- tu developpes sur Windows ou macOS
- tu veux deployer vers un VPS Linux distant
- tu ne veux pas installer SpeedDeploy directement sur le serveur

### Attention a la compatibilite Python / Django

Si ton projet utilise `Django 6.x`, le serveur doit avoir Python 3.12 ou plus recent.
Avec Python 3.11, l installation echouera.

Pour corriger cela :

- renseigne `python: python3.12` si Python 3.12 est installe
- ou baisse la version de Django dans le projet vers une version compatible avec Python 3.11

SpeedDeploy V2 detecte maintenant ce cas avant l installation des dependances.
Par defaut, `speeddeploy v2 update` conserve les changements locaux en les mettant de cote dans un stash temporaire puis en les restaurant apres le `pull`.

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

### Exemple complet en ligne

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

### Comment choisir le bon mode

- Choisis `local` si tu lances SpeedDeploy sur le serveur cible lui-meme
- Choisis `ssh` si tu lances SpeedDeploy depuis ton poste local vers un serveur distant
- Garde `target.web_server` a `apache` si tu veux une configuration classique Debian/Ubuntu
- Passe a `nginx` si tu veux un reverse proxy Nginx devant Gunicorn

## Toutes les commandes SpeedDeploy

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

### Mise a jour avec changements locaux

```bash
speeddeploy v2 update gestiolocative --keep-local-changes
speeddeploy v2 update gestiolocative --discard-local-changes
speeddeploy v2 update-code gestiolocative --keep-local-changes
speeddeploy v2 update-code gestiolocative --discard-local-changes
```

### Mises a jour ciblees

Utilise ces commandes quand tu ne veux pas relancer tout le cycle:

- `speeddeploy v2 update-code <project>` pour mettre a jour uniquement le code, les dependances Python et les migrations
- `speeddeploy v2 update-conf <project>` pour regenerer Gunicorn et la configuration Apache ou Nginx
- `speeddeploy v2 update-cert <project>` pour renouveler ou reemettre le certificat SSL

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
speeddeploy v2 deploy gestiolocative --keep-local-changes
speeddeploy v2 deploy gestiolocative --discard-local-changes
speeddeploy v2 update gestiolocative
speeddeploy v2 update gestiolocative --keep-local-changes
speeddeploy v2 update gestiolocative --discard-local-changes
speeddeploy v2 update-code gestiolocative
speeddeploy v2 update-code gestiolocative --keep-local-changes
speeddeploy v2 update-code gestiolocative --discard-local-changes
speeddeploy v2 update-conf gestiolocative
speeddeploy v2 update-cert gestiolocative
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
7. utiliser `speeddeploy v2 update-code <project>` pour le code, `speeddeploy v2 update-conf <project>` pour la conf, `speeddeploy v2 update-cert <project>` pour le SSL, ou `speeddeploy v2 update <project>` pour tout relancer

Par defaut, `speeddeploy v2 update` et `speeddeploy v2 update-code` conservent les changements locaux.
Si tu veux imposer un comportement explicite :

- `--keep-local-changes` conserve les changements locaux
- `--discard-local-changes` supprime les changements locaux avant la mise a jour

Ces deux options sont aussi disponibles sur `speeddeploy v2 deploy` et `speeddeploy v2 update-code` si le depot existe deja.

Pour un serveur local :

1. creer une config avec `connection.backend: local`
2. verifier le plan
3. executer le deploiement depuis le serveur cible

Pour un serveur distant :

1. creer une config avec `connection.backend: ssh`
2. verifier que la cle SSH fonctionne
3. tester avec `--dry-run`
4. lancer le vrai deploiement

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

### Propriete Git douteuse

Si Git affiche `proprietaire douteux detecte` ou `dubious ownership`, SpeedDeploy ajoute automatiquement le depot a `git safe.directory` avant le `pull`.
Cela arrive quand le dossier du projet est clone sous un compte systeme different de l utilisateur qui execute SpeedDeploy.
SpeedDeploy V2 lance maintenant les operations Git avec l utilisateur du projet, ce qui evite aussi les erreurs de type `FETCH_HEAD` ou droits insuffisants.
Si le depot contient des modifications locales, SpeedDeploy V2 les met automatiquement de cote dans un stash avant le `pull`.
Si tu veux supprimer les modifications locales au lieu de les conserver, utilise `--discard-local-changes`.

### Django 6.x avec Python 3.11

Si `pip` refuse `Django==6.0.x`, le serveur n a probablement pas une version de Python assez recente.
Dans ce cas :

- installe Python 3.12 sur le serveur
- ou passe le projet sur une version de Django compatible avec Python 3.11

### `collectstatic` demande `STATIC_ROOT`

Si `collectstatic` affiche une erreur du type `STATIC_ROOT setting to a filesystem path`, le projet Django ne declare pas encore `STATIC_ROOT`.
Ajoute dans les settings quelque chose comme :

```python
STATIC_ROOT = BASE_DIR / "staticfiles"
```

SpeedDeploy V2 verifie maintenant ce point avant de lancer `collectstatic`.

### Warnings `DEFAULT_AUTO_FIELD`

Les warnings sur `DEFAULT_AUTO_FIELD` ne bloquent pas le deploiement, mais ils indiquent que le projet peut encore utiliser l ancien type de cle primaire automatique.
Pour les supprimer, ajoute dans les settings :

```python
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

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
