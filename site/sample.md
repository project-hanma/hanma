# The Linux Command Line: A Practical Guide

A no-nonsense reference for engineers who live in the terminal. This guide
covers everyday tools, shell patterns, and system administration tasks on
RHEL-compatible distributions.

---

## Getting Around

Navigation is the foundation of everything. Knowing these cold saves time every
single day.

| Command | What it does |
|---|---|
| `pwd` | Print current working directory |
| `cd -` | Jump back to the previous directory |
| `ls -lah` | Long list with human-readable sizes, including hidden files |
| `tree -L 2` | Directory tree, two levels deep |
| `find . -name "*.log" -mtime -7` | Find `.log` files modified in the last 7 days |

### Jumping Around Faster

The `pushd` / `popd` stack is underused:

```bash
pushd /etc/nginx        # save current dir, move to /etc/nginx
pushd /var/log          # stack now: /var/log /etc/nginx ~
popd                    # back to /etc/nginx
popd                    # back to ~
```

---

## Working with Files

### Viewing and Searching

```bash
# Page through a file with search support
less /var/log/messages

# Follow a live log
tail -f /var/log/messages

# Search for a pattern recursively
grep -rn "error" /var/log/ --include="*.log"

# Count matching lines
grep -c "FAILED" /var/log/secure
```

> **Tip:** Combine `grep` with `--color=auto` in your shell alias to make
> matches pop visually. Add it to `~/.bashrc` or `~/.bash_profile`.

### Copying, Moving, Deleting

```bash
# Recursive copy preserving attributes
cp -av /source/dir /destination/

# Move (rename) with verbose output
mv -v old-name.conf new-name.conf

# Delete with confirmation prompt
rm -i suspicious-file.txt

# Wipe a directory tree (no recovery — be certain)
rm -rf /tmp/scratch/
```

---

## Processes and System Resources

### Snapshot and Live Views

```bash
# Static snapshot of all processes
ps aux

# Filter by name
ps aux | grep nginx

# Interactive real-time view
top

# Improved top — install if missing
htop

# Per-process memory map
pmap -x <PID>
```

### Killing Processes

Signals matter. Don't reach for `-9` first.

| Signal | Number | Meaning |
|---|---|---|
| `SIGTERM` | 15 | Polite shutdown request (default) |
| `SIGHUP` | 1 | Reload configuration |
| `SIGKILL` | 9 | Unconditional termination |

```bash
kill -15 <PID>      # ask nicely
kill -1  <PID>      # reload (e.g. nginx, sshd)
kill -9  <PID>      # last resort only
pkill -f "python ssg.py"   # kill by name pattern
```

---

## Disk and Storage

```bash
# Disk usage — human readable, summarised
df -h

# Find what is eating space under /var
du -sh /var/* | sort -rh | head -20

# Block device layout
lsblk

# Filesystem and mount details
findmnt --real

# Check and repair (unmounted fs only)
fsck /dev/sdb1
```

---

## Networking

### Connectivity Checks

```bash
# Basic reachability
ping -c 4 8.8.8.8

# Trace the route
traceroute 8.8.8.8

# DNS lookup
dig example.com A +short

# Reverse DNS
dig -x 93.184.216.34 +short
```

### Ports and Sockets

```bash
# All listening TCP/UDP ports
ss -tulnp

# Who is using port 8080?
ss -tulnp | grep 8080

# Or with lsof
lsof -i :8080
```

### Transferring Files

```bash
# Download a file
curl -O https://example.com/file.tar.gz

# Download with progress bar and follow redirects
curl -L --progress-bar -o output.tar.gz https://example.com/file.tar.gz

# Secure copy between hosts
scp user@remote:/path/to/file .

# Sync a directory (dry run first)
rsync -avhn /local/dir/ user@remote:/remote/dir/
rsync -avh  /local/dir/ user@remote:/remote/dir/
```

---

## Podman and Containers

Podman is the daemonless, rootless OCI runtime on RHEL. Most Docker commands
translate directly — just swap the binary name.

### Basic Workflow

```bash
# Pull an image
podman pull registry.access.redhat.com/ubi9/ubi:latest

# Run interactively and remove on exit
podman run -it --rm ubi9/ubi bash

# Run a detached web server
podman run -d --name webserver -p 8080:80 nginx:alpine

# List running containers
podman ps

# All containers including stopped
podman ps -a

# Stream logs
podman logs -f webserver

# Stop and remove
podman stop webserver && podman rm webserver
```

### Rootless Podman Tips

```bash
# Check your user namespace mapping
podman info | grep -A5 "idMappings"

# Expose a privileged port without root (RHEL 9+)
sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80

# Persist it across reboots
echo "net.ipv4.ip_unprivileged_port_start=80" \
  | sudo tee /etc/sysctl.d/99-unprivileged-ports.conf
```

### Systemd Integration

```bash
# Generate a systemd unit from a running container
podman generate systemd --new --name webserver \
  > ~/.config/systemd/user/container-webserver.service

# Enable and start it as a user service
systemctl --user daemon-reload
systemctl --user enable --now container-webserver

# Check status
systemctl --user status container-webserver
```

---

## Shell Productivity

### Aliases Worth Having

Add these to `~/.bashrc`:

```bash
alias ll='ls -lah --color=auto'
alias grep='grep --color=auto'
alias vi='vim'
alias k='kubectl'

# Safety nets
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Quick navigation
alias ..='cd ..'
alias ...='cd ../..'
```

### History Tricks

```bash
# Search history interactively (Ctrl+R is faster)
history | grep podman

# Re-run the last command as root
sudo !!

# Run the last command that started with 'git'
!git

# Expand and edit before running (safe habit)
!git:p      # prints it; press Up then Enter to run
```

### Useful One-Liners

```bash
# Watch a command every 2 seconds
watch -n 2 'ss -tulnp | grep LISTEN'

# Repeat a command 10 times
for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080; done

# Extract any archive (alias this)
extract() {
  case "$1" in
    *.tar.gz|*.tgz)  tar xzf "$1" ;;
    *.tar.bz2)        tar xjf "$1" ;;
    *.tar.xz)         tar xJf "$1" ;;
    *.zip)            unzip "$1" ;;
    *.gz)             gunzip "$1" ;;
    *)                echo "Unknown format: $1" ;;
  esac
}
```
