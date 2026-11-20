#!/usr/bin/env bash
# Test every route through the Ingress.
#   ./scripts/test.sh                 # uses /etc/hosts (or DNS) for the names
#   INGRESS_IP=192.168.122.41 ./scripts/test.sh   # works without /etc/hosts (curl --resolve)
set -uo pipefail
IP="${INGRESS_IP:-}"
WWW=www.id-581.com
ADMIN=admin.id-581.com

c() {  # c <host> <path> [curl args...]
  local host=$1 path=$2; shift 2
  if [ -n "$IP" ]; then curl -s --resolve "$host:80:$IP" "$@" "http://$host$path"
  else curl -s "$@" "http://$host$path"; fi
}
show() { printf '\n\033[1;34m### %s\033[0m\n' "$*"; }
pod() { grep -o 'pod <code>[^<]*' | sed 's/pod <code>/pod: /'; }

show "1) http://$WWW/  (landing, app-about)"
c $WWW / -o /dev/null -w "HTTP %{http_code}\n"; c $WWW / | pod

show "2) http://$WWW/about  (app-about)"
c $WWW /about -o /dev/null -w "HTTP %{http_code}\n"
c $WWW /about | grep -oE '<h1>[^<]*</h1>|ID [0-9]+' | sed 's/<[^>]*>//g'
c $WWW /about | pod
c $WWW /about/photo.jpg -o /dev/null -w "photo.jpg -> HTTP %{http_code}, %{content_type}, %{size_download} bytes\n"

show "3) http://$WWW/research  (app-research)"
c $WWW /research -o /dev/null -w "HTTP %{http_code}\n"
c $WWW /research | grep -oE '<h1>[^<]*</h1>|ประมาณ [0-9]+ คำ' | sed 's/<[^>]*>//g' | head -2
c $WWW /research | pod

show "4) http://$WWW/api/<text>  (app-api)"
for t in "Hello%20Kubernetes" "%E0%B8%AA%E0%B8%A7%E0%B8%B1%E0%B8%AA%E0%B8%94%E0%B8%B5" "id-581"; do
  c $WWW "/api/$t" | grep -oE '<h1>[^<]*</h1>|pod <code>[^<]*' | sed 's/<[^>]*>//g; s/pod <code>/   pod: /'
done

show "5) http://$ADMIN/  (app-research /edit)"
c $ADMIN / -o /dev/null -w "HTTP %{http_code}\n"
c $ADMIN / | grep -oE '<h1>[^<]*</h1>|<textarea' | sed 's/<h1>//; s/<\/h1>//' | head -2

show "6) load balancing: 6 requests to /api/lb"
for i in $(seq 1 6); do c $WWW /api/lb | grep -o 'pod <code>[^<]*' | sed 's/pod <code>/pod: /'; done | sort | uniq -c

show "7) not routed -> 404"
c $WWW /nothing-here -o /dev/null -w "www /nothing-here -> HTTP %{http_code}\n"
