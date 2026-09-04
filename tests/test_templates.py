import re

from jinja2 import Environment, FileSystemLoader

SAMPLE_CONTEXT = {
    "conta": "acme",
    "dominio": "acme.com.br",
    "porta": "8060",
    "pasta_settings": "config",
    "nginx_user": "www-data",
    "php_fpm_sock": "/run/php/php8.3-fpm.sock",
}

# bashrc não é usado por write_file() em nenhum lugar do fabfile.py
NON_JINJA_FILES = {"bashrc"}


def _jinja_env(inc_dir):
    return Environment(loader=FileSystemLoader(str(inc_dir)))


def test_all_jinja_templates_render_without_undefined_variables(inc_dir):
    env = _jinja_env(inc_dir)
    for path in sorted(inc_dir.iterdir()):
        if not path.is_file() or path.name in NON_JINJA_FILES:
            continue
        template = env.get_template(path.name)
        rendered = template.render(**SAMPLE_CONTEXT)
        assert "{{" not in rendered, "{0}: variavel jinja nao substituida".format(
            path.name
        )
        assert "{%" not in rendered


def test_nginx_conf_uses_sample_values(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("nginx.conf").render(**SAMPLE_CONTEXT)
    assert "acme.com.br" in rendered
    assert "8060" in rendered
    assert "/home/acme/" in rendered


def test_nginx_php_conf_targets_configured_fpm_socket(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("nginx_php.conf").render(**SAMPLE_CONTEXT)
    assert "unix:/run/php/php8.3-fpm.sock;" in rendered
    assert "php5-fpm" not in rendered


def test_nginx_php_conf_socket_follows_php_fpm_sock_variable(inc_dir):
    # o socket não fica mais fixo no template -- muda conforme a distro
    # (ver _PHP_FPM_SOCK_BY_FAMILY em server/fabfile.py)
    env = _jinja_env(inc_dir)
    context = dict(SAMPLE_CONTEXT, php_fpm_sock="/run/php-fpm/www.sock")
    rendered = env.get_template("nginx_php.conf").render(**context)
    assert "unix:/run/php-fpm/www.sock;" in rendered
    assert "php8.3-fpm.sock" not in rendered


def test_nginx_server_conf_uses_configured_worker_user(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("nginx_server.conf").render(**SAMPLE_CONTEXT)
    assert "user www-data;" in rendered

    context = dict(SAMPLE_CONTEXT, nginx_user="nginx")
    rendered = env.get_template("nginx_server.conf").render(**context)
    assert "user nginx;" in rendered


def test_supervisor_ini_uses_wsgi_module_not_run_gunicorn(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("supervisor.ini").render(**SAMPLE_CONTEXT)
    assert "config.wsgi:application" in rendered
    assert "run_gunicorn" not in rendered


def test_nginx_node_conf_uses_sample_values(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("nginx_node.conf").render(**SAMPLE_CONTEXT)
    assert "acme.com.br" in rendered
    assert "8060" in rendered
    assert "proxy_pass http://acme;" in rendered
    assert "proxy_set_header Upgrade $http_upgrade;" in rendered


def test_nginx_npm_static_conf_uses_dist_and_spa_routing(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("nginx_npm_static.conf").render(**SAMPLE_CONTEXT)
    assert "acme.com.br" in rendered
    assert "root /home/acme/project/dist/;" in rendered
    assert "try_files $uri $uri/ /index.html;" in rendered


def test_supervisor_node_ini_uses_command_and_port(inc_dir):
    env = _jinja_env(inc_dir)
    context = dict(SAMPLE_CONTEXT, npm_start_cmd="npm start")
    rendered = env.get_template("supervisor_node.ini").render(**context)
    assert "command=npm start" in rendered
    assert 'PORT="8060"' in rendered
    assert "user=acme" in rendered


def test_inc_dir_has_no_leftover_django17_template(inc_dir):
    assert not (inc_dir / "supervisor_django17.ini").exists()
