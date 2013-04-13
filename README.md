django-fab-server
=================

Instala e configura todos os pacotes necessários para configurar um servidor com python/django + nginx + supervisor no ubuntu


Configurando uma máquina para rodar python/django e mysql:

<ul>
    <li>
        <a href="html/NEWDEV.md">Local</a>
    </li>
    <li>
        <a href="html/NEWSERVER.md">Servidor</a>
    </li>
</ul>



Listando os comandos:

    fab list

Comandos disponíveis:

    adduser             Criar um usuário no servidor
    build_local         Instalar build-essential
    build_server        Instalar build-essential e outros pacotes importante...
    delconta            Deletar conta no servidor
    dropbase            Deletar banco de dados no servidor
    gera_senha          Gera uma senha - parametro tamanho
    git_local           Instalando git
    git_server          Instalar git no servidor
    log
    login               Acessa o servidor
    mysql_local         Instalando MySQL
    mysql_server        Instalar MySQL no servidor
    newbase             Criar banco de dados e usuário no servidor
    newdev              Configura uma maquina local Ubuntu para trabalhar py...
    newproject          Criar novo projeto local
    newserver           Configurar e instalar todos pacotes necessários par...
    nginx_reload        Reload nginx no servidor
    nginx_restart       Restart nginx no servidor
    nginx_start         Start nginx no servidor
    nginx_stop          Stop nginx no servidor
    novaconta           Criar uma nova conta do usuário no servidor
    outros_server       Instalar nginx e supervisor
    python_local        Instalando todos pacotes necessários
    python_server       Instalar todos pacotes necessários do python no ser...
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
