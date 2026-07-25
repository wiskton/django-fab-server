import re

from jinja2 import Environment, FileSystemLoader

SAMPLE_CONTEXT = {
    "conta": "acme",
    "dominio": "acme.com.br",
    "porta": "8060",
    "pasta_settings": "config",
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


def test_nginx_php_conf_targets_php83_fpm_socket(inc_dir):
    content = (inc_dir / "nginx_php.conf").read_text()
    assert "php8.3-fpm.sock" in content
    assert "php5-fpm" not in content


def test_supervisor_ini_uses_wsgi_module_not_run_gunicorn(inc_dir):
    env = _jinja_env(inc_dir)
    rendered = env.get_template("supervisor.ini").render(**SAMPLE_CONTEXT)
    assert "config.wsgi:application" in rendered
    assert "run_gunicorn" not in rendered


def test_inc_dir_has_no_leftover_django17_template(inc_dir):
    assert not (inc_dir / "supervisor_django17.ini").exists()
