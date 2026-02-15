<template>
  <div>
    <!-- 页面标题 -->
    <div class="mb-6 lg:mb-10">
      <h1 class="text-2xl lg:text-3xl xl:text-4xl font-bold text-gray-900 tracking-tight">{{ $t('dashboard.title') }}</h1>
      <p class="mt-2 lg:mt-3 text-base lg:text-lg text-gray-600">{{ $t('dashboard.systemStatus') }}</p>
    </div>

    <!-- 首次使用：模型下载提示 -->
    <div
      v-if="modelsStatus?.any_missing && !dismissModelTip"
      class="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200"
    >
      <div class="flex items-start justify-between gap-3">
        <p class="text-sm">{{ modelsStatus.first_use_tip }}</p>
        <button
          type="button"
          aria-label="关闭"
          class="shrink-0 rounded p-1 hover:bg-amber-200/50 dark:hover:bg-amber-800/50"
          @click="dismissModelTip = true"
        >
          <XCircle class="h-5 w-5" />
        </button>
      </div>
    </div>

    <!-- 队列统计卡片 -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 lg:gap-6 mb-6 lg:mb-8">
      <StatCard
        :title="$t('status.pending')"
        :value="queueStore.stats.pending"
        :subtitle="$t('dashboard.pendingTasks')"
        :icon="Clock"
        color="gray"
      />
      <StatCard
        :title="$t('status.processing')"
        :value="queueStore.stats.processing"
        :subtitle="$t('dashboard.processingTasks')"
        :icon="Loader"
        color="yellow"
      />
      <StatCard
        :title="$t('status.completed')"
        :value="queueStore.stats.completed"
        :subtitle="$t('dashboard.completedTasks')"
        :icon="CheckCircle"
        color="green"
      />
      <StatCard
        :title="$t('status.failed')"
        :value="queueStore.stats.failed"
        :subtitle="$t('dashboard.failedTasks')"
        :icon="XCircle"
        color="red"
      />
    </div>

    <!-- 快捷操作 -->
    <div class="mb-6 lg:mb-8">
      <div class="card">
        <h2 class="text-base lg:text-lg font-semibold text-gray-900 mb-3 lg:mb-4">{{ $t('common.actions') }}</h2>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 lg:gap-3">
          <router-link to="/tasks/submit" class="btn btn-primary flex items-center justify-center">
            <Upload class="w-4 h-4 mr-2" />
            {{ $t('task.submitTask') }}
          </router-link>
          <router-link to="/tasks" class="btn btn-secondary flex items-center justify-center">
            <ListTodo class="w-4 h-4 mr-2" />
            {{ $t('task.taskList') }}
          </router-link>
          <router-link to="/queue" class="btn btn-secondary flex items-center justify-center">
            <Settings class="w-4 h-4 mr-2" />
            {{ $t('queue.title') }}
          </router-link>
        </div>
      </div>
    </div>

    <!-- 模型检测与状态 -->
    <div class="mb-6 lg:mb-8">
      <div class="card">
        <div class="mb-3 flex items-center justify-between gap-3 lg:mb-4">
          <h2 class="text-base lg:text-lg font-semibold text-gray-900">{{ $t('dashboard.modelStatus') }}</h2>
          <button
            v-if="authStore.isManager"
            @click="triggerModelPreload"
            :disabled="preloadStarting || preloadStatus?.running"
            class="btn btn-secondary btn-sm disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {{ preloadStarting || preloadStatus?.running ? $t('dashboard.modelPreloading') : $t('dashboard.preloadModels') }}
          </button>
        </div>
        <p v-if="modelsStatus?.catalog?.length" class="mb-3 text-xs text-gray-500">
          {{ $t('dashboard.modelCatalog') }}:
          {{ modelsStatus.catalog.map(item => `${item.name}${item.required ? ' (required)' : ''}`).join('，') }}
        </p>
        <div v-if="preloadStatus" class="mb-3 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
          <p v-if="preloadStatus.running">{{ $t('dashboard.modelPreloading') }}</p>
          <p v-else-if="preloadStatus.success_flag === true">{{ $t('dashboard.modelPreloadSuccess') }}</p>
          <p v-else-if="preloadStatus.success_flag === false">{{ $t('dashboard.modelPreloadFailed') }}</p>
          <p v-if="preloadStatus.output_dir">Output: {{ preloadStatus.output_dir }}</p>
        </div>
        <div v-if="modelsStatusLoading" class="py-4 text-center text-gray-500">
          <LoadingSpinner :text="$t('common.loading')" />
        </div>
        <div v-else-if="modelsStatus?.models" class="space-y-2">
          <div
            v-for="(item, key) in modelsStatus.models"
            :key="key"
            class="flex items-center justify-between rounded border border-gray-200 bg-gray-50/50 px-3 py-2 dark:border-gray-700 dark:bg-gray-800/50"
          >
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ item.name }}</span>
            <span class="text-sm" :class="item.ready ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'">
              {{ item.message }}
            </span>
          </div>
        </div>
        <p v-else class="text-sm text-gray-500">{{ $t('common.noData') }}</p>
      </div>
    </div>

    <!-- 最近任务 -->
    <div class="card">
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <h2 class="text-base lg:text-lg font-semibold text-gray-900">{{ $t('dashboard.recentTasks') }}</h2>
        <button
          @click="refreshTasks"
          :disabled="taskStore.loading"
          class="text-sm text-primary-600 hover:text-primary-700 flex items-center justify-center sm:justify-start"
        >
          <RefreshCw :class="{ 'animate-spin': taskStore.loading }" class="w-4 h-4 mr-1" />
          {{ $t('common.refresh') }}
        </button>
      </div>

      <div v-if="taskStore.loading && recentTasks.length === 0" class="text-center py-8">
        <LoadingSpinner :text="$t('common.loading')" />
      </div>

      <div v-else-if="recentTasks.length === 0" class="text-center py-8 text-gray-500">
        <FileQuestion class="w-12 h-12 mx-auto mb-2 text-gray-400" />
        <p>{{ $t('task.noTasks') }}</p>
      </div>

      <div v-else class="overflow-x-auto -mx-4 sm:-mx-6 lg:-mx-8">
        <div class="inline-block min-w-full align-middle px-4 sm:px-6 lg:px-8">
          <table class="min-w-full divide-y divide-gray-200">
          <thead>
            <tr class="bg-gray-50">
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.fileName') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.status') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.createdAt') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.actions') }}
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="task in recentTasks" :key="task.task_id" class="hover:bg-gray-50">
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                  <FileText class="w-5 h-5 text-gray-400 mr-2" />
                  <div class="text-sm font-medium text-gray-900 truncate max-w-xs">
                    {{ task.file_name }}
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <StatusBadge :status="task.status" />
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatRelativeTime(task.created_at) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm">
                <router-link
                  :to="`/tasks/${task.task_id}`"
                  class="text-primary-600 hover:text-primary-700 flex items-center"
                >
                  <Eye class="w-4 h-4 mr-1" />
                  查看
                </router-link>
              </td>
            </tr>
          </tbody>
        </table>
        </div>
      </div>

      <div v-if="recentTasks.length > 0" class="mt-4 text-center">
        <router-link to="/tasks" class="text-sm text-primary-600 hover:text-primary-700">
          查看全部任务 →
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTaskStore, useQueueStore, useAuthStore } from '@/stores'
import { formatRelativeTime } from '@/utils/format'
import {
  getModelsStatus,
  getModelPreloadStatus,
  startModelPreload,
  type ModelsStatusResponse,
  type ModelPreloadStatusResponse,
} from '@/api/systemApi'
import StatCard from '@/components/StatCard.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import {
  Clock,
  Loader,
  CheckCircle,
  XCircle,
  Upload,
  ListTodo,
  Settings,
  RefreshCw,
  FileText,
  Eye,
  FileQuestion,
} from 'lucide-vue-next'

const taskStore = useTaskStore()
const queueStore = useQueueStore()
const authStore = useAuthStore()

const modelsStatus = ref<ModelsStatusResponse | null>(null)
const modelsStatusLoading = ref(true)
const dismissModelTip = ref(false)
const preloadStatus = ref<ModelPreloadStatusResponse | null>(null)
const preloadStarting = ref(false)
let preloadTimer: number | null = null

// 计算最近的任务（最多显示10个）
const recentTasks = computed(() => {
  return taskStore.tasks.slice(0, 10)
})

async function refreshTasks() {
  await taskStore.fetchTasks(undefined, 10)
}

async function loadModelsStatus() {
  modelsStatusLoading.value = true
  try {
    const res = await getModelsStatus()
    if (res.success) modelsStatus.value = res
  } catch {
    modelsStatus.value = null
  } finally {
    modelsStatusLoading.value = false
  }
}

async function loadModelPreloadStatus() {
  if (!authStore.isAuthenticated) return

  try {
    const res = await getModelPreloadStatus()
    preloadStatus.value = res
  } catch {
    preloadStatus.value = null
  }
}

function startPreloadPolling() {
  if (preloadTimer) window.clearInterval(preloadTimer)
  preloadTimer = window.setInterval(async () => {
    await loadModelPreloadStatus()
    if (!preloadStatus.value?.running && preloadTimer) {
      window.clearInterval(preloadTimer)
      preloadTimer = null
      await loadModelsStatus()
    }
  }, 3000)
}

async function triggerModelPreload() {
  preloadStarting.value = true
  try {
    await startModelPreload()
    await loadModelPreloadStatus()
    startPreloadPolling()
  } catch (error: any) {
    alert(error?.response?.data?.detail || '启动模型预下载失败')
  } finally {
    preloadStarting.value = false
  }
}

onMounted(async () => {
  await refreshTasks()
  await loadModelsStatus()
  await loadModelPreloadStatus()

  if (preloadStatus.value?.running) {
    startPreloadPolling()
  }
})

onUnmounted(() => {
  if (preloadTimer) {
    window.clearInterval(preloadTimer)
    preloadTimer = null
  }
})
</script>
