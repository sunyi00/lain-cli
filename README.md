## 设计概要

## 迁移流程

* lain init 将会生成 example helm chart, 如果调用的时候提供了 --lain-yaml, 则会从给定的 lain.yaml 里翻译. 并且用 helm lint 检查生成的 chart/values.yaml
* lain*.yaml 在迁移完成以后, 可以删除, chart/values.yaml 里包含 lain build 等命令所需要的信息

## 云平台功能

* lain deploy 的功能将会由 helm 来实现, 将会 subprocess 里调用 helm, 如果缺少可执行文件或者版本不符合要求, 将会从阿里云 oss 上下载
* 容器管理等功能由 kubectl 来实现, 因此在使用 lain4 cli 的过程中也会不断打印常见操作, 提示用户接下来应该用什么工具做什么事情
* lain secret 封装了 Kubernetes Secret, 为 lain4 提供 secretfile 和 env 管理, 同时向后兼容 legacy_lain 的参数

## 兼容性

* lain3 cli 保持原有功能, 但是 entrypoint 改为 legacy_lain
* lain4 cli 的 entrypoint 仍然叫做 lain, 并且将会尽量保持命令行参数向后兼容
* lain*.yaml 可以用来翻译成 chart/values.yaml, 后者和 lain.yaml 的交集部分仍然是合法的 lain.yaml, 在 lain4 里, values.yaml 会用来做 lain build / tag / push

## 运维

### 生成 kubeconfig

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
