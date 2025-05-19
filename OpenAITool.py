# -*- coding:utf-8 -*-
# @Time: 2025/5/15 0015 14:57
# @Author: cxd
# @File: OpenAITool.py
# @Remark:
from openai import OpenAI


class OpenAITool:

    def call_gpt_api(self, user_content: str,
                     system_prompt: str = "",
                     model: str = "gpt-4.1",  # Default model, can be overridden by action params
                     max_tokens: int = 1024,
                     vision_images: list = None):
        if OpenAI is None:
            raise RuntimeError("openai 包未安装，无法调用LLM。pip install openai")
        client = OpenAI()  # Assumes OPENAI_API_KEY and BASE_URL are set in environment
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content_to_send = []
        if vision_images:  # Vision expects specific format
            for img_data in vision_images:
                content_to_send.append(
                    img_data)  # e.g., {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            if user_content:  # If there's also text prompt for vision
                content_to_send.append({"type": "text", "text": user_content})
            messages.append({"role": "user", "content": content_to_send})
        else:  # Text-only
            messages.append({"role": "user", "content": user_content})

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
        )
        return completion.choices[0].message.content.strip()