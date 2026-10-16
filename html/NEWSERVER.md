Provisionamento de Servidor Seguro e Isolado
=============================================

Instala e configura todos os pacotes e configurações de segurança necessários para executar múltiplas aplicações Django (Python), Node.js e PHP em um único servidor Linux, com Nginx, Gunicorn, Supervisor e isolamento estrito por usuário.

Suporta **Ubuntu**, **Debian**, **Fedora**, **CentOS Stream/RHEL** e **Arch Linux**.

---

### Configuração Inicial

Os comandos abaixo devem ser executados a partir da pasta `server/` deste repositório.
Crie seu arquivo de configuração local a partir do template:

    cd server
    cp local_settings-template.py local_settings.py

Edite `server/local_settings.py`:

    user = 'root'
    host = 'IP_DO_SERVIDOR'
    chave = '~/.ssh/id_ed25519'  # caminho da sua chave privada
    os_family = 'debian'        # 'debian', 'fedora', 'rhel' ou 'arch'

Garanta que sua chave pública SSH esteja autorizada no servidor:

    ssh-copy-id root@IP_DO_SERVIDOR
    ssh root@IP_DO_SERVIDOR  # deve autenticar sem pedir senha interativa

---

### Provisionar o Servidor do Zero

Instala todos os pacotes (build, python, node, nginx, mysql/mariadb, supervisor, certbot, ftp) e configura o Supervisor seguro (socket unix 0700):

    cd server
    fab newserver

---

### Criar uma Nova Conta de Projeto

Cria usuário Linux exclusivo com permissões restritas (750), virtualenv, configurações Nginx e Supervisor, regras mínimas em sudoers e banco de dados:

    fab newaccount

Durante a execução:
1. Digite o nome da conta (ex: `meusite`).
2. Digite o domínio (ex: `meusite.com.br`).
3. Escolha a linguagem:
   - `1` para **Python / Django** (solicita porta TCP e pasta do wsgi/settings)
   - `2` para **PHP** (cria estrutura `public_html`)
   - `3` para **NPM / Node.js** (`1` para SSR com Supervisor ou `2` para SPA estático)
4. Senhas seguras do usuário Linux e do banco MySQL são geradas automaticamente.

> **Importante**: O comando registra o novo processo no Supervisor via `reread && update` e recarrega o Nginx com `systemctl reload nginx`, **sem reiniciar nem interromper os outros projetos já existentes no servidor**.

---

### Migrar Projetos Legados

Se você já possui projetos rodando no servidor sob a configuração antiga:

#### Migrar uma conta específica:
    fab migrate-account
    # Digite o nome da conta existente

#### Migrar todas as contas detectadas no servidor:
    fab migrate-all-projects

O procedimento de migração:
- Cria um backup prévio completo em `/home/{conta}/.backup_migration_{timestamp}/`
- Instala o `/usr/local/bin/supervisorctl-restricted`
- Ajusta a permissão do diretório para `chmod 750` e adiciona `www-data` ao grupo
- Configura o arquivo `/etc/sudoers.d/{conta}` com permissão mínima (0440)
- Move/copia a configuração para `/etc/supervisor/conf.d/{conta}.conf` com posse do root
- Executa `supervisorctl reread && supervisorctl update` sem reiniciar outros serviços

#### Reverter em caso de imprevisto:
    fab rollback-migration --conta=meusite

---

### Deploy pelo Desenvolvedor (Sem Root)

No repositório da aplicação, o desenvolvedor utiliza o `client/fabfile.py`:

    # Configuração inicial (chaves SSH, clone e bootstrap)
    fab config

    # Deploy rotineiro (conecta com o usuário da aplicação, sem root)
    fab deploy

    # Consultar status dos processos
    fab status

    # Reiniciar aplicação de forma restrita
    fab restart

    # Teste de resposta HTTP
    fab health-check
