# 上传到GitHub的操作说明

本文件夹已经按GitHub仓库结构整理并初始化为本地`main`仓库，但尚未提交或上传。推荐将源码仓库和Windows安装包分两步上传。

Windows安装包已单独放在与本文件夹同级的`RoC_Workflow_GitHub_Release_Asset`文件夹中，因此源码文件夹内不再包含超过25 MB的文件。

## 第一步：创建源码仓库

在GitHub中新建空仓库，建议仓库名：

```text
Rates-of-Change-RoC-for-Deeptime-data
```

创建时不要让GitHub自动添加README、`.gitignore`或License，因为本文件夹已经包含。

### GitHub网页上传方式

1. 打开空仓库并选择 **Add file → Upload files**；
2. 打开本地`RoC_Workflow_GitHub_Ready`文件夹；
3. 选择该文件夹里面的所有项目拖入网页，不要拖入外层文件夹本身，避免仓库中多出一层`RoC_Workflow_GitHub_Ready`目录；
4. 不要选择隐藏的`.git`文件夹；
5. 等待文件列表加载完毕，提交说明填写`Initial release v1.0.1`；
6. 选择 **Commit changes**。

### GitHub Desktop方式

1. 选择 **File → Add local repository**；
2. 选择整个`RoC_Workflow_GitHub_Ready`文件夹；
3. 检查Changes列表；
4. 在Summary中填写`Initial release v1.0.1`并提交到`main`；
5. 选择 **Publish repository**，仓库名填写`Rates-of-Change-RoC-for-Deeptime-data`；
6. 如需公开发布，取消勾选 **Keep this code private**。

### 命令行方式

```bash
git add .
git commit -m "Initial release v1.0.1"
git remote add origin https://github.com/CUGB-zhaohy/Rates-of-Change-RoC-for-Deeptime-data.git
git push -u origin main
```

## 第二步：上传Windows安装包

`RoC_Workflow_GitHub_Release_Asset/RoC_Workflow_Windows_v1.0.1.zip`约158 MB，超过网页普通文件上传限制和普通Git文件100 MiB限制，因此不能放入源码仓库，需要作为GitHub Release附件上传。

上传方法：

1. 打开GitHub仓库；
2. 进入 **Releases**；
3. 选择 **Draft a new release**；
4. 新建标签`v1.0.1`；
5. 标题填写`Deeptime RoC Analysis v1.0.1`；
6. 将`RELEASE_NOTES_v1.0.1.md`内容复制到发布说明；
7. 从`RoC_Workflow_GitHub_Release_Asset`文件夹中把ZIP拖入附件区域；
8. 发布Release。

## 上传前检查

- Git提交中没有`venv`、`dist`、`outputs`、`.idea`、`.gui_runtime`或`.git`；
- Git提交中没有158 MB的ZIP；
- README首页能显示logo；
- 英文和中文手册链接可打开；
- GitHub页面显示“Cite this repository”；
- Release页面能下载Windows ZIP。
