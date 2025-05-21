# -*- coding:utf-8 -*-
# @Time: 2025/4/11 0011 17:20
# @Author: cxd
# @File: GUIDGen.py
# @Remark:
import uuid

# 生成一个随机的 GUID
guid = uuid.uuid4()
print(f"{{ {guid} }}")  # 输出格式化后的 GUID