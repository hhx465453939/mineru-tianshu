<template>
  <div>
    <!-- 页面标题 -->
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-gray-900">{{ $t('task.taskList') }}</h1>
      <p class="mt-1 text-sm text-gray-600">{{ $t('task.taskList') }}</p>
    </div>

    <!-- 筛选和搜索 -->
    <div class="card mb-6">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <!-- 状态筛选 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('task.filterByStatus') }}</label>
          <select
            v-model="filters.status"
            @change="applyFilters"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">{{ $t('task.allStatus') }}</option>
            <option value="pending">{{ $t('status.pending') }}</option>
            <option value="processing">{{ $t('status.processing') }}</option>
            <option value="completed">{{ $t('status.completed') }}</option>
            <option value="failed">{{ $t('status.failed') }}</option>
            <option value="cancelled">{{ $t('status.cancelled') }}</option>
          </select>
        </div>

        <!-- 后端筛选 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('task.backend') }}</label>
          <select
            v-model="filters.backend"
            @change="applyFilters"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">{{ $t('task.allStatus') }}</option>
            <option value="pipeline">MinerU Pipeline</option>
            <option value="paddleocr-vl">PaddleOCR-VL</option>
            <option value="paddleocr-vl-vllm">PaddleOCR-VL-VLLM</option>
            <option value="vlm-transformers">VLM Transformers</option>
            <option value="vlm-vllm-engine">VLM vLLM Engine</option>
          </select>
        </div>

        <!-- 搜索 -->
        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.search') }}</label>
          <div class="relative">
            <input
              v-model="filters.search"
              @input="applyFilters"
              type="text"
              :placeholder="$t('common.search')"
              class="w-full px-3 py-2 pl-10 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          </div>
        </div>
      </div>

      <div class="mt-4 flex justify-between items-center">
        <div class="text-sm text-gray-600">
          {{ $t('common.total') }}: {{ filteredTasks.length }}
        </div>
        <div class="flex gap-2">
          <button
            @click="refreshTasks"
            :disabled="loading"
            class="btn btn-secondary btn-sm flex items-center"
          >
            <RefreshCw :class="{ 'animate-spin': loading }" class="w-4 h-4 mr-1" />
            {{ $t('common.refresh') }}
          </button>
          <router-link to="/tasks/submit" class="btn btn-primary btn-sm flex items-center">
            <Plus class="w-4 h-4 mr-1" />
            {{ $t('task.submitTask') }}
          </router-link>
        </div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="card">
      <div v-if="loading && tasks.length === 0" class="text-center py-12">
        <LoadingSpinner :text="$t('common.loading')" />
      </div>

      <div v-else-if="filteredTasks.length === 0" class="text-center py-12 text-gray-500">
        <FileQuestion class="w-16 h-16 mx-auto mb-4 text-gray-400" />
        <p>{{ $t('task.noTasks') }}</p>
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                <input
                  v-model="selectAll"
                  @change="toggleSelectAll"
                  :disabled="selectableTaskIdsOnPage.length === 0"
                  type="checkbox"
                  class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.fileName') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.status') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.backend') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.createdAt') }}
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Worker
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {{ $t('task.actions') }}
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr
              v-for="task in paginatedTasks"
              :key="task.task_id"
              :class="{ 'bg-blue-50': selectedTasks.includes(task.task_id) }"
              class="hover:bg-gray-50"
            >
              <td class="px-6 py-4 whitespace-nowrap">
                <input
                  v-model="selectedTasks"
                  :value="task.task_id"
                  :disabled="task.status !== 'completed'"
                  type="checkbox"
                  class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 disabled:opacity-40 disabled:cursor-not-allowed"
                />
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center max-w-xs">
                  <FileText class="w-5 h-5 text-gray-400 flex-shrink-0 mr-2" />
                  <div class="truncate">
                    <div class="text-sm font-medium text-gray-900 truncate">{{ task.file_name }}</div>
                    <div class="text-xs text-gray-500 font-mono truncate">{{ task.task_id }}</div>
                  </div>
                </div>
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <StatusBadge :status="task.status" />
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                {{ formatBackendName(task.backend) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatRelativeTime(task.created_at) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-xs text-gray-500 font-mono">
                {{ task.worker_id ? task.worker_id.split('-').slice(-1)[0] : '-' }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <div class="flex items-center gap-2">
                  <router-link
                    :to="`/tasks/${task.task_id}`"
                    class="text-primary-600 hover:text-primary-700"
                  >
                    <Eye class="w-4 h-4" />
                  </router-link>
                  <button
                    v-if="task.status === 'pending'"
                    @click="cancelTask(task.task_id)"
                    class="text-red-600 hover:text-red-700"
                    :title="$t('common.cancel')"
                  >
                    <X class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 批量操作和分页 -->
      <div v-if="filteredTasks.length > 0" class="mt-4 flex items-center justify-between">
        <!-- 批量操作 -->
        <div class="flex items-center gap-2">
          <span v-if="selectedCompletedTasks.length > 0" class="text-sm text-gray-600">
            {{ $t('common.selected') }}: {{ selectedCompletedTasks.length }}
          </span>
          <button
            v-if="selectedCompletedTasks.length > 0"
            @click="batchDownloadResults"
            :disabled="downloading"
            class="btn btn-primary btn-sm flex items-center disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download class="w-4 h-4 mr-1" />
            {{ downloading ? $t('common.loading') : $t('task.batchDownloadCompleted') }}
          </button>
        </div>

        <!-- 分页 -->
        <div class="flex items-center gap-2">
          <button
            @click="currentPage--"
            :disabled="currentPage === 1"
            class="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft class="w-5 h-5" />
          </button>
          <span class="text-sm text-gray-600">
            {{ $t('common.page') }} {{ currentPage }} / {{ totalPages }}
          </span>
          <button
            @click="currentPage++"
            :disabled="currentPage === totalPages"
            class="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronRight class="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>

    <!-- 取消确认对话框 -->
    <ConfirmDialog
      v-model="showCancelDialog"
      :title="$t('common.confirm')"
      :message="cancelDialogMessage"
      @confirm="confirmCancel"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useTaskStore } from '@/stores'
import { formatRelativeTime, formatBackendName } from '@/utils/format'
import { taskApi } from '@/api'
import StatusBadge from '@/components/StatusBadge.vue'
import LoadingSpinner from '@/components/LoadingSpinner.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  Search,
  RefreshCw,
  Plus,
  FileText,
  Eye,
  X,
  Download,
  FileQuestion,
  ChevronLeft,
  ChevronRight,
} from 'lucide-vue-next'
import type { TaskStatus, Backend } from '@/api/types'

const taskStore = useTaskStore()

const tasks = computed(() => taskStore.tasks)
const loading = ref(false)

// 筛选
const filters = ref({
  status: '' as TaskStatus | '',
  backend: '' as Backend | '',
  search: '',
})

// 计算筛选后的任务
const filteredTasks = computed(() => {
  let result = tasks.value

  if (filters.value.status) {
    result = result.filter(t => t.status === filters.value.status)
  }

  if (filters.value.backend) {
    result = result.filter(t => t.backend === filters.value.backend)
  }

  if (filters.value.search) {
    const search = filters.value.search.toLowerCase()
    result = result.filter(t =>
      t.file_name.toLowerCase().includes(search) ||
      t.task_id.toLowerCase().includes(search)
    )
  }

  return result
})

// 分页
const pageSize = 20
const currentPage = ref(1)
const totalPages = computed(() => Math.ceil(filteredTasks.value.length / pageSize))
const paginatedTasks = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  const end = start + pageSize
  return filteredTasks.value.slice(start, end)
})

// 选择
const selectedTasks = ref<string[]>([])
const selectAll = ref(false)
const downloading = ref(false)
const selectedCompletedTasks = computed(() =>
  selectedTasks.value.filter(id => tasks.value.find(task => task.task_id === id)?.status === 'completed')
)
const selectableTaskIdsOnPage = computed(() =>
  paginatedTasks.value
    .filter(task => task.status === 'completed')
    .map(task => task.task_id)
)

function toggleSelectAll() {
  if (selectAll.value) {
    const selectedSet = new Set(selectedTasks.value)
    selectableTaskIdsOnPage.value.forEach(id => selectedSet.add(id))
    selectedTasks.value = Array.from(selectedSet)
  } else {
    const selectableSet = new Set(selectableTaskIdsOnPage.value)
    selectedTasks.value = selectedTasks.value.filter(id => !selectableSet.has(id))
  }
}

// 取消对话框
const showCancelDialog = ref(false)
const cancelDialogMessage = ref('')
const taskToCancel = ref<string | string[]>('')

async function cancelTask(taskId: string) {
  taskToCancel.value = taskId
  cancelDialogMessage.value = '确定要取消这个任务吗？'
  showCancelDialog.value = true
}

function sanitizeFileName(name: string): string {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

function downloadTextFile(content: string, fileName: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

async function batchDownloadResults() {
  const taskIds = [...selectedCompletedTasks.value]

  if (taskIds.length === 0) {
    alert('请先勾选成功任务')
    return
  }

  downloading.value = true
  const failedTasks: string[] = []
  let downloadedTaskCount = 0

  for (const taskId of taskIds) {
    try {
      const taskStatus = await taskApi.getTaskStatus(taskId, false, 'both')
      if (taskStatus.status !== 'completed' || !taskStatus.data?.content) {
        failedTasks.push(taskStatus.file_name || taskId)
        continue
      }

      const baseName = sanitizeFileName(taskStatus.file_name.replace(/\.[^/.]+$/, '') || taskId)
      downloadTextFile(taskStatus.data.content, `${baseName}_${taskId}.md`, 'text/markdown;charset=utf-8')

      if (taskStatus.data.json_content !== undefined) {
        downloadTextFile(
          JSON.stringify(taskStatus.data.json_content, null, 2),
          `${baseName}_${taskId}.json`,
          'application/json;charset=utf-8'
        )
      }

      downloadedTaskCount += 1
    } catch (error) {
      console.error(`Failed to download task ${taskId}:`, error)
      failedTasks.push(taskId)
    }
  }

  selectedTasks.value = []
  selectAll.value = false
  downloading.value = false

  if (failedTasks.length === 0) {
    alert(`已完成下载 ${downloadedTaskCount} 个任务结果`)
    return
  }

  alert(`已下载 ${downloadedTaskCount} 个任务；失败 ${failedTasks.length} 个`)
}

async function confirmCancel() {
  const ids = Array.isArray(taskToCancel.value) ? taskToCancel.value : [taskToCancel.value]

  for (const id of ids) {
    try {
      await taskStore.cancelTask(id)
    } catch (err) {
      console.error(`Failed to cancel task ${id}:`, err)
    }
  }

  selectedTasks.value = []
  selectAll.value = false
  await refreshTasks()
}

async function applyFilters() {
  currentPage.value = 1
}

async function refreshTasks() {
  loading.value = true
  try {
    await taskStore.fetchTasks(undefined, 1000)
  } finally {
    loading.value = false
  }
}

// 监听筛选后的任务变化,重置选择状态
watch([paginatedTasks, selectedTasks], () => {
  if (selectableTaskIdsOnPage.value.length === 0) {
    selectAll.value = false
    return
  }

  const selectedSet = new Set(selectedTasks.value)
  selectAll.value = selectableTaskIdsOnPage.value.every(id => selectedSet.has(id))
})

watch(tasks, () => {
  const completedTaskIds = new Set(tasks.value.filter(task => task.status === 'completed').map(task => task.task_id))
  selectedTasks.value = selectedTasks.value.filter(id => completedTaskIds.has(id))
})

onMounted(async () => {
  await refreshTasks()
})
</script>

<style scoped>
.btn-sm {
  @apply px-3 py-1.5 text-sm;
}
</style>
