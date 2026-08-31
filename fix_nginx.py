from fabric import Connection

content = """upstream mymoneyx {
    server 127.0.0.1:8002;
}

# Redirecionamento HTTP -> HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name mymoneyx.top www.mymoneyx.top static.mymoneyx.top media.mymoneyx.top;
    return 301 https://$host$request_uri;
}

# Servidor HTTPS Principal
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name mymoneyx.top www.mymoneyx.top;

    ssl_certificate /etc/letsencrypt/live/mymoneyx.top/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mymoneyx.top/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    client_max_body_size 50M;

    access_log /home/mymoneyx/logs/access.log;
    error_log /home/mymoneyx/logs/error.log;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;

    # Arquivos estaticos
    location /static/ {
        alias /home/mymoneyx/project/staticfiles/;
        expires 30d;
        add_header Cache-Control public;
        access_log off;
    }

    # Arquivos de media
    location /media/ {
        alias /home/mymoneyx/project/media/;
        expires 7d;
        access_log off;
    }

    # Proxy reverso para Gunicorn
    location / {
        proxy_pass http://mymoneyx;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
"""

with open("/tmp/clean_nginx.conf", "w") as f:
    f.write(content)

c = Connection(host="209.145.59.193", user="root")
c.put("/tmp/clean_nginx.conf", "/home/mymoneyx/nginx.conf")
c.run("nginx -t")
c.run("systemctl reload nginx")
print("=== SUCESSO NGINX RECARREGADO ===")
c.run("curl -I https://mymoneyx.top")
