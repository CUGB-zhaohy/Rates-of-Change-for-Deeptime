# 上传到GitHub的操作说明

本文件夹已经按GitHub仓库结构整理并初始化为本地`main`仓库，但尚未提交或上传。推荐将源码仓库和Windows安装包分两步上传。

## 第一步：创建源码仓库

在GitHub中新建空仓库，建议仓库名：

```text
Rates-of-Change-RoC-for-Deeptime-data
```

创建时不要让GitHub自动添加README、`.gitignore`或License，因为本文件夹已经包含。

使用GitHub Desktop时：

1. 选择 **File → Add local repository**；
2. 选择整个`RoC_Workflow_GitHub_Ready`文件夹；
3. 检查Changes列表；
4. `release-assets/RoC_Workflow_Windows_v1.0.1.zip`不应出现在提交列表；
5. 在Summary中填写`Initial release v1.0.1`并提交到`main`；
6. 选择 **Publish repository**，仓库名填写`Rates-of-Change-RoC-for-Deeptime-data`；
7. 如需公开发布，取消勾选 **Keep this code private**。

命令行方式：

```bash
git add .
git commit -m "Initial release v1.0.1"
git remote add origin https://github.com/CUGB-zhaohy/Rates-of-Change-RoC-for-Deeptime-data.git
git push -u origin main
```

## 第二步：上传Windows安装包

`release-assets/RoC_Workflow_Windows_v1.0.1.zip`约158 MB，超过普通Git文件
100 MiB限制，因此已被`.gitignore`排除。

上传方法：

1. 打开GitHub仓库；
2. 进入 **Releases**；
3. 选择 **Draft a new release**；
4. 新建标签`v1.0.1`；
5. 标题填写`Deeptime RoC Analysis v1.0.1`；
6. 将`RELEASE_NOTES_v1.0.1.md`内容复制到发布说明；
7. 把ZIP拖入附件区域；
8. 发布Release。

## 上传前检查

- Git提交中没有`venv`、`dist`、`outputs`、`.idea`或`.gui_runtime`；
- Git提交中没有158 MB的ZIP；
- README首页能显示logo；
- 英文和中文手册链接可打开；
- GitHub页面显示“Cite this repository”；
- Release页面能下载Windows ZIP。
