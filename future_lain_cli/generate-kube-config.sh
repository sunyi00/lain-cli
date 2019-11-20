#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'


server=$(cat ~/.kube/config | grep -o -P "(?<=server: ).+")
# the name of the secret containing the service account token goes here
token_name=$(kubectl describe sa default | grep -o -P "(?<=Mountable secrets:).+" | awk '{$1=$1};1')

ca=$(kubectl get secret/$token_name -o jsonpath='{.data.ca\.crt}')
token=$(kubectl get secret/$token_name -o jsonpath='{.data.token}' | base64 --decode)
namespace=$(kubectl get secret/$token_name -o jsonpath='{.data.namespace}' | base64 --decode)

cat > rbac.yml << EOF
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: default
rules:
- apiGroups:
  - ""
  resources:
  - events
  verbs:
  - list
  - get
- apiGroups:
  - ""
  - "apps"
  - "batch"
  - "networking.k8s.io"
  - "extensions"
  resources:
  - jobs
  - secrets
  - services
  - deployments
  - pods
  - pods/log
  - pods/exec
  - replicasets
  - cronjobs
  - ingresses
  verbs:
  - list
  - get
  - create
  - patch
  - update
  - delete
---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: default
subjects:
- kind: ServiceAccount
  name: default
  namespace: default
EOF

kubectl apply -f rbac.yml > /dev/null

echo "---
apiVersion: v1
kind: Config
clusters:
- name: default-cluster
  cluster:
    certificate-authority-data: ${ca}
    server: ${server}
contexts:
- name: default-context
  context:
    cluster: default-cluster
    namespace: default
    user: default-user
current-context: default-context
users:
- name: default-user
  user:
    token: ${token}
"
