/**
 * 系统配置 API
 */

import type {
  SystemConfigResponse,
  SystemConfigUpdateRequest,
} from './types'
import apiClient from './client'

/** 单个模型状态 */
export interface ModelStatusItem {
  ready: boolean
  name: string
  cache_hint: string
  message: string
}

/** 模型状态接口响应 */
export interface ModelsStatusResponse {
  success: boolean
  models: Record<string, ModelStatusItem>
  catalog: Array<{
    key: string
    name: string
    required: boolean
    auto_download: boolean
    description: string
  }>
  any_ready: boolean
  any_missing: boolean
  first_use_tip: string
  timestamp: string
}

export interface ModelPreloadStartResponse {
  success: boolean
  message: string
  output_dir: string
  models?: string
  force: boolean
  started_at: string
}

export interface ModelPreloadStatusResponse {
  success: boolean
  running: boolean
  started_at: string | null
  finished_at: string | null
  success_flag: boolean | null
  return_code: number | null
  error: string | null
  output_dir: string | null
  logs: string[]
}

/**
 * 获取模型就绪状态（用于首次使用提示与模型检测）
 */
export async function getModelsStatus(): Promise<ModelsStatusResponse> {
  const response = await apiClient.get<ModelsStatusResponse>('/api/v1/models/status')
  return response.data
}

/**
 * 启动模型预下载（后台任务）
 */
export async function startModelPreload(
  outputDir?: string,
  models?: string,
  force: boolean = false
): Promise<ModelPreloadStartResponse> {
  const response = await apiClient.post<ModelPreloadStartResponse>('/api/v1/models/preload/start', null, {
    params: {
      output_dir: outputDir,
      models,
      force,
    },
  })
  return response.data
}

/**
 * 获取模型预下载状态
 */
export async function getModelPreloadStatus(): Promise<ModelPreloadStatusResponse> {
  const response = await apiClient.get<ModelPreloadStatusResponse>('/api/v1/models/preload/status')
  return response.data
}

/**
 * 获取系统配置（公开接口）
 */
export async function getSystemConfig(): Promise<SystemConfigResponse> {
  const response = await apiClient.get('/api/v1/auth/system/config')
  return response.data
}

/**
 * 更新系统配置（管理员）
 */
export async function updateSystemConfig(
  config: SystemConfigUpdateRequest
): Promise<SystemConfigResponse> {
  const response = await apiClient.post('/api/v1/auth/system/config', config)
  return response.data
}

/**
 * 上传系统 Logo（管理员）
 */
export async function uploadSystemLogo(
  file: File
): Promise<{ success: boolean; logo_url: string; message: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await apiClient.post('/api/v1/auth/system/logo/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}
