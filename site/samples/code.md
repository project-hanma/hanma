# Syntax Highlighting Samples

A tour of fenced code blocks across the languages most relevant to a Linux
and container-focused workflow. Switch between light and dark mode to see
each theme in action.

---

## Bash

```bash
#!/usr/bin/env bash
set -euo pipefail

LOGFILE="/var/log/deploy.log"
SERVICES=("nginx" "postgresql" "redis")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOGFILE"
}

restart_services() {
    for svc in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            log "Restarting $svc..."
            systemctl restart "$svc"
        else
            log "WARNING: $svc is not running, attempting start..."
            systemctl start "$svc"
        fi
    done
}

restart_services
log "All services processed."
```

---

## Python

```python
#!/usr/bin/env python3
"""Simple HTTP health-check poller."""

import asyncio
import httpx
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CheckResult:
    url: str
    status: int
    elapsed_ms: float
    checked_at: datetime = field(default_factory=datetime.now)

    @property
    def healthy(self) -> bool:
        return 200 <= self.status < 300


async def check(client: httpx.AsyncClient, url: str) -> CheckResult:
    response = await client.get(url, timeout=5.0)
    elapsed = response.elapsed.total_seconds() * 1000
    return CheckResult(url=url, status=response.status_code, elapsed_ms=elapsed)


async def main(urls: list[str]) -> None:
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[check(client, u) for u in urls])

    for r in results:
        icon = "✓" if r.healthy else "✗"
        print(f"  {icon}  {r.status}  {r.elapsed_ms:6.1f}ms  {r.url}")


if __name__ == "__main__":
    targets = [
        "https://example.com",
        "https://httpbin.org/status/200",
        "https://httpbin.org/status/503",
    ]
    asyncio.run(main(targets))
```

---

## YAML

```yaml
# Podman Quadlet — rootless systemd container unit
[Unit]
Description=My Web Application
After=network-online.target
Wants=network-online.target

[Container]
Image=registry.example.com/myapp:latest
ContainerName=myapp

PublishPort=8080:8080

Environment=APP_ENV=production
Environment=LOG_LEVEL=info

Volume=%h/myapp/data:/data:Z
Volume=%h/myapp/config:/config:ro,Z

HealthCmd=curl --fail http://localhost:8080/health
HealthInterval=30s
HealthRetries=3

[Service]
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=default.target
```

---

## Dockerfile / Containerfile

```dockerfile
# syntax=docker/dockerfile:1
FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY --chown=1001:0 . .

# Non-root user (UBI default)
USER 1001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl --fail http://localhost:8080/health || exit 1

ENTRYPOINT ["python", "-m", "gunicorn"]
CMD ["--bind", "0.0.0.0:8080", "--workers", "4", "app:create_app()"]
```

---

## Ansible

```yaml
---
- name: Deploy web application
  hosts: webservers
  become: true
  vars:
    app_version: "{{ lookup('env', 'APP_VERSION') | default('latest') }}"
    app_port: 8080

  tasks:
    - name: Ensure podman is installed
      ansible.builtin.package:
        name: podman
        state: present

    - name: Pull application image
      containers.podman.podman_image:
        name: "registry.example.com/myapp:{{ app_version }}"
        pull: true

    - name: Deploy container
      containers.podman.podman_container:
        name: myapp
        image: "registry.example.com/myapp:{{ app_version }}"
        state: started
        restart_policy: always
        ports:
          - "{{ app_port }}:8080"
        env:
          APP_ENV: production
          LOG_LEVEL: info

    - name: Open firewall port
      ansible.posix.firewalld:
        port: "{{ app_port }}/tcp"
        permanent: true
        state: enabled
        immediate: true
```

---

## INI / Config

```ini
[global]
log_level    = info
data_dir     = /var/lib/myapp
max_workers  = 4

[database]
host         = localhost
port         = 5432
name         = myapp_prod
user         = myapp
# password read from environment: DB_PASSWORD

[cache]
backend      = redis
host         = 127.0.0.1
port         = 6379
ttl_seconds  = 300

[tls]
cert_file    = /etc/myapp/tls/server.crt
key_file     = /etc/myapp/tls/server.key
min_version  = TLSv1.2
```

---

## JSON

```json
{
  "name": "myapp",
  "version": "2.1.0",
  "description": "Example application manifest",
  "runtime": {
    "image": "registry.example.com/myapp:2.1.0",
    "replicas": 3,
    "resources": {
      "requests": { "cpu": "250m", "memory": "256Mi" },
      "limits":   { "cpu": "1000m", "memory": "512Mi" }
    }
  },
  "healthCheck": {
    "path": "/health",
    "intervalSeconds": 30,
    "timeoutSeconds": 5,
    "failureThreshold": 3
  },
  "environment": {
    "APP_ENV": "production",
    "LOG_LEVEL": "info"
  }
}
```

---

## SQL

```sql
-- Monthly active users by plan tier
WITH active_users AS (
    SELECT
        u.id,
        u.plan_tier,
        COUNT(DISTINCT DATE(e.created_at)) AS active_days
    FROM users u
    JOIN events e ON e.user_id = u.id
    WHERE
        e.created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
        AND e.created_at <  DATE_TRUNC('month', NOW())
        AND u.deleted_at IS NULL
    GROUP BY u.id, u.plan_tier
)
SELECT
    plan_tier,
    COUNT(*)                            AS total_users,
    COUNT(*) FILTER (WHERE active_days >= 7)  AS retained_users,
    ROUND(
        COUNT(*) FILTER (WHERE active_days >= 7)::numeric
        / NULLIF(COUNT(*), 0) * 100, 1
    )                                   AS retention_pct
FROM active_users
GROUP BY plan_tier
ORDER BY retention_pct DESC;
```

---

## Nginx

```nginx
server {
    listen       443 ssl http2;
    server_name  example.com www.example.com;

    ssl_certificate     /etc/nginx/tls/fullchain.pem;
    ssl_certificate_key /etc/nginx/tls/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Content-Type-Options    "nosniff"          always;
    add_header X-Frame-Options           "DENY"             always;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    location /static/ {
        root      /var/www/myapp;
        expires   30d;
        add_header Cache-Control "public, immutable";
    }
}

# Redirect HTTP → HTTPS
server {
    listen      80;
    server_name example.com www.example.com;
    return      301 https://$host$request_uri;
}
```
