/**
 * 任务相关 API
 */
import apiClient from './client'
import type {
  SubmitTaskRequest,
  SubmitTaskResponse,
  TaskStatusResponse,
  TaskListResponse,
  ApiResponse,
  TaskQueryParams,
} from './types'

// =================================================================
// 核心任务操作
// =================================================================

/**
 * 提交任务
 */
export async function submitTask(request: SubmitTaskRequest): Promise<SubmitTaskResponse> {
  const formData = new FormData()
  formData.append('file', request.file)

  // 基础参数
  if (request.backend) formData.append('backend', request.backend)
  if (request.lang) formData.append('lang', request.lang)
  if (request.method) formData.append('method', request.method)
  if (request.formula_enable !== undefined) formData.append('formula_enable', String(request.formula_enable))
  if (request.table_enable !== undefined) formData.append('table_enable', String(request.table_enable))
  if (request.priority !== undefined) formData.append('priority', String(request.priority))

  // 分页与模式
  if (request.start_page !== undefined) formData.append('start_page', String(request.start_page))
  if (request.end_page !== undefined) formData.append('end_page', String(request.end_page))
  if (request.force_ocr !== undefined) formData.append('force_ocr', String(request.force_ocr))

  // 远程服务
  if (request.server_url) formData.append('server_url', request.server_url)

  // Office 转换
  if (request.convert_office_to_pdf !== undefined) {
    formData.append('convert_office_to_pdf', String(request.convert_office_to_pdf))
  }

  // MinerU 调试/输出选项
  if (request.draw_layout_bbox !== undefined) formData.append('draw_layout_bbox', String(request.draw_layout_bbox))
  if (request.draw_span_bbox !== undefined) formData.append('draw_span_bbox', String(request.draw_span_bbox))
  if (request.dump_markdown !== undefined) formData.append('dump_markdown', String(request.dump_markdown))
  if (request.dump_middle_json !== undefined) formData.append('dump_middle_json', String(request.dump_middle_json))
  if (request.dump_model_output !== undefined) formData.append('dump_model_output', String(request.dump_model_output))
  if (request.dump_content_list !== undefined) formData.append('dump_content_list', String(request.dump_content_list))
  if (request.dump_orig_pdf !== undefined) formData.append('dump_orig_pdf', String(request.dump_orig_pdf))

  // 兼容旧参数
  if (request.draw_layout !== undefined) formData.append('draw_layout', String(request.draw_layout))
  if (request.draw_span !== undefined) formData.append('draw_span', String(request.draw_span))

  // Video 专用参数
  if (request.keep_audio !== undefined) formData.append('keep_audio', String(request.keep_audio))
  if (request.enable_keyframe_ocr !== undefined) formData.append('enable_keyframe_ocr', String(request.enable_keyframe_ocr))
  if (request.ocr_backend) formData.append('ocr_backend', request.ocr_backend)
  if (request.keep_keyframes !== undefined) formData.append('keep_keyframes', String(request.keep_keyframes))

  // 水印去除参数
  if (request.remove_watermark !== undefined) formData.append('remove_watermark', String(request.remove_watermark))
  if (request.watermark_conf_threshold !== undefined) formData.append('watermark_conf_threshold', String(request.watermark_conf_threshold))
  if (request.watermark_dilation !== undefined) formData.append('watermark_dilation', String(request.watermark_dilation))

  // Audio 专属参数 (SenseVoice)
  if (request.enable_speaker_diarization !== undefined) formData.append('enable_speaker_diarization', String(request.enable_speaker_diarization))

  const response = await apiClient.post<SubmitTaskResponse>(
    '/api/v1/tasks/submit',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  )
  return response.data
}

/**
 * 查询任务状态
 */
export async function getTaskStatus(
  taskId: string,
  uploadImages: boolean = false,
  format: 'markdown' | 'json' | 'both' = 'markdown'
): Promise<TaskStatusResponse> {
  const response = await apiClient.get<TaskStatusResponse>(
    `/api/v1/tasks/${taskId}`,
    {
      params: {
        upload_images: uploadImages,
        format: format
      },
    }
  )
  return response.data
}

/**
 * 取消任务
 */
export async function cancelTask(taskId: string): Promise<ApiResponse> {
  const response = await apiClient.delete<ApiResponse>(`/api/v1/tasks/${taskId}`)
  return response.data
}

/**
 * 获取任务列表 (支持分页、搜索、筛选)
 */
export async function listTasks(params: TaskQueryParams): Promise<TaskListResponse> {
  const response = await apiClient.get<TaskListResponse>('/api/v1/queue/tasks', {
    params,
  })
  return response.data
}

// =================================================================
// 批量操作（本地增强功能）
// =================================================================

function parseFileNameFromDisposition(disposition?: string): string | null {
  if (!disposition) return null

  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }

  const plainMatch = disposition.match(/filename="?([^";]+)"?/i)
  if (plainMatch?.[1]) return plainMatch[1]
  return null
}

/**
 * 批量下载任务完整结果目录压缩包
 */
export async function downloadTasksArchive(taskIds: string[]): Promise<{ blob: Blob; fileName: string }> {
  const response = await apiClient.post(
    '/api/v1/tasks/export/archive',
    { task_ids: taskIds },
    { responseType: 'blob' }
  )

  const header = response.headers?.['content-disposition']
  const fileName =
    parseFileNameFromDisposition(header) ||
    `tianshu_tasks_export_${new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14)}.zip`

  return {
    blob: response.data as Blob,
    fileName,
  }
}

/**
 * 批量取消/停止任务（支持 pending 和 processing 状态）
 */
export async function batchCancelTasks(taskIds: string[]): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>('/api/v1/tasks/batch/cancel', {
    task_ids: taskIds,
  })
  return response.data
}

/**
 * 批量硬删除任务（数据库记录 + 上传文件 + 结果目录，不可恢复）
 */
export async function batchDeleteTasks(taskIds: string[]): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>('/api/v1/tasks/batch/delete', {
    task_ids: taskIds,
  })
  return response.data
}

/**
 * 批量原地重启任务（仅 failed/pending 生效，重置为 pending 并重新入队，复用原上传文件）
 */
export async function batchRestartTasks(taskIds: string[]): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>('/api/v1/tasks/batch/restart', {
    task_ids: taskIds,
  })
  return response.data
}

// =================================================================
// 新增管理接口：重试、暂停、恢复、清理（上游新增）
// =================================================================

/**
 * 重试失败的任务
 */
export async function retryTask(taskId: string): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>(`/api/v1/tasks/${taskId}/retry`)
  return response.data
}

/**
 * 暂停任务 (仅 Pending 状态有效)
 */
export async function pauseTask(taskId: string): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>(`/api/v1/tasks/${taskId}/pause`)
  return response.data
}

/**
 * 恢复任务 (仅 Paused 状态有效)
 */
export async function resumeTask(taskId: string): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>(`/api/v1/tasks/${taskId}/resume`)
  return response.data
}

/**
 * 清理任务缓存 (删除磁盘文件，保留数据库记录)
 */
export async function clearTaskCache(taskId: string): Promise<ApiResponse> {
  const response = await apiClient.post<ApiResponse>(`/api/v1/tasks/${taskId}/clear-cache`)
  return response.data
}

/**
 * 一键清理所有失败的任务
 */
export async function clearFailedTasks(): Promise<{ status: string; deleted_count: number }> {
  const response = await apiClient.delete<{ status: string; deleted_count: number }>('/api/v1/tasks/failed/clear')
  return response.data
}
