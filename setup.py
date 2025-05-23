from cx_Freeze import setup, Executable
import os
from main import USER_TYPE
# 收集静态文件并保留目录结构
data_files = ['config.ini']
resources_dir = './resources'  # 静态资源目录

# --- 定义要排除的项 ---
# 1. 要完全排除的目录名 (os.walk 不会进入这些目录)
exclude_dirs = {'User Data','agent_outputs'}

# 2. 要排除的特定文件名
exclude_files = {}

# 3. 要排除的文件扩展名 (注意包含点号)
exclude_extensions = {}
# --- --- --- --- --- ---

for root, dirs, files in os.walk(resources_dir, topdown=True):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if file in exclude_files:
            continue  # 跳过这个文件

        file_name, file_ext = os.path.splitext(file)
        if file_ext.lower() in exclude_extensions: # 使用 lower() 保证大小写不敏感
            continue # 跳过这个文件
        source_path = os.path.join(root, file)
        relative_path = os.path.relpath(source_path, resources_dir)  # 获取相对路径（如 css/style.css）
        destination_root_in_package = os.path.basename(resources_dir)
        if not destination_root_in_package: # 处理 resources_dir = '.' 或 './' 的情况
            destination_root_in_package = 'resources' # 或者你希望的默认值

        destination_path = os.path.join(destination_root_in_package, relative_path)
        data_files.append((source_path, destination_path))
print(data_files)

name = "PBrowserUse" if USER_TYPE=="Personal" else "EBrowserUse"

executables = [
    Executable("main.py", base='Win32GUI', target_name=f"{name}.exe")  # GUI 应用需指定 base
]

# 设置默认安装目录
build_exe_options = {
    "zip_include_packages": [],
    "include_files": data_files,
    "includes": ["pydantic.deprecated", "pydantic.deprecated.decorator"]
}

bdist_msi_options = {
    "upgrade_code": "{c1f7238b-4b60-41d6-bfdf-0965418395c6}",  # 替换为你生成的 GUID
    "initial_target_dir": rf"[ProgramFilesFolder]\{name}"  # 默认安装目录
}

setup(
    name=f"{name}",
    version="1.0",
    description="BrowserUse客户端",
    options={
        'build_exe': build_exe_options,
        'bdist_msi': bdist_msi_options
    },
    executables=executables,
)