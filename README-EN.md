
<p align="center">
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/releases">Download</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README.md">中文文档</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README-EN.md">English Documents</a>
</p>

- - -

## Project Introduction

> BrowserUse Client Version

```
Detailed Introduction: Since there is no official client version and the provided web version has limited features that are not suitable for personal use scenarios, I developed this client version and added some extra functionalities. See the feature list for details.
```

> BrowserUse Official: https://github.com/browser-use/browser-use

## Feature List

### Basic BrowserUse Features

> 1. Task instruction definition and sending

> 2. Browser definition

> 3. User data directory specification

> 4. openai configuration

### Client Extended Features

> 1. Task Template Management: Support saving, loading, and setting Task instructions as default templates.

> 2. Screenshot support

> 3. File download support

> 4. Save data as Excel file (both tables and charts)

> 5. Export output directory: All automated operation files are output to a specific directory

### Client Basic Features

> 1. Configure openai directly in the client

> 2. Open config file (config.ini) in the client for viewing and direct modification (Remember to save and close after modifications to prevent write failures)

> 3. View log files

> 4. Display operation logs (key operations) in the client

> 5. List and open saved files in client; locate their directories with one click

> 6. Support stopping agent execution: The agent will finish its current task before stopping, so this might take a while.

> 7. Support Force Quit: If you don't want to wait, use Force Quit; a confirmation dialog will be shown to prevent data loss if you forgot to save templates.

> 8. Support for both Chinese and English UI

> 9. Support enterprise environments: Prevents openai key from leaking, but you must download the source code, modify and package it yourself—see Secondary Development Guide.

## Usage Instructions

### Program Execution

> Executable file: dist/exe.win-amd64-3.10/main.exe

> If you want to relocate the directory, you must copy the entire 'dist' directory.

## Related Technologies

> Python version: 3.11.10 (official requirement >= 3.11)

> Core: browser-use

> GUI: tkinter

> Packaging: cx_Freeze

### Directory Structure

```
BrowserUse/
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

Architecture Description:
- `actions.py`: AI capability extension action implementations.
- `OpenAITool.py`: OpenAI integration tool.
- `ConfigTool.py`: Configuration file (config.ini) management tool.
- `localization.py`: JSON file manager for the locales directory.
- `main.py`: Main application entry point.
- `setup.py`: Packaging script for the application.
- `requirements.txt`: Lists all required dependencies.
- `README.md`: Project documentation (in Chinese).
- `resources`: Static resources directory.

## Installation

### 1. Enter Project Directory
```sh
cd BrowserUse
```

### 3. Install dependencies
```sh
pip install -r requirements.txt
```

### 4. Run the program
```sh
python -u main.py
```

### 5. Package as exe
```sh
python setup.py build

# Package as msi
# python setup.py bdist_msi
```

## Secondary Development Notes

### Enterprise Environment Support

> Currently, the system checks if it can connect to an internal enterprise service to determine the environment. Modify as needed for special cases.

```
1. In Enterprise environments, fill in the openai key and base url in ConfigTool.py; do NOT configure these in config.ini.
2. In main.py, change USER_TYPE to Enterprise, and set ENTERPRISE_NETWORK_CHECK_HOST and ENTERPRISE_NETWORK_CHECK_PORT to the internal service’s IP and port.
```

---
