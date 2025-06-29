<p align="center">
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/releases">Download</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README.md">中文文档</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README-EN.md">English Documents</a>
</p>

- - -

## 项目介绍

> BrowserUse客户端版

```
详细介绍：由于官方没有提供客户端版，而提供的网页端功能来说也比较简陋，不太符合个人使用场景， 
所以单独做了个客户端，并且扩展了一些功能，具体看功能介绍。
```

> BrowserUse官方：https://github.com/browser-use/browser-use

## 功能介绍

### BrowserUse基础功能

> 1. Task指令定义和发送

> 2. 浏览器定义

> 3. 用户数据目录指定

> 4. openai配置

### 客户端扩展功能

> 1. Task模板管理：支持Task指令保存为模板、加载模板和设为默认模板。

> 2. 支持截图功能

> 3. 支持下载文件功能

> 4. 支持数据保存为Excel功能（数据表和图表）

> 5. 支持输出文件：将自动化操作的文件都输出到一个目录里

> 6. 支持AI优化输入指令

### 客户端基础功能

> 1. 支持在客户端配置openai

> 2. 支持在客户端打开配置文件(config.ini)对其进行查看和直接修改（注意修改完要保存关闭配置文件，避免程序无法写入）

> 3. 支持查看日志文件

> 4. 支持在客户端展示操作日志（关键操作）

> 5. 支持在客户端展示保存的文件：可直接在客户端打开文件，可直接定位文件目录

> 7. 支持停止Agent运行：但需要等Task处理完它当前的任务才会停止，这个需要等待。

> 7. 支持强制退出程序：不想等待Agent停止，就使用该操作直接退出程序，会弹出确认框，避免用户模板忘记保存导致要重新输入。

> 8. 支持中英文双语

> 9. 支持企业环境使用：避免openai key泄露，但需要自行下载源码、修改代码和打包，具体看二次开发说明。

## 使用说明

### 程序运行

> 运行文件：dist/exe.win-amd64-3.10/main.exe

> 如需另行存放目录，需拷贝 'dist' 整个目录。

### 界面主要功能介绍

#### 主界面

![image](https://github.com/user-attachments/assets/5080439a-7142-498b-92cb-eed032c839d8)

#### 浏览器配置

![image](https://github.com/user-attachments/assets/fd496ab0-5a21-4452-96bc-cb68f6e1c7a6)

> 自定义Chrome路径：建议保持默认，用户自行填入或选择浏览器程序地址，默认可修改config.ini文件里的chrome_binary_path参数

> 使用内置Chromium：不建议使用，没有用户数据目录功能、任务完成后浏览器会直接关闭无法保持。

> 禁用网页安全：不建议取消，保持默认即可，避免某些网页功能影响BrowerUse读取和操作。

> 任务完成后保持浏览器活动：任务完成后保持浏览器当前活动页面，只有自定义Chrome有效。

> 用户数据目录：浏览器缓存数据目录，只有自定义Chrome有效。

#### 任务输入

![image](https://github.com/user-attachments/assets/530ae095-ad82-4e92-8d17-f9a1b0cbb6cb)

> 模板管理：可保存当前指令内容模板、加载历史保存的模板和设置当前的指令内容为默认模板

> 指定输入：可以按行方式输入指令任务流程，也可以使用文本结构化方式。

> 运行：操作“运行 Agent”。

#### 操作日志（关键事件）

![image](https://github.com/user-attachments/assets/27a53613-dcdc-42fd-bf5c-2de61faa96fa)

> 展示操作日志，但Agent操作过程不会展示，因为内容会很多，如需查看详细，直接在设置里面执行“查看日志文件”即可。

#### 已保存文件

![image](https://github.com/user-attachments/assets/0610f03f-983d-4dee-9e94-bdf6d435b03e)

> 任务过程中，保存的文件都会展示在里面

> 打开选定文件：选中展示的文件，直接打开

> 打开输出目录：选中展示的文件，直接进入文件所在目录。

#### 设置

![image](https://github.com/user-attachments/assets/70837d77-e2fa-4a14-85fb-91f08c78f098)

> 配置 OpenAI：配置openai相关信息，默认模型

> 查看配置文件：打开配置文件，可直接对其进行修改。

> 查看日志文件：查看整个程序运行的日志记录。

## 相关技术

> Python版本：3.11.10(官方要求>=3.11)

> 核心BrowserUse：browser-use

> GUI UI使用：tkinter

> 打包程序使用：cx_Freeze

### 目录结构

```
BrowserUse/
├── AISystemPrompt.py
├── LogTool.py
├── tool.py
├── actions.py
├── ConfigTool.py
├── OpenAITool.py
├── localization.py
├── config.ini
├── main.py
├── setup.py
├── requirements.txt
├── README.md
├── resources/
    ├──locales/
    ├──User Data/
    ├──task_template/
    ├──agent_outputs/
```

```

架构介绍：
- `AISystemPrompt.py`: 系统提示词定义。
- `LogTool.py`: 日志工具。
- `tool.py`: 工具集。
- `actions.py`: AI能力扩展action实现。
- `OpenAiTool`: openAI对接工具实现。
- `ConfigTool.py`: config.ini文件配置管理工具。
- `localization.py`: locales目录语言json文件管理工具。
- `main.py`: 主程序文件。
- `setup.py`: 用于打包应用程序的脚本。
- `requirements.txt`: 列出了所有依赖项。
- `README.md`: 项目的说明文档（中文）。
- `resources`: 静态资源目录。

```

## 安装说明

### 1. 进入项目目录
```sh
cd BrowserUse
```

### 3. 安装相关依赖
```sh
pip install -r requirements.txt
```

### 4. 运行文件
```sh
python -u main.py
```

### 5. 打包exe
```sh
python setup.py build

# 打包msi
# python setup.py bdist_msi
```

## 二次开发说明

### 企业环境支持

> 暂时采用判断是否能够连接到企业内部服务做环境判断，如有特殊场景，自行修改。

```
1. 企业环境在ConfigTool.py里面填写openai key和base url地址即可，不需在config.ini里配置。
2. 在main.py里面修改USER_TYPE为Enterprise，ENTERPRISE_NETWORK_CHECK_HOST和ENTERPRISE_NETWORK_CHECK_PORT改为企业服务的IP和端口。
```

## 问题处理

### 问题1：ImportError: DLL load failed while importing aggregations: 找不到指定的模块。

> 缺少 Microsoft Visual C++ Redistributable

> 安装或修复 VC 运行库：https://aka.ms/vs/17/release/vc_redist.x64.exe?spm=a2ty_o01.29997173.0.0.77e1c921kBdzS5&file=vc_redist.x64.exe

---
