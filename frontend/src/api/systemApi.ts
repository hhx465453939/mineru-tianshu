/**
 * 系统配置 API
 */

import type {
  SystemConfigResponse,
  SystemConfigUpdateRequest,
} from './types'
import apiClient from './client'

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
