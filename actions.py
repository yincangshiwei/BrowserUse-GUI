# actions.py

import os
import re
import pandas as pd
import io
import traceback
import urllib.parse
import base64
from typing import Optional, List
from docx import Document
from pydantic import BaseModel, Field
from browser_use.agent.views import ActionResult
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Page
from OpenAITool import OpenAITool

openAITool = OpenAITool()
import pdfplumber
import logging


# --------------------- Pydantic 参数模型 ---------------------
class ExcelWithChartParams(BaseModel):
    data_csv_string: str = Field(...,
                                 description="CSV格式的字符串，第一行必须是表头 (e.g., \"电影名称,上映年份,票房(亿)\\n霸王别姬,1993,1.5\")")
    file_path: str = Field(..., description="保存Excel文件的路径 (e.g., 'movie_stats.xlsx')")
    sheet_name: str = Field("Data", description="Excel中数据表的工作表名称")
    chart_title: str = Field(..., description="图表的标题")
    chart_type: str = Field(..., description="图表类型 ('bar', 'column', 'line', 'pie', etc.)")
    x_axis_column: str = Field(..., description="用作图表X轴的列名 (来自CSV表头)")
    y_axis_columns: List[str] = Field(..., description="一个或多个用作图表Y轴的列名 (来自CSV表头)")
    y_axis_label: Optional[str] = Field(None, description="Y轴的标签")
    x_axis_label: Optional[str] = Field(None, description="X轴的标签")
    aggregation_column: Optional[str] = Field(None,
                                              description="如果X轴是分类轴，Y轴需要聚合计算（如计数），则指定此列进行聚合。")
    aggregation_type: Optional[str] = Field("count",
                                            description="聚合类型 ('count', 'sum', 'average')。仅当 aggregation_column 指定时有效。")


class ScreenshotParams(BaseModel):
    file_path: str = Field(..., description="截图保存的文件名 (例如: 'screenshot.png')。")
    full_page: bool = Field(False, description="是否截取整个可滚动页面，默认为 False (仅当前视口)。")


class DownloadFileParams(BaseModel):
    url: str = Field(..., description="要下载的文件的URL。")
    file_name: Optional[str] = Field(None,
                                     description="保存文件的文件名 (含后缀, e.g., 'document.pdf', 'archive.zip')。如果未提供，将尝试从URL或HTTP响应头派生。")


class ScreenshotElementParams(BaseModel):
    selector: str = Field(..., description="用于定位元素的CSS选择器。")
    file_path: str = Field(..., description="截图保存的文件名 (例如 'element_screenshot.png')。")
    timeout: Optional[int] = Field(30000, description="等待元素出现的最长时间（毫秒）。")


class ImageOCRParams(BaseModel):
    file_name: str = Field(..., description="要识别的图片文件名（仅文件名，如 'myimg.png'），从 output_dir 下读取。")
    system_prompt: Optional[str] = Field("你是图片内容识别专家，只告诉我图片里是什么内容，不要输出多余解释。",
                                         description="用于图片识别的 system prompt")


class PDFOCRParams(BaseModel):
    file_name: str = Field(..., description="要识别的PDF文件名（仅文件名，如 'my.pdf'），从 output_dir 下读取。")
    max_pages: Optional[int] = Field(5, description="最多解析前多少页。")
    max_chars: Optional[int] = Field(3000, description="最多发送给LLM的字符数（防止长文溢出）。")
    system_prompt: Optional[str] = Field("你是PDF内容识别专家，只输出PDF文件所包含的主要内容，不要解释。",
                                         description="识别时采用的指令。")


# --------------------- 统一注册函数 ---------------------
def register_actions(controller, gui_feedback_queue, initial_output_dir_param, file_logger: logging.Logger, config):
    def _get_effective_output_dir() -> str:
        current_gui_dir = getattr(controller, 'current_output_dir_from_gui', None)
        if current_gui_dir and os.path.isdir(current_gui_dir):
            return current_gui_dir
        os.makedirs(initial_output_dir_param, exist_ok=True)
        return initial_output_dir_param

    def _prepare_output_path(file_path_param: str) -> str:
        path = file_path_param
        effective_output_dir = _get_effective_output_dir()
        if not os.path.isabs(path):
            path = os.path.join(effective_output_dir, os.path.basename(path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if gui_feedback_queue is not None:
            gui_feedback_queue.put({"type": "file_saved", "path": os.path.abspath(path)})
        file_logger.debug(f"Prepared output path: {os.path.abspath(path)}")
        return os.path.abspath(path)

    def _ensure_overwrite(file_path: str):
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                msg = f"Removed existing file: {os.path.basename(file_path)}"
                if gui_feedback_queue is not None:
                    gui_feedback_queue.put({"type": "log", "message": msg, "level": "INFO_GUI"})
                file_logger.info(f"Removed existing file: {file_path}")
            except Exception as e_remove:
                msg = f"Could not remove existing file {os.path.basename(file_path)}: {e_remove}"
                if gui_feedback_queue is not None:
                    gui_feedback_queue.put(
                        {"type": "log", "message": f"WARNING: {msg}", "level": "WARNING_GUI"})
                file_logger.warning(f"Could not remove existing file {file_path}: {e_remove}")

    # --------- save_to_file ----------
    @controller.registry.action('save_to_file')
    def save_to_file(text: str, file_path: str):
        action_name = "save_to_file"
        final_file_path = ""
        try:
            base_output_path = _prepare_output_path(file_path)
            sanitized_filename = os.path.basename(base_output_path)
            base, ext = os.path.splitext(sanitized_filename)
            ext = ext.lower()

            if ext == '.xlsx':
                final_file_path = os.path.join(os.path.dirname(base_output_path), base + ".xlsx")
                _ensure_overwrite(final_file_path)
                lines = text.strip().split('\n')
                data = [line.split(',') for line in lines if line.strip()]
                df = pd.DataFrame(data)
                df.to_excel(final_file_path, index=False, header=False)
                msg_summary = f"Data saved to Excel: {os.path.basename(final_file_path)}"
                msg_detail = f"Data saved to Excel (no chart): {final_file_path}"
            elif ext == '.docx':
                final_file_path = os.path.join(os.path.dirname(base_output_path), base + ".docx")
                _ensure_overwrite(final_file_path)
                doc = Document()
                doc.add_paragraph(text)
                doc.save(final_file_path)
                msg_summary = f"Text saved to Word: {os.path.basename(final_file_path)}"
                msg_detail = f"Text saved to Word document: {final_file_path}"
            else:
                final_ext = ext if ext in ['.txt', '.md', '.json', '.csv'] else ".txt"
                final_file_path = os.path.join(os.path.dirname(base_output_path), base + final_ext)
                _ensure_overwrite(final_file_path)
                with open(final_file_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                msg_summary = f"Text saved to file: {os.path.basename(final_file_path)}"
                msg_detail = f"Text saved to file: {final_file_path}"

            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: {msg_detail}. Input file_path param: '{file_path}'")
            return ActionResult(extracted_content=msg_detail)
        except Exception as e:
            error_msg_summary = f"Failed to save file '{file_path}': {str(e)[:100]}"
            error_msg_detail = f"Failed to save file '{file_path}' (final: {final_file_path or 'unknown'}): {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {error_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {error_msg_detail}\n{tb_full}. Input file_path param: '{file_path}'")
            return ActionResult(error_message=error_msg_detail)

    # --------- save_data_to_excel_with_chart ----------
    @controller.registry.action('save_data_to_excel_with_chart', param_model=ExcelWithChartParams)
    def save_data_to_excel_with_chart(params: ExcelWithChartParams):
        action_name = "save_data_to_excel_with_chart"
        final_file_path = ""
        try:
            final_file_path = _prepare_output_path(params.file_path)
            _ensure_overwrite(final_file_path)
            params_for_log = params.model_dump(exclude={'data_csv_string'})
            file_logger.debug(f"Executing {action_name} with params: {params_for_log}")
            if len(params.data_csv_string) > 500:
                file_logger.debug(f"Data CSV string (partial for {action_name}): {params.data_csv_string[:500]}...")
            else:
                file_logger.debug(f"Data CSV string (full for {action_name}): {params.data_csv_string}")

            csv_data = io.StringIO(params.data_csv_string)
            df = pd.read_csv(csv_data)

            required_cols_in_df = {params.x_axis_column}
            for y_col in params.y_axis_columns: required_cols_in_df.add(y_col)
            if params.aggregation_column: required_cols_in_df.add(params.aggregation_column)

            missing_cols = [col for col in required_cols_in_df if col not in df.columns]
            if missing_cols:
                err_msg = f"Column(s) {missing_cols} not found in CSV data. Available: {df.columns.tolist()}"
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {err_msg}", "level": "ERROR_GUI"})
                file_logger.error(f"ERROR in {action_name}: {err_msg}. Params: {params_for_log}")
                return ActionResult(error_message=err_msg)

            writer = pd.ExcelWriter(final_file_path, engine='xlsxwriter')
            chart_df = df.copy()
            y_axis_cols_for_chart = params.y_axis_columns[:]

            if params.aggregation_column:
                file_logger.info(
                    f"{action_name}: Performing aggregation '{params.aggregation_type}' on '{params.aggregation_column}' grouped by '{params.x_axis_column}'.")
                if params.aggregation_type == 'count':
                    chart_df = df.groupby(params.x_axis_column, as_index=False)[params.aggregation_column].count()
                    y_axis_cols_for_chart = [params.aggregation_column]
                elif params.aggregation_type in ['sum', 'average']:
                    numeric_cols_for_agg = [col for col in y_axis_cols_for_chart if
                                            pd.api.types.is_numeric_dtype(df[col])]
                    if not numeric_cols_for_agg:
                        err_msg = f"For aggregation '{params.aggregation_type}', Y-axis columns must include numeric types. Y-axis: {y_axis_cols_for_chart}"
                        if gui_feedback_queue: gui_feedback_queue.put(
                            {"type": "log", "message": f"ERROR ({action_name}): {err_msg}", "level": "ERROR_GUI"})
                        file_logger.error(f"ERROR in {action_name}: {err_msg}. Params: {params_for_log}")
                        return ActionResult(error_message=err_msg)
                    agg_func = 'sum' if params.aggregation_type == 'sum' else 'mean'
                    chart_df = df.groupby(params.x_axis_column, as_index=False)[numeric_cols_for_agg].agg(agg_func)
                    y_axis_cols_for_chart = numeric_cols_for_agg
                else:
                    err_msg = f"Unsupported aggregation type: {params.aggregation_type}"
                    if gui_feedback_queue: gui_feedback_queue.put(
                        {"type": "log", "message": f"ERROR ({action_name}): {err_msg}", "level": "ERROR_GUI"})
                    file_logger.error(f"ERROR in {action_name}: {err_msg}. Params: {params_for_log}")
                    return ActionResult(error_message=err_msg)

            chart_df.to_excel(writer, sheet_name=params.sheet_name, index=False)
            workbook = writer.book
            worksheet = writer.sheets[params.sheet_name]
            chart = workbook.add_chart({'type': params.chart_type})

            if params.x_axis_column not in chart_df.columns:
                err_msg = f"X-axis column '{params.x_axis_column}' surprisingly not in chart data. Columns: {chart_df.columns.tolist()}"
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {err_msg}", "level": "ERROR_GUI"})
                file_logger.error(
                    f"CRITICAL ERROR in {action_name}: {err_msg}. Params: {params_for_log}. Chart DF: \n{chart_df.head()}")
                return ActionResult(error_message=err_msg)
            x_col_idx_chart = chart_df.columns.get_loc(params.x_axis_column)

            for y_col_name in y_axis_cols_for_chart:
                if y_col_name not in chart_df.columns:
                    err_msg = f"Y-axis column '{y_col_name}' not found in chart data. Columns: {chart_df.columns.tolist()}"
                    if gui_feedback_queue: gui_feedback_queue.put(
                        {"type": "log", "message": f"ERROR ({action_name}): {err_msg}", "level": "ERROR_GUI"})
                    file_logger.error(
                        f"CRITICAL ERROR in {action_name}: {err_msg}. Y-axis was supposed to be {y_axis_cols_for_chart}. Params: {params_for_log}. Chart DF: \n{chart_df.head()}")
                    return ActionResult(error_message=err_msg)
                y_col_idx_chart = chart_df.columns.get_loc(y_col_name)
                chart.add_series({
                    'name': f"={params.sheet_name}!${chr(ord('A') + y_col_idx_chart)}$1",
                    'categories': f"={params.sheet_name}!${chr(ord('A') + x_col_idx_chart)}$2:${chr(ord('A') + x_col_idx_chart)}${len(chart_df) + 1}",
                    'values': f"={params.sheet_name}!${chr(ord('A') + y_col_idx_chart)}$2:${chr(ord('A') + y_col_idx_chart)}${len(chart_df) + 1}",
                })
            chart.set_title({'name': params.chart_title})
            chart.set_x_axis({'name': params.x_axis_label or params.x_axis_column})
            chart.set_y_axis({'name': params.y_axis_label or (
                y_axis_cols_for_chart[0] if len(y_axis_cols_for_chart) == 1 else 'Values')})
            num_data_cols = len(chart_df.columns)
            chart_start_col_letter = chr(ord('A') + num_data_cols + 1)
            worksheet.insert_chart(f'{chart_start_col_letter}2', chart)
            writer.close()
            msg_summary = f"Excel with chart saved: {os.path.basename(final_file_path)}"
            msg_detail = f"Data and chart saved to Excel: {final_file_path}"
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: {msg_detail}. Params: {params_for_log}")
            return ActionResult(extracted_content=msg_detail)
        except pd.errors.EmptyDataError:
            err_msg_summary = "CSV data is empty or badly formatted."
            err_msg_detail = f"CSV data empty or malformed. CSV sample: {params.data_csv_string[:200]}..."
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {err_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {err_msg_detail}. Params: params_for_log")  # Use params_for_log if defined
            return ActionResult(error_message=err_msg_detail)
        except Exception as e:
            error_msg_summary = f"Failed to save Excel with chart '{params.file_path}': {str(e)[:100]}"
            error_msg_detail = f"Failed to save Excel with chart '{final_file_path or params.file_path}': {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {error_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {error_msg_detail}\n{tb_full}. Params: {params_for_log if 'params_for_log' in locals() else params.model_dump(exclude={'data_csv_string'})}")
            return ActionResult(error_message=error_msg_detail)

    # --------- take_screenshot_action ----------
    @controller.registry.action("take_screenshot_action", param_model=ScreenshotParams)
    async def take_screenshot_action_with_context(params: ScreenshotParams, browser):
        action_name = "take_screenshot_action"
        output_file_path = ""
        try:
            current_page = await browser.get_current_page()
            if not current_page:
                msg = "Browser page not available for screenshot."
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
                file_logger.error(f"ERROR in {action_name}: {msg}. Params: {params.model_dump_json()}")
                return ActionResult(error_message=msg)

            output_file_path = _prepare_output_path(params.file_path)
            _ensure_overwrite(output_file_path)

            await current_page.screenshot(path=output_file_path, full_page=params.full_page)
            msg_summary = f"Screenshot saved: {os.path.basename(output_file_path)}"
            msg_detail = f"Screenshot saved to: {output_file_path}"
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: {msg_detail}. Params: {params.model_dump_json()}")
            return ActionResult(extracted_content=msg_detail)
        except Exception as e:
            error_msg_summary = f"Screenshot failed for '{params.file_path}': {str(e)[:100]}"
            error_msg_detail = f"Screenshot failed for '{params.file_path}': {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {error_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {error_msg_detail}\n{tb_full}. Output path: {output_file_path}. Params: {params.model_dump_json()}")
            return ActionResult(error_message=error_msg_detail)

    @controller.registry.action("download_file", param_model=DownloadFileParams)
    async def download_file_action(params: DownloadFileParams, browser):
        action_name = "download_file"
        output_file_path = ""
        absolute_url = ""
        try:
            current_page: Optional[Page] = await browser.get_current_page()
            if not current_page:
                msg = "Browser page not available for file download."
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
                file_logger.error(f"ERROR in {action_name}: {msg}. Params: {params.model_dump_json()}")
                return ActionResult(error_message=msg)

            absolute_url = urllib.parse.urljoin(current_page.url, params.url)
            file_logger.info(f"Attempting to download file from URL: {absolute_url}")

            api_request_context = current_page.context.request
            response = await api_request_context.get(absolute_url)

            if not response.ok:
                msg_summary = f"Failed to download file (HTTP {response.status})."
                msg_detail = f"Failed to download file: URL {absolute_url} returned status {response.status}"
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg_summary}", "level": "ERROR_GUI"})
                file_logger.error(f"ERROR in {action_name}: {msg_detail}. Params: {params.model_dump_json()}")
                return ActionResult(error_message=msg_detail)

            # Determine filename
            final_filename_to_use = params.file_name
            server_suggested_filename = None
            content_disposition_header = response.headers.get('content-disposition')

            if content_disposition_header:
                file_logger.debug(f"Content-Disposition header: {content_disposition_header}")
                # Try filename*=UTF-8''...
                match_star_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition_header, re.IGNORECASE)
                if match_star_utf8:
                    encoded_name = match_star_utf8.group(1).strip()
                    try:
                        server_suggested_filename = urllib.parse.unquote(encoded_name)
                        file_logger.debug(f"Filename from filename*=UTF-8'' (decoded): {server_suggested_filename}")
                    except Exception as e:
                        file_logger.warning(
                            f"Failed to decode UTF-8 filename* '{encoded_name}': {e}. Original header: {content_disposition_header}")
                        server_suggested_filename = None  # Fallback if decoding fails

                if not server_suggested_filename:
                    # Fallback to filename="filename.ext"
                    match_quoted = re.search(r'filename="([^"]+)"', content_disposition_header, re.IGNORECASE)
                    if match_quoted:
                        server_suggested_filename = match_quoted.group(1).strip()
                        file_logger.debug(f"Filename from filename=\"...\" : {server_suggested_filename}")

                if not server_suggested_filename:
                    # Fallback to filename=filename.ext (unquoted)
                    match_unquoted = re.search(r'filename=([^;"]+)', content_disposition_header, re.IGNORECASE)
                    if match_unquoted:
                        potential_filename = match_unquoted.group(1).strip()
                        # Avoid picking up part of filename*= if the UTF-8 part failed but left a generic filename=... afterwards
                        if "''" not in potential_filename:
                            server_suggested_filename = potential_filename
                            file_logger.debug(f"Filename from filename= (unquoted): {server_suggested_filename}")

            if server_suggested_filename:
                # Sanitize
                server_suggested_filename = os.path.basename(server_suggested_filename)  # Remove path components
                server_suggested_filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_',
                                                   server_suggested_filename)  # remove invalid chars
                server_suggested_filename = server_suggested_filename.strip(' .')  # remove leading/trailing dots/spaces
                if not server_suggested_filename:  # If sanitization results in empty string
                    server_suggested_filename = None
                    file_logger.debug("Sanitized server_suggested_filename was empty.")
                else:
                    file_logger.debug(f"Sanitized server_suggested_filename: {server_suggested_filename}")
            else:
                file_logger.debug("No server_suggested_filename could be derived from Content-Disposition.")

            if final_filename_to_use:
                name_part, ext_part = os.path.splitext(final_filename_to_use)
                if not ext_part:
                    derived_ext = None
                    if server_suggested_filename:
                        _, derived_ext = os.path.splitext(server_suggested_filename)

                    if not derived_ext:
                        _, derived_ext = os.path.splitext(os.path.basename(urllib.parse.urlparse(absolute_url).path))

                    if derived_ext and len(derived_ext) > 1 and len(derived_ext) <= 10:
                        final_filename_to_use += derived_ext
            else:
                if server_suggested_filename:
                    final_filename_to_use = server_suggested_filename
                else:
                    parsed_url_path_basename = os.path.basename(urllib.parse.urlparse(absolute_url).path)
                    if parsed_url_path_basename:
                        final_filename_to_use = parsed_url_path_basename
                    else:
                        final_filename_to_use = "downloaded_file"

                    name_part, ext_part = os.path.splitext(final_filename_to_use)
                    if not ext_part:
                        _, url_ext = os.path.splitext(os.path.basename(urllib.parse.urlparse(absolute_url).path))
                        if url_ext and len(url_ext) > 1 and len(url_ext) <= 10:
                            final_filename_to_use += url_ext

            if not final_filename_to_use:
                final_filename_to_use = "downloaded_file_unknown"

            output_file_path = _prepare_output_path(final_filename_to_use)
            _ensure_overwrite(output_file_path)

            file_bytes = await response.body()
            with open(output_file_path, 'wb') as f:
                f.write(file_bytes)

            msg_summary = f"File downloaded: {os.path.basename(output_file_path)}"
            msg_detail = f"File downloaded from {absolute_url} and saved to: {output_file_path}"
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: {msg_detail}. Params: {params.model_dump_json()}")
            return ActionResult(extracted_content=msg_detail)
        except Exception as e:
            error_msg_summary = f"File download failed for URL '{params.url}': {str(e)[:100]}"
            error_msg_detail = f"File download failed (URL: {absolute_url or params.url}, Target File: {output_file_path or params.file_name or 'unknown'}): {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {error_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {error_msg_detail}\n{tb_full}. Output path: {output_file_path}. Params: {params.model_dump_json()}")
            return ActionResult(error_message=error_msg_detail)

    # --------- screenshot_element_action ----------
    @controller.registry.action("screenshot_element_action", param_model=ScreenshotElementParams)
    async def screenshot_element_action_with_context(params: ScreenshotElementParams, browser):
        action_name = "screenshot_element_action"
        output_file_path = ""
        try:
            current_page = await browser.get_current_page()
            if not current_page:
                msg = "Browser page not available for element screenshot."
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
                file_logger.error(f"ERROR in {action_name}: {msg}. Params: {params.model_dump_json()}")
                return ActionResult(error_message=msg)

            output_file_path = _prepare_output_path(params.file_path)
            _ensure_overwrite(output_file_path)

            element_locator = current_page.locator(
                params.selector).first

            try:
                await element_locator.wait_for(state="visible", timeout=float(params.timeout))
            except PlaywrightTimeoutError:
                msg = f"Timeout waiting for element '{params.selector}' (timeout: {params.timeout}ms)."
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
                file_logger.error(f"TIMEOUT ERROR in {action_name}: {msg}. Params: {params.model_dump_json()}")
                return ActionResult(error_message=msg)

            await element_locator.screenshot(path=output_file_path)
            msg_summary = f"Element '{params.selector}' screenshot saved: {os.path.basename(output_file_path)}"
            msg_detail = f"Element '{params.selector}' screenshot saved to: {output_file_path}"
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: {msg_detail}. Params: {params.model_dump_json()}")
            return ActionResult(extracted_content=msg_detail)
        except Exception as e:
            error_msg_summary = f"Element screenshot failed for '{params.selector}': {str(e)[:100]}"
            error_msg_detail = f"Element screenshot failed (Selector: {params.selector}, File: {output_file_path or params.file_path}): {str(e)}"
            if "strict mode violation" in str(e).lower():
                error_msg_summary = f"Element screenshot failed: selector '{params.selector}' matched multiple elements."
                error_msg_detail = f"Element screenshot failed: selector '{params.selector}' matched multiple elements. Ensure selector is unique or use a more specific one. Error: {str(e)}"

            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {error_msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(
                f"ERROR in {action_name}: {error_msg_detail}\n{tb_full}. Output path: {output_file_path}. Params: {params.model_dump_json()}")
            return ActionResult(error_message=error_msg_detail)

    @controller.registry.action("image_ocr_action", param_model=ImageOCRParams)
    def image_ocr_action(params: ImageOCRParams):
        action_name = "image_ocr_action"
        file_logger.info(
            f"Executing {action_name} for image: {params.file_name}, model: {config['ocr_image_model_name']}")
        effective_output_dir = _get_effective_output_dir()
        img_path = os.path.join(effective_output_dir, params.file_name)

        if not os.path.isfile(img_path):
            msg = f"Image file not found: {params.file_name} (expected in {effective_output_dir})"
            if gui_feedback_queue: gui_feedback_queue.put(
                {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
            file_logger.error(f"ERROR in {action_name}: {msg}. Full path: {img_path}")
            return ActionResult(error_message=msg)
        try:
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            b64img = base64.b64encode(img_bytes).decode()
            img_ext = os.path.splitext(params.file_name)[1].lower()
            mime_type = "image/png"
            if img_ext == ".jpg" or img_ext == ".jpeg":
                mime_type = "image/jpeg"
            elif img_ext == ".gif":
                mime_type = "image/gif"
            elif img_ext == ".webp":
                mime_type = "image/webp"
            vision_images = [{"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64img}"}}]
            system_prompt = params.system_prompt or "Describe the contents of this image."
            file_logger.debug(
                f"{action_name}: Sending image {params.file_name} to model {config['ocr_image_model_name']} with prompt: '{system_prompt}'")
            reply = openAITool.call_gpt_api(user_content="", system_prompt=system_prompt,
                                            model=config['ocr_image_model_name'],
                                            vision_images=vision_images)
            reply_clean = reply.replace(' ', '')
            msg_summary = f"Image '{params.file_name}' OCR complete: {reply_clean[:70]}..."
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: OCR for '{params.file_name}' successful.")
            file_logger.debug(f"ACTION [{action_name}] Full OCR Reply: {reply_clean}")
            return ActionResult(extracted_content=reply_clean)
        except Exception as e:
            msg_summary = f"Image OCR failed for '{params.file_name}': {str(e)[:100]}"
            msg_detail = f"Image OCR failed for '{params.file_name}': {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(f"ERROR in {action_name}: {msg_detail}\n{tb_full}. Image path: {img_path}")
            return ActionResult(error_message=msg_detail)

    def truncate_text(text, max_chars):
        if len(text) <= max_chars: return text
        end_pos = text.rfind('.', 0, max_chars)
        if end_pos == -1: end_pos = text.rfind('\n', 0, max_chars)
        if end_pos == -1 or end_pos < max_chars // 2: end_pos = max_chars
        return text[:end_pos].strip() + "..."

    @controller.registry.action("pdf_ocr_action", param_model=PDFOCRParams)
    def pdf_ocr_action(params: PDFOCRParams):
        action_name = "pdf_ocr_action"
        file_logger.info(
            f"Executing {action_name} for PDF: {params.file_name}, model: {config['ocr_pdf_model_name']}, max_pages: {params.max_pages}, max_chars: {params.max_chars}")
        effective_output_dir = _get_effective_output_dir()
        pdf_file_path = os.path.join(effective_output_dir, params.file_name)

        if not os.path.isfile(pdf_file_path):
            msg = f"PDF file not found: {params.file_name} (expected in {effective_output_dir})"
            if gui_feedback_queue: gui_feedback_queue.put(
                {"type": "log", "message": f"ERROR ({action_name}): {msg}", "level": "ERROR_GUI"})
            file_logger.error(f"ERROR in {action_name}: {msg}. Full path: {pdf_file_path}")
            return ActionResult(error_message=msg)
        try:
            all_text = ""
            page_count = 0
            with pdfplumber.open(pdf_file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    if params.max_pages and i >= params.max_pages:
                        file_logger.info(
                            f"{action_name}: Reached max_pages ({params.max_pages}) for {params.file_name}.")
                        break
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"
                    page_count += 1
            all_text = all_text.strip()
            file_logger.info(
                f"{action_name}: Extracted text from {page_count} pages of '{params.file_name}'. Total raw chars: {len(all_text)}.")
            if not all_text:
                msg = f"No text extracted from PDF '{params.file_name}'. It might be image-based or empty."
                if gui_feedback_queue: gui_feedback_queue.put(
                    {"type": "log", "message": f"WARNING ({action_name}): {msg}", "level": "WARNING_GUI"})
                file_logger.warning(f"WARNING in {action_name}: {msg}. PDF path: {pdf_file_path}")
                return ActionResult(extracted_content="", error_message=None)  # No error, but no content
            text_to_send_llm = truncate_text(all_text, params.max_chars or 3000)
            file_logger.debug(
                f"{action_name}: Text sent to LLM (len {len(text_to_send_llm)}): {text_to_send_llm[:300]}...")
            system_prompt = params.system_prompt or "Summarize the key information from the following PDF text."
            file_logger.debug(
                f"{action_name}: Sending PDF text from {params.file_name} to model {config['ocr_pdf_model_name']} with prompt: '{system_prompt}'")
            reply = openAITool.call_gpt_api(user_content=text_to_send_llm, system_prompt=system_prompt,
                                            model=config['ocr_pdf_model_name'])
            msg_summary = f"PDF '{params.file_name}' content processed: {reply[:70]}..."
            if gui_feedback_queue is not None:
                gui_feedback_queue.put({"type": "log", "message": f"ACTION: {msg_summary}", "level": "ACTION_GUI"})
            file_logger.info(f"ACTION [{action_name}]: Content processing for '{params.file_name}' successful.")
            file_logger.debug(f"ACTION [{action_name}] Full LLM Reply for PDF: {reply}")
            return ActionResult(extracted_content=reply)
        except Exception as e:
            msg_summary = f"PDF content processing failed for '{params.file_name}': {str(e)[:100]}"
            msg_detail = f"PDF content processing failed for '{params.file_name}': {str(e)}"
            tb_full = traceback.format_exc()
            if gui_feedback_queue is not None:
                gui_feedback_queue.put(
                    {"type": "log", "message": f"ERROR ({action_name}): {msg_summary}", "level": "ERROR_GUI"})
            file_logger.error(f"ERROR in {action_name}: {msg_detail}\n{tb_full}. PDF path: {pdf_file_path}")
            return ActionResult(error_message=msg_detail)


# --------------------- System message ---------------------
extend_system_message = """
记住最重要的规则:
1. 当你需要保存信息时，请明确指出要保存的文件名和期望的格式（如 .txt, .docx, .xlsx）。
   - 对于截图整个页面或视口，动作名是 'take_screenshot_action'，它接受 'file_path' (字符串) 和 'full_page' (布尔值, 可选, 默认false) 参数。
   - 对于下载任何类型的文件，动作名是 'download_file'，它接受 'url' (字符串, 文件的完整URL) 和 'file_name' (字符串, 可选, 保存的文件名，建议包含后缀如 'report.pdf' 或 'data.zip') 参数。如果未提供 file_name，系统会尝试从URL或HTTP响应头中推断。
   - 对于截取页面上的特定元素（例如一个logo、一个按钮），动作名是 'screenshot_element_action'。它需要以下参数：
     - 'selector' (字符串): 用于定位元素的CSS选择器 (例如 '#some-id' 或 '.some-class img')。
     - 'file_path' (字符串): 保存截图的文件名 (例如 'element_screenshot.png')。
     - 'timeout' (整数, 可选, 默认30000毫秒): 等待元素出现的最长时间（以毫秒为单位）。
   - 对于图片识别，动作名是 'image_ocr_action'，它接受 'file_name' (字符串, 图片必须位于输出目录中) 和 'system_prompt' (字符串) 参数。
   - 对于PDF识别（提取文本并交由LLM处理），动作名是 'pdf_ocr_action'，它接受 'file_name' (字符串, PDF必须位于输出目录中)，以及可选的 'max_pages' (数值, 默认5), 'max_chars' (数值, 默认3000), 'system_prompt' (字符串) 参数。
   - 对于保存文本到简单文件（txt, docx, 基本的xlsx无图表），使用 'save_to_file' 动作。它接受 'text' (字符串) 和 'file_path' (字符串) 参数。文件名应包含期望的后缀如 .txt, .docx, .xlsx。
   - 对于保存结构化数据到Excel文件，并且需要在Excel中创建图表，请使用 'save_data_to_excel_with_chart' 动作。
     它需要以下参数：
       - 'data_csv_string' (字符串): CSV格式的字符串，第一行必须是表头 (e.g., "电影名称,上映年份,类型\\n霸王别姬,1993,剧情\\n活着,1994,剧情")。
       - 'file_path' (字符串): 保存Excel文件的路径 (e.g., 'movies_chart.xlsx')。
       - 'sheet_name' (字符串, 可选, 默认 'Data'): Excel中数据表的工作表名称。
       - 'chart_title' (字符串): 图表的标题。
       - 'chart_type' (字符串): 图表类型 ('bar', 'column', 'line', 'pie' 等)。
       - 'x_axis_column' (字符串): 用作图表X轴的列名（必须与 data_csv_string 中的表头匹配）。
       - 'y_axis_columns' (列表[字符串]): 一个或多个用作图表Y轴的列名（必须与 data_csv_string 中的表头匹配）。
       - 'y_axis_label' (字符串, 可选): Y轴的标签。
       - 'x_axis_label' (字符串, 可选): X轴的标签。
       - 'aggregation_column' (字符串, 可选): 如果X轴是分类数据，且Y轴应代表对某列的聚合（如计数、求和、平均），则指定此列。例如，若X轴为“年份”，Y轴为“该年电影数量”，则此列可能是“电影名称”列，系统将对其进行计数。
       - 'aggregation_type' (字符串, 可选, 默认 'count'): 聚合类型，可以是 'count', 'sum', 'average'。仅当 'aggregation_column' 被指定时有效。

2. 最后的输出结果，要用中文回答用户的问题。
3. 如果任务涉及到提取结构化数据（例如列表、表格），并且用户要求保存为 .xlsx 文件，请尽量将数据构造成适合表格的格式。如果需要图表，必须使用 'save_data_to_excel_with_chart'。
"""

__all__ = [
    "register_actions",
    "extend_system_message",
    "ExcelWithChartParams",
    "ScreenshotParams",
    "DownloadFileParams",
    "ScreenshotElementParams",
    "ImageOCRParams",
    "PDFOCRParams"
]