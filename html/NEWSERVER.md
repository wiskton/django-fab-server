django-fab-server
=================

Instalar na máquina pip e fabric distribuições linux badeadas no debian:

    sudo apt-get install python-pip
    sudo pip install fabric


Alterar configurações no fabfile.py:

    username = 'root'
    ip = '192.168.1.111'


Configura um novo servidor instalando todos pacotes necessários:

    fab newserver

Criar uma nova conta no servidor:

    fab novaconta

não esquecer de editar o arquivo /home/conta/nginx.conf e /home/conta/supervisord.ini alterando para o domínio correto.


Reiniciar nginx e supervisor:

    fab restart

clonar projeto do bitbucket

    fab login
    su - NOVACONTA
    ssh-keygen && cat ~/.ssh/id_rsa.pub
    git clone git@bitbucket.org:willemarf/REPOSITORIO.git project
    source env/bin/activate
    pip install -r project/requirements.txt

dependendo do projeto precisa criar os links simbolicos de media e static, o nginx cai na pasta raiz então precisa ter os diretórios static e media:
    ln -s project/static static
    ln -s project/media media

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
