django-fab-server
=================

**Atualizado para ubuntu 20.04 utilizando docker rodando com o script rodando com python3**

Como funciona?

<p>É um fabric que acessa o servidor e instala todas dependencias. <BR>É preciso clonar o arquivo variable-template.env e renomear para variable.env e configurar as variáveis antes de rodar.</p>

requirements:

    git
    docker
    docker-compose


Clone o projeto na máquina na sua pasta de projetos:

    git clone git@github.com:willemallan/django-fab-server.git


Criar o container:

    docker-compose up --build


Configurando uma máquina para rodar python/django e mysql:

<ul>
    <li>
        <a href="html/NEWDEV.md"><b>Local</b></a> é para configurar uma maquina linux para trabalhar com python/django.
    </li>
    <li>
        <a href="html/NEWSERVER.md"><b>Servidor</b></a> é para configurar um servidor linux para rodar sites em python/django.
    </li>
</ul>


IMPORTANTE
==========

## Para dar permissão de acesso externo ao mysql altere o arquivo /etc/mysql/my.conf comentando o comando bind 127.0.0.1

## Para o funcionamento de projetos em php altere com sudo a linha 768 do arquivo /etc/php5/fpm/php.ini - mude para 1 e descomente a var cgi.fix_pathinfo=0

Listando os comandos:

    docker-compose run fab


Executar um comando:

    docker-compose run fab fab newserver


Comandos disponíveis:

    adduser             Criar um usuário no servidor
    aptget              Executa apt-get install no servidor ex: fab aptget:lib...
    build_local         Instalar build-essential
    build_server        Instalar build-essential e outros pacotes importantes ...
    create_password     Gera uma senha - parametro tamanho
    delaccount          Deletar conta no servidor
    dropbase            Deletar banco de dados no servidor
    git_local           Instalando git
    git_server          Instalar git no servidor
    listaccount         Lista usuários do servidor

    log
    login               Acessa o servidor

    mysql_local         Instalando MySQL
    mysql_restart       Restart mysql no servidor
    mysql_server        Instalar MySQL no servidor
    mysql_start         start mysql no servidor
    mysql_stop          stop mysql no servidor

    newaccount          Criar uma nova conta do usuário no servidor
    newbase             Criar banco de dados e usuário no servidor
    newdev              Configura uma maquina local Ubuntu para trabalhar pyth...
    newproject          Criar novo projeto local
    newserver           Configurar e instalar todos pacotes necessários para ...
    nginx_reload        Reload nginx no servidor
    nginx_restart       Restart nginx no servidor
    nginx_start         Start nginx no servidor
    nginx_stop          Stop nginx no servidor
    others_server       Instalar nginx e supervisor
    proftpd_restart     restart proftpd
    python_local        Instalando todos pacotes necessários
    python_server       Instalar todos pacotes necessários do python no servi...
    reboot              Reinicia o servidor
    restart             Reiniciar servicos no servidor
    restart_server      Restart aplicação no servidor
    start_server        Start aplicação no servidor
    stop_server         Stop aplicação no servidor
    supervisor_restart  Restart supervisor no servidor
    supervisor_start    Start supervisor no servidor
    supervisor_stop     Stop supervisor no servidor
    update_local        Atualizando pacotes
    update_server       Atualizando pacotes no servidor
    upgrade_local       Atualizando programas
    upgrade_server      Atualizar programas no servidor
    upload_public_key   Faz o upload da chave ssh para o servidor
    userdel             Deletar usuário no servidor
    write_file
