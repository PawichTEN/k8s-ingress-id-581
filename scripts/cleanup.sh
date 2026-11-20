#!/usr/bin/env bash
# Remove the lab (keeps ingress-nginx and MetalLB installed).
#   ./scripts/cleanup.sh
cd "$(dirname "$0")/.."
kubectl delete -k . --ignore-not-found
# The PV uses Retain, so the saved summary stays on k8s-worker2 in /srv/id-581/research
echo "Saved data (if any) is still on k8s-worker2: /srv/id-581/research/research.md"
