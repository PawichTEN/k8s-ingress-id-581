#!/usr/bin/env bash
# Deploy the K8s Ingress lab for id-581 (run on k8s-control from the repo folder).
#   ./deploy.sh
# Steps:
#   1. install ingress-nginx (baremetal manifest) if it is not installed yet
#   2. expose it with MetalLB as LoadBalancer 192.168.122.41
#   3. kubectl apply -k .   (namespace, ConfigMaps, PV/PVC, Deployments, Services, Ingress)
#   4. wait for every Deployment and print the result
set -euo pipefail
cd "$(dirname "$0")"

NS=id-581
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-controller-v1.12.1}"
INGRESS_IP="${INGRESS_IP:-192.168.122.41}"

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

command -v kubectl >/dev/null || { echo "kubectl not found"; exit 1; }
kubectl get nodes >/dev/null || { echo "cannot reach the cluster"; exit 1; }

# ---------------------------------------------------------------- 1
step "1/4 ingress-nginx controller"
if kubectl get deploy -n ingress-nginx ingress-nginx-controller >/dev/null 2>&1; then
  echo "already installed: $(kubectl get deploy -n ingress-nginx ingress-nginx-controller \
        -o jsonpath='{.spec.template.spec.containers[0].image}')"
else
  kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VERSION}/deploy/static/provider/baremetal/deploy.yaml"
fi
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=300s
kubectl -n ingress-nginx wait --for=condition=complete job --all --timeout=180s || true

# ---------------------------------------------------------------- 2
step "2/4 expose ingress-nginx with MetalLB IP ${INGRESS_IP}"
if kubectl get ns metallb-system >/dev/null 2>&1; then
  kubectl apply -f ingress-controller/metallb-pool.yaml
  kubectl -n ingress-nginx patch svc ingress-nginx-controller --type merge -p \
    "{\"metadata\":{\"annotations\":{\"metallb.universe.tf/loadBalancerIPs\":\"${INGRESS_IP}\"}},\"spec\":{\"type\":\"LoadBalancer\",\"externalTrafficPolicy\":\"Cluster\"}}"
  for i in $(seq 1 30); do
    ip=$(kubectl -n ingress-nginx get svc ingress-nginx-controller -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
    [ -n "$ip" ] && break; sleep 2
  done
  echo "EXTERNAL-IP = ${ip:-<pending>}"
else
  echo "MetalLB is not installed -> keeping NodePort. Use http://<node-ip>:<nodeport>"
fi

# ---------------------------------------------------------------- 3
step "3/4 apply manifests (kubectl apply -k .)"
kubectl apply -k .
# ConfigMaps keep fixed names, so restart Pods to pick up changed files
kubectl -n "$NS" rollout restart deploy/app-about deploy/app-api deploy/app-research >/dev/null

# ---------------------------------------------------------------- 4
step "4/4 wait for Deployments"
for d in app-about app-research app-api; do
  kubectl -n "$NS" rollout status deploy/"$d" --timeout=300s
done

step "result"
kubectl -n ingress-nginx get svc ingress-nginx-controller
kubectl -n "$NS" get deploy,pods,svc,pvc -o wide
kubectl -n "$NS" get ingress

cat <<EOF

Add to /etc/hosts (Linux) or C:\\Windows\\System32\\drivers\\etc\\hosts (Windows):
  ${INGRESS_IP}  www.id-581.com
  ${INGRESS_IP}  admin.id-581.com

Then open:
  http://www.id-581.com/about
  http://www.id-581.com/research
  http://www.id-581.com/api/สวัสดี
  http://admin.id-581.com/
Or run:  ./scripts/test.sh
EOF
