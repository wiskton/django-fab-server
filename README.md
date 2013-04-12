django-fab-server
=================

Instala e configura todos os pacotes necessários para configurar um servidor com python/django + nginx + supervisor no ubuntu



Configura um novo servidor instalando todos pacotes necessários:

    fab newserver


Criar uma nova conta no servidor:

    fab novaconta

Editar os arquivos da pasta do usuário alterando o domínio:

    nginx.conf
    supervisor.conf

Reiniciar nginx e supervisor:

    fab nginx_restart
    fab supervisor_restart

clonar projeto do bitbucket

    fab login
    su - NOVACONTA
    ssh-keygen && cat ~/.ssh/id_rsa.pub
    git clone git@bitbucket.org:willemarf/REPOSITORIO.git project
    source env/bin/activate
    pip install -r project/requirements.txt

criando as tabelas da aplicação:

    python project/manage.py syncdb
    python project/manage.py migrate

rodar projeto para ver se ocorreu tudo bem:

    python project/manage.py runserver 8000

criar pasta para collectstatic (depende do projeto):

    mkdir ~/project/config/static/

reiniciar nginx e supervisor

    fab restart


Outros comandos
================

Reinicie NGINX

    fab nginx_restart

Reinicie SUPERVISOR

    fab supervisor_restart
