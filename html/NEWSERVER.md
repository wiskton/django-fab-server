django-fab-server
=================


Alterar configurações no fabfile.py:

    username = 'root'
    ip = '192.168.1.111'


Configura um novo servidor instalando todos pacotes necessários:

    fab newserver


<h2>Contas</h2>

<p>cria um usuario e banco por site para deixar separado as estruturas, pois cada site tem suas senhas e em caso de invasão só terão acesso a um projeto e não a todos.</p>

Criar uma nova conta no servidor:

    fab novaconta


Exclui uma nova conta no servidor:

    fab delconta


<h2>Clonar projeto no servidor</h2>

<p>Estrutura dos projetos - são utilizados 3 dominios media e static separados</p>

<ul>
    <li>www.willemallan.com.br ou willemallan.com.br</li>
    <li>static.willemallan.com.br - /home/willemallan/project/static</li>
    <li>media.willemallan.com.br - /home/willemallan/project/media</li>
</ul>

exemplo do settings.py do projeto:

    MEDIA_ROOT = os.path.join(PROJECT_PATH, '..', 'media')
    MEDIA_URL = 'http://media.willemallan.com.br/'


    STATIC_ROOT = os.path.join(PROJECT_PATH, '..', 'static')
    STATIC_URL = 'http://static.willemallan.com.br/'

    STATICFILES_DIRS = (
        os.path.join(PROJECT_PATH, 'static'),
    )

    TEMPLATE_DIRS = (
        os.path.join(PROJECT_PATH, '..', 'templates')
    )


git - repositório

<p>Antes de clonar precisa configurar o settings do projeto de acordo com os dados que o script gera.</p>
<p>Quando vai clonar um projeto eu utilizo a chave do usuário criado. E no bitbucket coloco no deploy key do repositório assim o servidor só pode ler os arquivos e nunca pode commitar evitando problemas que acontecem de alguém ir no servidor e arrumar de lá e não dar commit.</p>

Roteiro:

    workon willemallan
    fab login

    ssh-keygen && cat ~/.ssh/id_rsa.pub
    pegar chave adicionar no projeto do bitbucket
    git clone git@bitbucket.org:willemarf/willemallan.git project

    . env/bin/activate
    easy_install -U distribute
    pip install -r project/requirements.txt
    python project/manage.py syncdb
    python project/manage.py migrate
    python project/manage.py collectstatic --noinput
    python project/manage.py runserver 8060
    python project/manage.py run_gunicorn
    exit
    fab deploy servidor2 restart


reiniciar nginx e supervisor

    fab restart


Outros comandos
================

Reinicie NGINX

    fab nginx_restart

Reinicie SUPERVISOR

    fab supervisor_restart











