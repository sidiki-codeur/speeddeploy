# SpeedDeploy

SpeedDeploy est un outil en ligne de commande pour deployer des applications Django sur des serveurs Linux.
Le projet dispose maintenant de deux niveaux :

- V1, le flux local historique
- V2, le moteur moderne avec prise en charge de `local` et `ssh`

V2 est le chemin principal et recommande pour les nouveaux projets.

## Documentation detaillee

Les pages suivantes detailleent les cas d usage les plus utiles:

- [Installation](docs/installation.md)
- [Django + Apache](docs/django-apache.md)
- [Django + Nginx](docs/django-nginx.md)
- [Deploiement SSH](docs/ssh-deploy.md)
- [Releases et rollback](docs/releases-rollback.md)
- [SSL avec Certbot](docs/ssl-certbot.md)
- [Sauvegardes de base](docs/database-backups.md)
- [Depannage](docs/troubleshooting.md)

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

## Prerequis

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
speeddeploy v2 config new gestiolocative --branch main
```

Creation pour un deploiement distant :

```bash
speeddeploy v2 config new gestiolocative --branch main --backend ssh --host 203.0.113.10 --connection-user root
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
speeddeploy v2 config new gestiolocative --branch main
```

Ou en mode ligne :

```bash
speeddeploy v2 config new gestiolocative --branch main --backend ssh --host 203.0.113.10 --connection-user root
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
speeddeploy v2 config new --branch main
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
branch: main
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
branch: main
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
- `branch`
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

### Branche Git

- `branch` : branche Git a suivre pour le clone et les mises a jour
- par defaut, SpeedDeploy utilise `main`
- renseigne une autre branche si ton projet deploie depuis `develop`, `release`, ou une branche de production specifique

### Comment choisir le bon mode

- Choisis `local` si tu lances SpeedDeploy sur le serveur cible lui-meme
- Choisis `ssh` si tu lances SpeedDeploy depuis ton poste local vers un serveur distant
- Garde `target.web_server` a `apache` si tu veux une configuration classique Debian/Ubuntu
- Passe a `nginx` si tu veux un reverse proxy Nginx devant Gunicorn

## Deploiement atomique, healthcheck, backups, systeme et secrets

La V2 propose plusieurs blocs de configuration optionnels qui rendent les deploiements plus surs. Ils sont desactives ou neutres par defaut : les projets existants continuent de fonctionner sans modification.

### Bloc `releases` — deploiement atomique et rollback

Quand `releases.enabled: true`, chaque deploiement construit un nouveau dossier `releases/<horodatage>/` (avec son propre virtualenv), puis bascule le lien symbolique `current` de maniere atomique. Le site ne pointe jamais vers une release a moitie construite, et un retour arriere est instantane.

```yaml
releases:
  enabled: true   # active la strategie par releases (defaut: false = deploiement en place)
  keep: 5         # nombre de releases a conserver (les plus anciennes sont purgees)
```

Arborescence produite sous `path` :

```
releases/<horodatage>/   un checkout Git par deploiement, avec son venv
current -> releases/...   lien symbolique vers la release active
shared/
  staticfiles/  media/    fichiers partages entre releases (lies dans chaque release)
  backups/                 sauvegardes de base de donnees
  .env                     secrets (mode 0640)
  .speeddeploy/            etat de deploiement
```

Commandes associees :

```bash
speeddeploy v2 releases <projet>    # liste les releases et indique l active
speeddeploy v2 rollback <projet>    # reactive la release precedente
```

> En mode releases, `deploy`, `update` et `update-code` creent tous une nouvelle release ; le code provient toujours d un clone neuf de la branche, donc les options `--keep/--discard-local-changes` ne s appliquent pas.

### Bloc `system_packages` - controle de l installation des paquets

Si tu veux garder la main sur les paquets systeme, coupe l installation automatique:

```yaml
system_packages:
  install: false
```

Par defaut, la valeur reste active. Quand elle vaut `false`, SpeedDeploy prepare le reste du deploiement sans toucher au gestionnaire de paquets.

### Bloc `system_user` - creation optionnelle de l utilisateur

Quand tu veux laisser SpeedDeploy creer l utilisateur systeme, active ce bloc:

```yaml
system_user:
  create: true
  shell: /usr/sbin/nologin
  home: /srv/gestiolocative
```

Ce bloc est utile pour les serveurs vierges ou les installations standardisees. Si l utilisateur et le groupe existent deja, SpeedDeploy les reutilise.

### Bloc `healthcheck` — verification post-deploiement

Apres le redemarrage, SpeedDeploy interroge le site via `curl` sur `127.0.0.1` en utilisant le domaine comme en-tete `Host` (cela teste le vrai vhost et le socket Gunicorn sans dependre du DNS public ni du TLS). En mode releases, un echec declenche un **rollback automatique** vers la release precedente.

```yaml
healthcheck:
  enabled: true              # defaut: true
  path: /                    # chemin a tester (ex: /healthz)
  host: demo.example.com     # par defaut le domaine du projet
  port: 80                   # optionnel
  expect_status: [200, 204, 301, 302, 308]
  timeout: 10                # secondes par tentative
  retries: 5                 # nombre de tentatives
  delay: 3                   # secondes entre tentatives
```

Mets `enabled: false` si ton application n expose pas de page accessible sans authentification.

### Bloc `database` — sauvegarde avant migration

Avant chaque `migrate`, SpeedDeploy sauvegarde la base dans `shared/backups/` (mode releases) ou `path/backups/` (mode en place). Le mot de passe n est jamais passe en ligne de commande ni affiche dans les logs : il transite par un fichier temporaire `0600` (`PGPASSFILE` / `--defaults-extra-file`).

```yaml
database:
  engine: postgres      # none (defaut), postgres, mysql, sqlite
  name: ma_base
  user: mon_user
  password: secret      # ou laisse vide et fournis-le via .pgpass cote serveur
  host: localhost
  port: 5432
  sqlite_path: db.sqlite3   # pour engine: sqlite, relatif au code
  keep: 5                   # nombre de sauvegardes a conserver
```

Sauvegarde a la demande :

```bash
speeddeploy v2 backup <projet>
```

### Bloc `env` — fichier `.env` et secrets

Les variables declarees sous `env:` sont ecrites dans un fichier `.env` cote serveur (permissions `0640`, proprietaire `user:group`) et injectees dans le service systemd via `EnvironmentFile=`. Le contenu n est jamais affiche dans les logs.

```yaml
env:
  DJANGO_SETTINGS_MODULE: monprojet.settings.prod
  SECRET_KEY: "une-cle-secrete"
  DATABASE_URL: "postgres://user:pass@localhost/ma_base"
```

> Le fichier projet contenant ces secrets est ignore par Git (tout le dossier `projects/` est exclu). Ne committe jamais de secrets.

## Gestion des projets

La V2 inclut aussi des commandes pour administrer les fichiers de configuration projet.

### Lister les projets

```bash
speeddeploy v2 projects list
```

### Afficher un projet

```bash
speeddeploy v2 projects show gestiolocative
```

### Dupliquer un projet

```bash
speeddeploy v2 projects duplicate gestiolocative gestiolocative-staging --path /srv/gestiolocative-staging
```

### Renommer un projet

```bash
speeddeploy v2 projects rename gestiolocative gestiolocative-prod
```

### Supprimer un projet

```bash
speeddeploy v2 projects remove gestiolocative --yes
```

Ces commandes agissent sur les fichiers YAML dans `projects/` et reutilisent le schema V2 existant.

## Toutes les commandes SpeedDeploy

### Resume V2

| Commande | Usage exact |
| --- | --- |
| `speeddeploy v2 config new` | Creer un fichier YAML de projet de maniere interactive. |
| `speeddeploy v2 projects list` | Lister tous les fichiers de configuration projet connus. |
| `speeddeploy v2 projects show <project>` | Afficher la configuration d un projet. |
| `speeddeploy v2 projects duplicate <project> <new>` | Dupliquer une configuration projet sous un nouveau nom. |
| `speeddeploy v2 projects rename <project> <new>` | Renommer un fichier de configuration projet. |
| `speeddeploy v2 projects remove <project>` | Supprimer un fichier de configuration projet. |
| `speeddeploy v2 doctor <project>` | Verifier la configuration, l environnement et le plan avant d executer. |
| `speeddeploy v2 doctor <project> --fix` | Reparer les droits du depot et `safe.directory`. |
| `speeddeploy v2 plan <project>` | Afficher la liste exacte des etapes prevues. |
| `speeddeploy v2 info <project>` | Afficher l etat persistant du dernier deploiement et la release active. |
| `speeddeploy v2 diagnose <project>` | Inspecter l etat du service, les logs, le healthcheck et l etat de deploiement. |
| `speeddeploy v2 deploy <project>` | Lancer un deploiement complet du projet. |
| `speeddeploy v2 update <project>` | Relancer tout le cycle: code, configuration, SSL et redemarrage. |
| `speeddeploy v2 update-code <project>` | Mettre a jour le code applicatif, les dependances Python et les migrations. |
| `speeddeploy v2 update-conf <project>` | Regenerer Gunicorn et la configuration Apache ou Nginx. |
| `speeddeploy v2 update-cert <project>` | Renouveler ou reemettre le certificat SSL. |
| `speeddeploy v2 restart <project>` | Redemarrer le service applicatif et recharger le proxy web. |
| `speeddeploy v2 status <project>` | Consulter l etat du service systemd. |
| `speeddeploy v2 logs <project>` | Lire les journaux du service applicatif. |
| `speeddeploy v2 ssl <project>` | Repasser le provisionnement SSL via Certbot. |
| `speeddeploy v2 superuser <project>` | Creer un superutilisateur Django dans le virtualenv du projet. |
| `speeddeploy v2 rollback <project> --to <release>` | Revenir a une release precise par son nom. |
| `speeddeploy v2 helpers` | Afficher l aide operationnelle et les raccourcis utiles. |

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
speeddeploy v2 config new gestiolocative --branch main --backend ssh --host 203.0.113.10 --connection-user root
```

### Diagnostic

```bash
speeddeploy doctor gestiolocative
speeddeploy plan gestiolocative
speeddeploy helpers
speeddeploy v2 doctor gestiolocative
speeddeploy v2 plan gestiolocative
speeddeploy v2 info gestiolocative
speeddeploy v2 diagnose gestiolocative
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

En pratique:

- utilise `update-code` apres un nouveau `git pull` ou une modification du projet Python
- utilise `update-conf` apres un changement dans les fichiers de service, de proxy ou de template
- utilise `update-cert` quand tu veux forcer Certbot ou reconstruire le certificat du domaine
- utilise `update` quand tu veux relancer toute la chaine: code, conf, SSL et redemarrage

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
speeddeploy v2 rollback gestiolocative
speeddeploy v2 rollback gestiolocative --to 20260628-150000
speeddeploy v2 diagnose gestiolocative
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

## Optimisations du moteur

SpeedDeploy V2 applique maintenant plusieurs optimisations pour reduire le temps d exploitation:

- le virtualenv et les dependances sont reutilises si `requirements.txt` n a pas change
- un virtualenv partiel ou corrompu est nettoye puis reconstruit automatiquement
- `collectstatic` est saute si l arbre du projet n a pas change
- les fichiers de configuration ne sont reecrits que si leur contenu a vraiment change
- les dossiers generes `venv/`, `staticfiles/`, `media/` et `.speeddeploy/` sont ignores pendant les operations Git
- les operations Git utilisent l utilisateur du projet pour eviter les blocages de droits

En pratique, cela reduit les reinstalls, les redemarrages inutiles et les erreurs liees aux permissions.

## Depannage

### "Fichier de configuration introuvable"

Verifie que le fichier existe dans `projects/` et que tu passes le nom du projet sans extension.

### "Backend non supporte"

Verifie que `connection.backend` vaut `local` ou `ssh`.

### "Le backend SSH requiert `connection.host`"

Ajoute une valeur valide pour `host` dans le bloc `connection`.

### "Gestionnaire de paquets non supporte"

Utilise l une de ces valeurs :

- `apt`
- `dnf`
- `yum`
- `apk`
- `pacman`

### "Le deploiement local ne fonctionne que sous Linux/WSL"

Lance la commande sur le serveur Linux cible, ou utilise le backend SSH.

### Erreurs systemd ou sudo

Verifie que l utilisateur cible peut utiliser `sudo` et que `systemd` est bien present sur le serveur.

### Propriete Git douteuse

Si Git affiche `proprietaire douteux detecte` ou `dubious ownership`, SpeedDeploy ajoute automatiquement le depot a `git safe.directory` avant le `pull`.
Cela arrive quand le dossier du projet est clone sous un compte systeme different de l utilisateur qui execute SpeedDeploy.
SpeedDeploy V2 lance maintenant les operations Git avec l utilisateur du projet, ce qui evite aussi les erreurs de type `FETCH_HEAD` ou droits insuffisants.
Si le depot contient des modifications locales, SpeedDeploy V2 les met automatiquement de cote dans un stash standard avant le `pull`, sans essayer d y inclure `venv/`, `staticfiles/`, `media/` ou `.speeddeploy/`.
Si tu veux supprimer les modifications locales au lieu de les conserver, utilise `--discard-local-changes`.

### Reparation automatique

Si tu veux corriger rapidement les problemes de proprietaire ou de `safe.directory`, lance:

```bash
speeddeploy v2 doctor gestiolocative --fix
```

Cette commande ajuste les droits des repertoires de travail et recolle le depot Git a l utilisateur du projet.
Elle remet aussi en etat le cache interne `.speeddeploy/` quand il existe.

### Dossiers generes par le projet

SpeedDeploy ignore maintenant les dossiers generes les plus courants pendant les operations Git :

- `venv/`
- `staticfiles/`
- `media/`
- `.speeddeploy/`

Cela evite que le `stash`, le `clean` ou le `pull` se bloquent sur des fichiers Django generes par le serveur. Le `stash` standard ne cherche plus a les embarquer.
Garde ces dossiers hors de la gestion Git du projet applicatif si possible.

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
