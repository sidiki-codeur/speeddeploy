# SpeedDeploy

SpeedDeploy is a CLI tool for deploying Django applications on Linux servers.
It now ships with two layers:

- V1, the legacy local deployment flow
- V2, the backend-aware engine for local Linux/WSL and remote SSH deployments

V2 is the recommended path for new projects.

## What SpeedDeploy Does

SpeedDeploy automates the repetitive parts of a Django deployment:

- prepare the target directory
- clone or update the Git repository
- create and refresh the Python virtual environment
- run Django migrations and `collectstatic`
- install and enable Gunicorn as a systemd service
- render Apache or Nginx configuration
- provision SSL with Certbot
- restart or inspect the running services

## Requirements

### Local machine

- Python 3.10 or newer
- `pip`
- Git
- On Linux deployments: Linux or WSL is required for local execution
- On Windows: use SpeedDeploy to generate configs, plan deployments, or deploy through SSH

### Target server

- A Linux server with `systemd`
- A Git repository accessible from the server
- `sudo` privileges for package installation and service management
- For SSL: a public domain name pointing to the server

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Linux or macOS:

```bash
source venv/bin/activate
```

Install the project:

```bash
pip install -r requirements.txt
pip install -e .
```

## Package Layout

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

## How It Works

SpeedDeploy reads a YAML file from `projects/` by default.
The file describes the Django project, the server target, and the deployment backend.

Basic flow:

1. create a project config
2. inspect the plan with `doctor` or `plan`
3. run a dry-run
4. run the real deployment
5. enable SSL if needed
6. use `update`, `restart`, `status`, and `logs` for day-2 operations

## V1 And V2

### V1

V1 keeps the original simple flow:

- local execution
- Apache + Gunicorn
- Debian-style assumptions
- quick start for simple VPS setups

### V2

V2 introduces a real deployment model:

- `local` backend for Linux and WSL
- `ssh` backend for remote execution
- Apache or Nginx
- multiple package managers
- stronger config validation
- clearer execution engine

## Quick Start

### 1. Create a config

V2 interactive config creation:

```bash
speeddeploy v2 config new
```

V1 config creation:

```bash
speeddeploy config new
```

### 2. Inspect the plan

```bash
speeddeploy v2 plan gestiolocative
```

### 3. Run a dry-run

```bash
speeddeploy v2 --dry-run deploy gestiolocative
```

### 4. Deploy

```bash
speeddeploy v2 deploy gestiolocative
```

### 5. Enable SSL

```bash
speeddeploy v2 ssl gestiolocative
```

### 6. Update later

```bash
speeddeploy v2 update gestiolocative
```

## Configuration Guide

SpeedDeploy supports two config blocks:

- `target` for the deployment platform
- `connection` for the execution backend

### V2 Example Config

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

### SSH Example

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

## V2 Config Fields

### Required fields

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

### Target block

- `os`: target operating system, currently informational
- `init_system`: currently `systemd`
- `web_server`: `apache` or `nginx`
- `app_server`: currently `gunicorn`
- `ssl_provider`: `certbot`, `none`, or `disabled`
- `package_manager`: `apt`, `dnf`, `yum`, `apk`, or `pacman`

### Connection block

- `backend`: `local` or `ssh`
- `host`: required for SSH
- `port`: SSH port, default `22`
- `user`: SSH login user, optional
- `identity_file`: SSH private key, optional

## Command Reference

### Root CLI

```bash
speeddeploy --help
speeddeploy --dry-run deploy gestiolocative
speeddeploy --projects-dir projects v2 plan gestiolocative
```

### Helpers

```bash
speeddeploy helpers
speeddeploy helpers gestiolocative
```

### Config generation

```bash
speeddeploy config new
speeddeploy config new gestiolocative --domain locative.emanager.cloud --repo https://github.com/TON_COMPTE/gestiolocative.git

speeddeploy v2 config new
speeddeploy v2 config new gestiolocative --backend ssh --host 203.0.113.10 --connection-user root
```

### Diagnostics

```bash
speeddeploy doctor gestiolocative
speeddeploy plan gestiolocative
speeddeploy helpers
speeddeploy v2 doctor gestiolocative
speeddeploy v2 plan gestiolocative
speeddeploy v2 helpers
```

### Deployment lifecycle

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

### V2 lifecycle

```bash
speeddeploy v2 deploy gestiolocative
speeddeploy v2 update gestiolocative
speeddeploy v2 restart gestiolocative
speeddeploy v2 status gestiolocative
speeddeploy v2 logs gestiolocative
speeddeploy v2 ssl gestiolocative
speeddeploy v2 superuser gestiolocative
```

## Recommended Operational Flow

For a new project:

1. create the V2 config
2. run `speeddeploy v2 doctor <project>`
3. run `speeddeploy v2 plan <project>`
4. run `speeddeploy v2 --dry-run deploy <project>`
5. run `speeddeploy v2 deploy <project>`
6. validate the site and SSL
7. use `speeddeploy v2 update <project>` for later changes

## Deployment Backends

### Local backend

Use this when the machine running SpeedDeploy is the target server itself.
This is the simplest mode and works on Linux or WSL.

### SSH backend

Use this when SpeedDeploy runs from your workstation and deploys to a remote Linux server.
You need:

- SSH access
- a reachable host
- proper sudo rights on the remote server
- Git access from the remote host

## Nginx Vs Apache

### Apache

Use Apache when you want the classic Debian/Ubuntu reverse proxy stack.
SpeedDeploy renders a vhost file and enables the site automatically.

### Nginx

Use Nginx when you prefer an Nginx reverse proxy in front of Gunicorn.
SpeedDeploy renders an Nginx site config and reloads Nginx.

## Day-2 Operations

### Check service status

```bash
speeddeploy v2 status gestiolocative
```

### Read logs

```bash
speeddeploy v2 logs gestiolocative
```

### Restart services

```bash
speeddeploy v2 restart gestiolocative
```

### Create a Django superuser

```bash
speeddeploy v2 superuser gestiolocative
```

## Troubleshooting

### "Configuration file not found"

Check that the file exists in `projects/` and that you are passing the project name without extension.

### "Unsupported backend"

Make sure `connection.backend` is `local` or `ssh`.

### "SSH backend requires `connection.host`"

Add a valid `host` value in the `connection` block.

### "Unsupported package manager"

Use one of:

- `apt`
- `dnf`
- `yum`
- `apk`
- `pacman`

### "Local deployment only works on Linux/WSL"

Run the command on the target Linux host, or use the SSH backend.

### Systemd or sudo failures

Check that the target user can run `sudo` and that `systemd` is available on the server.

## Security Notes

- Never commit secrets, private keys, or production passwords.
- Keep SSH keys outside the repository.
- Review generated files before enabling SSL on a production domain.
- Use `--dry-run` before the first real deployment.

## Development Notes

The codebase is split into:

- `speeddeploy/` for the V1 flow
- `speeddeploy/v2/` for the new backend-aware engine

This makes it possible to evolve the tool without breaking the simpler path.

## Public Release Checklist

Before publishing to GitHub:

1. review every config file in `projects/`
2. remove any real credentials
3. verify the README examples
4. run the syntax checks locally
5. test `speeddeploy v2 config new`
6. test `speeddeploy v2 --dry-run deploy <project>`
