# Deeptime RoC Analysis 中文说明

Deeptime RoC Analysis 是用于不规则深时古气候和古环境记录的多时间尺度
变化速率（RoC）分析软件。仓库同时提供Python源码和带图形界面的Windows
独立程序。当前版本为 **v1.0.1**。

## 主要功能

- 时间窗口与滑动步长设置；
- 距离—样本数加权插值；
- IBR、Theil-Sen和IQR计算；
- 多时间尺度结果合并；
- LRI尺度效应分析和校正；
- nTV和Gini评价；
- PWLF断点识别；
- 分方法KDE共识边界；
- 阶段统计及图表输出。

其中IBR和TS属于显式包含时间的RoC估计方法，IQR用于表示窗口内部变异，
不应解释为传统意义上的变化速率。论文中的采样密度敏感性实验目前为独立
分析模块，尚未纳入v1.0.1主GUI流程。

## Windows程序

在GitHub仓库的 **Releases** 页面下载
`RoC_Workflow_Windows_v1.0.1.zip`。解压后不要移动单个exe或删除
`_internal`目录，双击`RoC_Workflow.exe`即可运行，无需安装Python。

GUI包含五个页面：输入数据、RoC设置、高级分析、运行与日志、结果预览。
完整操作见[中文使用手册](docs/Deeptime%20RoC%20Analysis%20使用手册.pdf)。

## 源码运行

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python main.py --config config_test.yaml --dry-run
python main.py --config config_test.yaml
```

启动图形界面：

```bash
python gui.py
```

Windows用户也可以双击`start_gui_windows.bat`。

## 输入格式

输入文件为Excel表格，至少包含：

- `Age`：年龄，单位为kyr；
- `Value`：连续型代用指标数值。

仓库中的`data/O.xlsx`为示例数据。正式运行前建议先执行dry run检查。

## 输出

软件会自动生成时间窗口、插值、三种方法结果、尺度合并、LRI校正、指标、
PWLF、KDE、阶段统计、图件和日志等分级目录。生成的`outputs/`不会提交到Git。

## 引用与许可

使用本软件时，请引用配套论文以及软件版本。引用信息见`CITATION.cff`。
软件采用[MIT许可证](LICENSE)。
