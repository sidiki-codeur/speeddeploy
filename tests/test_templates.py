from __future__ import annotations

import bootstrap_tests  # noqa: F401

import unittest

from jinja2 import Environment, PackageLoader

from tests.support import make_v2_template


class TemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = Environment(
            loader=PackageLoader("speeddeploy", "templates"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def test_gunicorn_template_renders_expected_execstart(self) -> None:
        spec = make_v2_template()
        rendered = self.env.get_template("gunicorn.service.j2").render(
            project=spec.project,
            domain=spec.domain,
            repo=spec.repo,
            path="/srv/demo",
            app_dir="/srv/demo",
            socket="/srv/demo/gunicorn.sock",
            user=spec.user,
            group=spec.group,
            wsgi=spec.wsgi,
            python=spec.python,
            venv="/srv/demo/venv",
            static_dir="/srv/demo/staticfiles",
            media_dir="/srv/demo/media",
            workers=spec.workers,
            env_file="/srv/demo/shared/.env",
        )

        self.assertIn("EnvironmentFile=-/srv/demo/shared/.env", rendered)
        self.assertIn("ExecStart=/srv/demo/venv/bin/gunicorn --workers 3 --bind unix:/srv/demo/gunicorn.sock config.wsgi:application", rendered)
        self.assertIn("PrivateTmp=true", rendered)
        self.assertIn("NoNewPrivileges=true", rendered)
        self.assertIn("ProtectSystem=full", rendered)

    def test_apache_template_renders_proxy_and_static_paths(self) -> None:
        spec = make_v2_template()
        rendered = self.env.get_template("apache.conf.j2").render(
            project=spec.project,
            domain=spec.domain,
            repo=spec.repo,
            path="/srv/demo",
            user=spec.user,
            group=spec.group,
            wsgi=spec.wsgi,
            python=spec.python,
            venv="/srv/demo/venv",
            static_dir="/srv/demo/staticfiles",
            media_dir="/srv/demo/media",
            workers=spec.workers,
            socket="/srv/demo/gunicorn.sock",
        )

        self.assertIn("ServerName demo.example.com", rendered)
        self.assertIn("Alias /static /srv/demo/staticfiles", rendered)
        self.assertIn("ProxyPass / unix:/srv/demo/gunicorn.sock|http://localhost/", rendered)
        self.assertIn("ServerSignature Off", rendered)
        self.assertIn("Header always set X-Content-Type-Options \"nosniff\"", rendered)

    def test_nginx_template_renders_proxy_and_timeout_defaults(self) -> None:
        spec = make_v2_template()
        rendered = self.env.get_template("nginx.conf.j2").render(
            project=spec.project,
            domain=spec.domain,
            repo=spec.repo,
            path="/srv/demo",
            user=spec.user,
            group=spec.group,
            wsgi=spec.wsgi,
            python=spec.python,
            venv="/srv/demo/venv",
            static_dir="/srv/demo/staticfiles",
            media_dir="/srv/demo/media",
            workers=spec.workers,
            socket="/srv/demo/gunicorn.sock",
        )

        self.assertIn("server_name demo.example.com;", rendered)
        self.assertIn("alias /srv/demo/staticfiles/;", rendered)
        self.assertIn("proxy_pass http://unix:/srv/demo/gunicorn.sock;", rendered)
        self.assertIn("server_tokens off;", rendered)
        self.assertIn("client_max_body_size 50m;", rendered)
        self.assertIn("proxy_redirect off;", rendered)
