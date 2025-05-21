
<p align="center">
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/releases">Download</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README.md">Chinese Documentation</a>
  ·
  <a href="https://github.com/yincangshiwei/BrowserUse-GUI/blob/master/README-EN.md">English Documents</a>
</p>

- - -

## Project Introduction

> BrowserUse Client Version

```
Detailed Description: Since the official version does not provide a client version, and the web-based functionality is quite basic, which does not meet personal usage scenarios,
I have created a separate client and expanded some features. For details, see the feature introduction.
```

> Official BrowserUse: https://github.com/browser-use/browser-use

## Feature Introduction

### Basic Features of BrowserUse

> 1. Task Instruction Definition and Sending

> 2. Browser Definition

> 3. User Data Directory Specification

> 4. OpenAI Configuration

### Extended Features of the Client

> 1. Task Template Management: Supports saving task instructions as templates, loading templates, and setting default templates.

> 2. Screenshot Functionality

> 3. File Download Functionality

> 4. Saving Data as Excel (Data Tables and Charts)

> 5. Output Files: Outputs all automated operation files to one directory.

### Basic Features of the Client

> 1. Configure OpenAI within the client

> 2. Open configuration file (config.ini) for viewing and direct modification within the client (note that after modification, save and close the configuration file to avoid program write errors).

> 3. View log files

> 4. Display operation logs (key events) within the client

> 5. Display saved files within the client: Can directly open files from the client and locate file directories

> 6. Stop Agent Operation: However, it will only stop after the current task is completed by the Task; this requires waiting.

> 7. Force Exit Program: If you do not want to wait for the Agent to stop, use this option to exit the program directly. A confirmation box will pop up to prevent loss of unsaved templates.

> 8. Support for bilingual Chinese and English

> 9. Support for enterprise environment usage: Avoids leaking OpenAI keys but requires downloading source code, modifying code, and packaging yourself. See secondary development instructions for details.

## Usage Instructions

### Running the Program

> Run file: dist/exe.win-amd64-3.10/main.exe

> If you need to store it in another directory, copy the entire 'dist' folder.

### Main Interface Functionalities

#### Main Interface

![image](https://github.com/user-attachments/assets/55b252a6-7625-4a72-ae27-afd6968eba76)

#### Browser Configuration

![image](https://github.com/user-attachments/assets/200e8637-68fa-40d4-afab-d35dff6f9138)

> Custom Chrome Path: It is recommended to keep the default. Enter or select the browser executable address manually. The default can be modified by changing the chrome_binary_path parameter in the config.ini file.

> Use Built-in Chromium: Not recommended. There is no user data directory function, and the browser will close directly after the task is complete without keeping it active.

> Disable Web Security: Not recommended. Keep the default to avoid affecting BrowserUse's reading and operations due to certain webpage functionalities.

> Keep Browser Active After Task Completion: Keeps the current active page of the browser after the task is complete. Only effective with custom Chrome.

> User Data Directory: Browser cache data directory. Only effective with custom Chrome.

#### Task Input

![image](https://github.com/user-attachments/assets/7782153f-91ae-454a-807b-a39e71d20981)

> Template Management: Save the current instruction content template, load historically saved templates, and set the current instruction content as the default template.

> Specify Input: You can input instruction tasks line-by-line or use structured text format.

> Run: Operate "Run Agent".

#### Operation Log (Key Events)

![image](https://github.com/user-attachments/assets/66cda241-a641-45f5-a1c9-d358da955a35)

> Displays operation logs, but agent operations are not shown during execution because there would be too much content. For detailed views, execute "View Log File" in settings.

#### Saved Files

![image](https://github.com/user-attachments/assets/6716cb3d-557c-4b79-9f1a-72ded6cb604e)

> All files saved during tasks will be displayed here.

> Open Selected File: Select the displayed file to open it directly.

> Open Output Directory: Select the displayed file to enter its directory directly.

#### Settings

![image](https://github.com/user-attachments/assets/94e95727-e6f4-4f3e-bed5-96c62a93b85b)

> Configure OpenAI: Configure relevant OpenAI information, including the default model.

> View Configuration File: Opens the configuration file for direct modification.

> View Log File: Views the entire program's running logs.

## Related Technologies

> Python Version: 3.11.10 (official requirement >=3.11)

> Core BrowserUse: browser-use

> GUI UI Tool: tkinter

> Packaging Tool: cx_Freeze

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

```
Architecture Overview:
- `actions.py`: Implementation of extended AI capabilities.
- `OpenAiTool`: Implementation of tools for interfacing with OpenAI.
- `ConfigTool.py`: Tool for managing the config.ini file.
- `localization.py`: Tool for managing language JSON files in the locales directory.
- `main.py`: Main program file.
- `setup.py`: Script used for packaging the application.
- `requirements.txt`: Lists all dependencies.
- `README.md`: Project documentation (in Chinese).
- `resources`: Static resource directory.
```

## Installation Instructions

### 1. Navigate to the project directory
```sh
cd BrowserUse
```

### 3. Install related dependencies
```sh
pip install -r requirements.txt
```

### 4. Run the file
```sh
python -u main.py
```

### 5. Package exe
```sh
python setup.py build

# To package msi
# python setup.py bdist_msi
```

## Secondary Development Instructions

### Enterprise Environment Support

> Temporarily uses whether an internal service connection can be established to determine the environment. Modify if necessary for special cases.

```
1. Fill in the OpenAI key and base URL address in ConfigTool.py for enterprise environments; no need to configure in config.ini.
2. Modify USER_TYPE to Enterprise and ENTERPRISE_NETWORK_CHECK_HOST and ENTERPRISE_NETWORK_CHECK_PORT to the IP and port of your enterprise service in main.py.
```

---
