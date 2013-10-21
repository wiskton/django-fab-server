Utilizando script para Servidor
=================

<p>Instala e configura todos os pacotes necessários para configurar um servidor com python/django + nginx + supervisor no ubuntu.</p>


Alterar configurações no fabfile.py:

    username = 'root'
    host = '192.168.1.111'


Configura um novo servidor instalando todos pacotes necessários:

    fab newserver

Reiniciar nginx e supervisor

    fab restart


<h3>Contas</h3>

<p>Cria um usuário e banco por site para deixar separado as estruturas, pois cada site tem suas senhas e em caso de invasão só terão acesso a um projeto e não a todos.</p>

Criar uma nova conta no servidor:

    fab novaconta


Exclui uma conta no servidor:

    fab delconta


<h3>Clonar projeto no servidor</h3>

<p><a href="https://github.com/willemallan/django-fab-server/blob/master/projeto/fabfile.py">fabfile</a> usado no projeto para subir os dados no servidor.</p>

<p>Estrutura dos projetos - são utilizados 3 domínios media e static separados.</p>

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

<h3>Clonando projeto</h3>

<p>Antes de clonar precisa configurar o settings do projeto de acordo com os dados que o script gera.</p>
<p>Quando vai clonar um projeto é importante adicionar a chave do servidor no bitbucket apenas no deploy key do projeto. Assim o servidor só poderá ler os arquivos e nunca poderá escrever, evitando problemas que acontecem do programador arrumar os bugs do servidor e esquecer de dar commit.</p>


Configurar o servidor pela primeira vez (precisa copiar a chave ssh para o repositório do servidor):

    fab config


Rode o projeto para testar se há alguem erro (depois pode cancelar ctrl+c):

    python project/manage.py runserver 8060


Rode o projeto com o gunicorn para testar se ele esta instalado no env e no INSTALLED_APPS:

    python project/manage.py run_gunicorn


Sai do servidor:
    exit


Atualiza o repositório no servidor e reinicia a aplicação do supervisor:

    fab deploy servidor2 restart


<p>Servidor2 muda para root pois para reiniciar a aplicação precisa ser o root e não o usuário da conta.</p>

Outros comandos
================

Reinicie NGINX

    fab nginx_restart

Reinicie SUPERVISOR

    fab supervisor_restart











