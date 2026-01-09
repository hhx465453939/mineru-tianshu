/**
 * 系统配置 Store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getSystemConfig, type SystemConfig } from '@/api'

export const useSystemStore = defineStore('system', () => {
  // 系统配置
  const config = ref<SystemConfig>({
    system_name: 'MinerU Tianshu',
    system_logo: '',
    show_github_star: true,
    allow_registration: true,
  })

  const loading = ref(false)

  /**
   * 加载系统配置
   */
  async function loadConfig() {
    try {
      loading.value = true
      const response = await getSystemConfig()
      config.value = response.config
    } catch (error) {
      console.error('Failed to load system config:', error)
      // 使用默认配置
      config.value = {
        system_name: 'MinerU Tianshu',
        system_logo: '',
        show_github_star: true,
        allow_registration: true,
      }
    } finally {
      loading.value = false
    }
  }

  /**
   * 更新页面标题
   */
  function updatePageTitle(pageTitle?: string) {
    if (pageTitle) {
      document.title = `${pageTitle} - ${config.value.system_name}`
    } else {
      document.title = config.value.system_name
    }
  }

  return {
    config,
    loading,
    loadConfig,
    updatePageTitle,
  }
})
