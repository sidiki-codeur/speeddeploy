# SpeedDeploy

SpeedDeploy is a CLI tool for deploying a Django app on Debian VPS instances with Gunicorn, Apache, and Certbot.

## Install

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

## Config

Create a project file in `projects/`, for example `projects/gestiolocative.yml`:

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
```

## Commands

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

## Notes

- The project targets Debian and Ubuntu.
- System commands use `sudo` only where needed.
- Never commit production secrets to the repository.
