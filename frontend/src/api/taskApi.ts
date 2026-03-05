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
  TaskStatus,
} from './types'

/**
 * 提交任务
 */
export async function submitTask(request: SubmitTaskRequest): Promise<SubmitTaskResponse> {
  const formData = new FormData()
  formData.append('file', request.file)
  formData.append('backend', request.backend || 'pipeline')
  formData.append('lang', request.lang || 'ch')
  formData.append('method', request.method || 'auto')
  formData.append('formula_enable', String(request.formula_enable ?? true))
  formData.append('table_enable', String(request.table_enable ?? true))
  formData.append('priority', String(request.priority || 0))

  // Video 专用参数
  if (request.keep_audio !== undefined) {
    formData.append('keep_audio', String(request.keep_audio))
  }
  if (request.enable_keyframe_ocr !== undefined) {
    formData.append('enable_keyframe_ocr', String(request.enable_keyframe_ocr))
  }
  if (request.ocr_backend) {
    formData.append('ocr_backend', request.ocr_backend)
  }
  if (request.keep_keyframes !== undefined) {
    formData.append('keep_keyframes', String(request.keep_keyframes))
  }

  // 水印去除参数
  if (request.remove_watermark !== undefined) {
    formData.append('remove_watermark', String(request.remove_watermark))
  }
  if (request.watermark_conf_threshold !== undefined) {
    formData.append('watermark_conf_threshold', String(request.watermark_conf_threshold))
  }
  if (request.watermark_dilation !== undefined) {
    formData.append('watermark_dilation', String(request.watermark_dilation))
  }

  // Audio 专属参数 (SenseVoice)
  if (request.enable_speaker_diarization !== undefined) {
    formData.append('enable_speaker_diarization', String(request.enable_speaker_diarization))
  }

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
  console.log('getTaskStatus called with:', { taskId, uploadImages, format })

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
 * 获取任务列表
 */
export async function listTasks(
  status?: TaskStatus,
  limit: number = 100
): Promise<TaskListResponse> {
  const response = await apiClient.get<TaskListResponse>('/api/v1/queue/tasks', {
    params: { status, limit },
  })
  return response.data
}

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
