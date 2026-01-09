<template>
  <div class="max-w-4xl mx-auto">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-900">{{ $t('systemConfig.title') }}</h1>
      <p class="mt-2 text-sm text-gray-600">{{ $t('systemConfig.description') }}</p>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="flex justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- 配置表单 -->
    <div v-else class="bg-white rounded-lg shadow-md p-6">
      <form @submit.prevent="handleSubmit" class="space-y-6">
        <!-- 系统名称 -->
        <div>
          <label for="system_name" class="block text-sm font-medium text-gray-700 mb-2">
            {{ $t('systemConfig.systemName') }}
          </label>
          <input
            id="system_name"
            v-model="formData.system_name"
            type="text"
            required
            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            :placeholder="$t('systemConfig.systemNamePlaceholder')"
          />
          <p class="mt-1 text-xs text-gray-500">{{ $t('systemConfig.systemNameHelp') }}</p>
        </div>

        <!-- Logo URL -->
        <div>
          <label for="system_logo" class="block text-sm font-medium text-gray-700 mb-2">
            {{ $t('systemConfig.systemLogo') }}
          </label>

          <!-- 文件上传区域 -->
          <div class="space-y-3">
            <!-- 隐藏的文件输入 -->
            <input
              ref="logoFileInput"
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/gif,image/webp"
              class="hidden"
              @change="handleFileSelect"
            />

            <!-- 上传按钮 -->
            <div class="flex items-center space-x-3">
              <button
                type="button"
                @click="triggerFileSelect"
                :disabled="uploading"
                class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="uploading">{{ $t('systemConfig.uploading') }}</span>
                <span v-else>{{ $t('systemConfig.uploadLogo') }}</span>
              </button>

              <button
                v-if="formData.system_logo"
                type="button"
                @click="clearLogo"
                :disabled="uploading"
                class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {{ $t('systemConfig.clearLogo') }}
              </button>
            </div>

            <!-- URL 输入框（可选） -->
            <div>
              <label class="block text-xs text-gray-600 mb-1">
                {{ $t('systemConfig.orEnterUrl') }}
              </label>
              <input
                id="system_logo"
                v-model="formData.system_logo"
                type="url"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                :placeholder="$t('systemConfig.systemLogoPlaceholder')"
              />
            </div>
          </div>

          <p class="mt-1 text-xs text-gray-500">{{ $t('systemConfig.systemLogoHelp') }}</p>

          <!-- Logo 预览 -->
          <div v-if="logoPreviewUrl" class="mt-3">
            <p class="text-sm text-gray-700 mb-2">{{ $t('systemConfig.logoPreview') }}</p>
            <img
              :src="logoPreviewUrl"
              alt="Logo Preview"
              class="h-16 object-contain border border-gray-200 rounded-lg p-2"
              @error="handleImageError"
            />
          </div>
        </div>

        <!-- GitHub Star 显示 -->
        <div>
          <label class="flex items-center">
            <input
              v-model="formData.show_github_star"
              type="checkbox"
              class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <span class="ml-2 text-sm font-medium text-gray-700">
              {{ $t('systemConfig.showGithubStar') }}
            </span>
          </label>
          <p class="mt-1 ml-6 text-xs text-gray-500">{{ $t('systemConfig.showGithubStarHelp') }}</p>
        </div>

        <!-- 允许用户注册 -->
        <div>
          <label class="flex items-center">
            <input
              v-model="formData.allow_registration"
              type="checkbox"
              class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <span class="ml-2 text-sm font-medium text-gray-700">
              {{ $t('systemConfig.allowRegistration') }}
            </span>
          </label>
          <p class="mt-1 ml-6 text-xs text-gray-500">{{ $t('systemConfig.allowRegistrationHelp') }}</p>
        </div>

        <!-- 按钮组 -->
        <div class="flex justify-end space-x-4 pt-4 border-t border-gray-200">
          <button
            type="button"
            @click="resetForm"
            class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
            :disabled="saving"
          >
            {{ $t('systemConfig.reset') }}
          </button>
          <button
            type="submit"
            class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="saving"
          >
            <span v-if="saving">{{ $t('systemConfig.saving') }}</span>
            <span v-else>{{ $t('systemConfig.save') }}</span>
          </button>
        </div>
      </form>

      <!-- 当前配置预览 -->
      <div class="mt-8 pt-6 border-t border-gray-200">
        <h2 class="text-lg font-semibold text-gray-900 mb-4">{{ $t('systemConfig.currentConfig') }}</h2>
        <div class="bg-gray-50 rounded-lg p-4 space-y-2">
          <div class="flex justify-between">
            <span class="text-sm text-gray-600">{{ $t('systemConfig.systemName') }}:</span>
            <span class="text-sm font-medium text-gray-900">{{ originalConfig.system_name }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-sm text-gray-600">{{ $t('systemConfig.systemLogo') }}:</span>
            <span class="text-sm font-medium text-gray-900">
              {{ originalConfig.system_logo || $t('systemConfig.default') }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-sm text-gray-600">{{ $t('systemConfig.showGithubStar') }}:</span>
            <span class="text-sm font-medium text-gray-900">
              {{ originalConfig.show_github_star ? $t('common.yes') : $t('common.no') }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-sm text-gray-600">{{ $t('systemConfig.allowRegistration') }}:</span>
            <span class="text-sm font-medium text-gray-900">
              {{ originalConfig.allow_registration ? $t('common.yes') : $t('common.no') }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getSystemConfig, updateSystemConfig, uploadSystemLogo, type SystemConfig } from '@/api'
import { toast } from '@/utils/toast'
import LoadingSpinner from '@/components/LoadingSpinner.vue'

const { t } = useI18n()

const loading = ref(true)
const saving = ref(false)
const uploading = ref(false)

// 原始配置（从服务器加载）
const originalConfig = ref<SystemConfig>({
  system_name: 'MinerU Tianshu',
  system_logo: '',
  show_github_star: true,
  allow_registration: true,
})

// 表单数据
const formData = ref<SystemConfig>({
  system_name: 'MinerU Tianshu',
  system_logo: '',
  show_github_star: true,
  allow_registration: true,
})

// Logo 上传相关
const logoFileInput = ref<HTMLInputElement | null>(null)
const logoPreviewUrl = ref<string>('')

/**
 * 加载系统配置
 */
async function loadConfig() {
  try {
    loading.value = true
    const response = await getSystemConfig()
    originalConfig.value = { ...response.config }
    formData.value = { ...response.config }
    logoPreviewUrl.value = response.config.system_logo
  } catch (error: any) {
    console.error('Failed to load system config:', error)
    toast.error(t('systemConfig.loadError'))
  } finally {
    loading.value = false
  }
}

/**
 * 触发文件选择
 */
function triggerFileSelect() {
  logoFileInput.value?.click()
}

/**
 * 处理文件选择
 */
async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]

  if (!file) return

  // 验证文件类型
  const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/gif', 'image/webp']
  if (!allowedTypes.includes(file.type)) {
    toast.error(t('systemConfig.invalidFileType'))
    return
  }

  // 验证文件大小 (5MB)
  if (file.size > 5 * 1024 * 1024) {
    toast.error(t('systemConfig.fileTooLarge'))
    return
  }

  try {
    uploading.value = true

    // 上传文件到服务器
    const response = await uploadSystemLogo(file)

    // 更新表单数据和预览
    formData.value.system_logo = response.logo_url
    logoPreviewUrl.value = response.logo_url

    toast.success(t('systemConfig.uploadSuccess'))
  } catch (error: any) {
    console.error('Failed to upload logo:', error)
    toast.error(error.response?.data?.detail || t('systemConfig.uploadError'))
  } finally {
    uploading.value = false
    // 清空 input，允许重新选择相同文件
    if (target) {
      target.value = ''
    }
  }
}

/**
 * 清除 Logo
 */
function clearLogo() {
  formData.value.system_logo = ''
  logoPreviewUrl.value = ''
  if (logoFileInput.value) {
    logoFileInput.value.value = ''
  }
}

/**
 * 提交表单
 */
async function handleSubmit() {
  try {
    saving.value = true

    // 只提交有变化的字段
    const updates: Partial<SystemConfig> = {}
    if (formData.value.system_name !== originalConfig.value.system_name) {
      updates.system_name = formData.value.system_name
    }
    if (formData.value.system_logo !== originalConfig.value.system_logo) {
      updates.system_logo = formData.value.system_logo
    }
    if (formData.value.show_github_star !== originalConfig.value.show_github_star) {
      updates.show_github_star = formData.value.show_github_star
    }
    if (formData.value.allow_registration !== originalConfig.value.allow_registration) {
      updates.allow_registration = formData.value.allow_registration
    }

    if (Object.keys(updates).length === 0) {
      toast.success(t('systemConfig.noChanges'))
      return
    }

    const response = await updateSystemConfig(updates)
    originalConfig.value = { ...response.config }
    formData.value = { ...response.config }
    logoPreviewUrl.value = response.config.system_logo

    toast.success(t('systemConfig.saveSuccess'))

    // 刷新页面以应用新配置（特别是系统名称和 Logo）
    setTimeout(() => {
      window.location.reload()
    }, 1500)
  } catch (error: any) {
    console.error('Failed to update system config:', error)
    toast.error(error.response?.data?.detail || t('systemConfig.saveError'))
  } finally {
    saving.value = false
  }
}

/**
 * 重置表单
 */
function resetForm() {
  formData.value = { ...originalConfig.value }
  logoPreviewUrl.value = originalConfig.value.system_logo
}

/**
 * 处理图片加载错误
 */
function handleImageError(event: Event) {
  const target = event.target as HTMLImageElement
  target.style.display = 'none'
  toast.error(t('systemConfig.logoLoadError'))
}

onMounted(() => {
  loadConfig()
})
</script>
