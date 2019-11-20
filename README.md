## Getting Started

lain cli 有着详细的 help message 以及命令行输出, 使用过程中注意阅读.

下边的示范以 public-api-docs 这个应用迁移到 future 集群为例.

```bash
# 安装 lain, 首先需要确保你在 python 3.7 下
pip install einplus_lain_cli>=4.0.0 -i https://pypi.in.ein.plus/root/ein/+simple/

# 对于 legacy_lain 应用, lain cli 提供了从 lain.yaml 翻译的功能, 由于 lain2 功能缺失, 所以一般不用 lain.yaml, 而是从 lain.poc.yaml, lain.azure.yaml 进行翻译
lain init --lain-yaml lain.poc.yaml
# 对于崭新的应用, 输出一份示范的 helm chart 就好
lain init

# 接下来按照 cli 的输出, review chart/values.yaml, 以及修改代码 (比如 .lain 域名的迁移之类的)

# 虽然 values.yaml 里边的注释也有讲到, 但是还是在这里提一下
# 如果你的应用需要公网域名, 则按照 chart/values.yaml 里的提示, 创建出 chart/values-future.yaml, 然后写成这样:
cat > chart/values-future.yaml << EOF
externalIngresses:
  - host: docs.einplus.cn
    # 你想把这个域名的流量打到哪个 deploy 上, 就在这里写哪个 deploy 的名称
    deployName: web
    paths:
      - /
EOF

# 改好了 values.yaml 以及代码以后, 如果需要重新构建镜像的话:
lain build
lain push

# 好像可以开始部署了, 那么先将 context 指向自己想要部署的集群
lain use future
# 部署过程会先用 legacy_lain 算出当前版本的镜像 tag, 如果该版本并没有构建, 也不用担心
# 命令行的 stderr 里贴心地帮你打印了最近构建出来的 release 镜像, 你可以直接选一个然后按照提示传参进行构建
lain deploy

# 部署过程如果不顺利, 按照 cli 的输出看一下 pod 的状态之类的吧, 如果自己不熟悉解决方法, 找 SA 哈
# 部署完成以后, 视情况可能要测一下内网域名访问是否通畅, 以及 cronjob 也许也要试跑一下, 这些 cli 输出里都有提示, 不赘述

# 如果需要公网访问, 则需要先通过 ingress controller 所在的节点访问一下, 看转发规则是不是真的生效了
# 先看看这个集群的 ingress controller 所在的节点
kubectl -n kube-system get po -l app=ingress -owide
# 再看看 ingress service 暴露出来的端口
k get svc --all-namespaces | ag nodeport
# 上边的信息里体现出 ingress controller 部署在 aws-future[4:5], http 端口为 31080
ssh aws-relay
# 为啥要费力登录进去才能测试请求呢, 因为安全组规则做的足够严格, 没法随便通过 vpn 请求到 ingress controller 节点
ssh aws-future4
curl 127.0.0.1:31080/api/v1/ -H 'Host: docs.einplus.cn'
# 请求成功则说明公网域名的转发规则在 ingress 这一层已经生效
# 可能还需要在 ingress controller 前的 gateway 之类的配一下域名转发规则才行, 详询 SA.

# lain*.yaml 在迁移完成以后, 可以删除, chart/values.yaml 里包含 lain build 等命令所需要的信息
```

## 云平台功能

* lain deploy 的功能将会由 helm 来实现, 将会 subprocess 里调用 helm, 如果缺少可执行文件或者版本不符合要求, 将会从阿里云 oss 上下载
* 容器管理等功能由 kubectl 来实现, 因此在使用 lain4 cli 的过程中也会不断打印常见操作, 提示用户接下来应该用什么工具做什么事情
* lain secret 封装了 Kubernetes Secret, 为 lain4 提供 secretfile 和 env 管理, 同时向后兼容 legacy_lain 的参数

## 兼容性

* lain3 cli 保持原有功能, 但是 entrypoint 改为 legacy_lain
* lain4 cli 的 entrypoint 仍然叫做 lain, 并且将会尽量保持命令行参数向后兼容
* lain*.yaml 可以用来翻译成 chart/values.yaml, 后者和 lain.yaml 的交集部分仍然是合法的 lain.yaml, 在 lain4 里, values.yaml 会用来做 lain build / tag / push

## 运维

### 生成小权限用户的 kubeconfig

helm3 需要通过 Kubernetes Apiserver 暴露出来的端口, 以及对应的一个小权限用户的 kubeconfig 与集群进行交互.

如需为当前的 namespace 下的 default 用户配置开发者权限, 可以用 `future_lain_cli/generate-kube-config.sh` 生成相应的 kubeconfig:

```bash
scp future_lain_cli/generate-kube-config.sh qcloud-relay:/jfs/lain
ssh qcloud-relay
ssh bei1
cd /jfs/lain
./generate-kube-config.sh > kubeconfig-bei
exit
scp qcloud-relay:/jfs/lain/kubeconfig-bei .
# 把该文件作为附件上传到 1pw 里的 kubeconfig 这一项目中
```

## 心路历程

* https://trello.com/c/hyr7pTnS/94-helm-%E8%BF%81%E7%A7%BB%E6%96%B9%E6%A1%88
