<template>
  <Dialog
    :model-value="open"
    :title="editingGroup ? '编辑模型映射' : '添加模型映射'"
    :description="editingGroup ? '修改映射配置' : '将提供商模型映射到客户端模型'"
    :icon="Tag"
    size="lg"
    @update:model-value="$emit('update:open', $event)"
  >
    <div class="space-y-4">
      <!-- 目标模型选择 -->
      <div class="space-y-1.5">
        <Label class="text-xs">客户端模型</Label>
        <Select
          :model-value="formData.modelId"
          :disabled="!!editingGroup"
          @update:model-value="handleModelChange"
        >
          <SelectTrigger class="h-9">
            <SelectValue placeholder="请选择客户端模型" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="model in models"
              :key="model.id"
              :value="model.id"
            >
              <div class="flex items-center gap-2">
                <span class="font-medium">{{ model.global_model_display_name || model.provider_model_name }}</span>
                <span class="text-xs text-muted-foreground font-mono">{{ model.provider_model_name }}</span>
              </div>
            </SelectItem>
          </SelectContent>
        </Select>
        <p class="text-xs text-muted-foreground">
          客户端请求此模型时，将路由到选中的提供商模型
        </p>
      </div>

      <!-- 映射名称选择面板 -->
      <div class="space-y-1.5">
        <Label class="text-xs">提供商模型</Label>
        <!-- 搜索栏 -->
        <div class="flex items-center gap-2">
          <div class="flex-1 relative">
            <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              v-model="searchQuery"
              placeholder="搜索或添加自定义提供商模型..."
              class="pl-8 h-9"
            />
          </div>
          <!-- 已选数量徽章 -->
          <span
            v-if="selectedNames.length === 0"
            class="h-7 px-2.5 text-xs rounded-md flex items-center bg-muted text-muted-foreground shrink-0"
          >
            未选择
          </span>
          <span
            v-else
            class="h-7 px-2.5 text-xs rounded-md flex items-center bg-primary/10 text-primary shrink-0"
          >
            已选 {{ selectedNames.length }} 个
          </span>
          <!-- 刷新上游模型按钮 -->
          <button
            v-if="upstreamModelsLoaded"
            type="button"
            class="p-2 hover:bg-muted rounded-md transition-colors shrink-0"
            :disabled="fetchingUpstreamModels"
            title="刷新上游模型"
            @click="fetchUpstreamModels()"
          >
            <RefreshCw
              class="w-4 h-4"
              :class="{ 'animate-spin': fetchingUpstreamModels }"
            />
          </button>
          <button
            v-else-if="!fetchingUpstreamModels"
            type="button"
            class="p-2 hover:bg-muted rounded-md transition-colors shrink-0"
            title="从提供商获取模型"
            @click="fetchUpstreamModels()"
          >
            <Zap class="w-4 h-4" />
          </button>
          <Loader2
            v-else
            class="w-4 h-4 animate-spin text-muted-foreground shrink-0"
          />
        </div>

        <!-- 模型列表 -->
        <div class="border rounded-lg overflow-hidden">
          <div class="min-h-60 max-h-80 overflow-y-auto">
            <!-- 加载中 -->
            <div
              v-if="loadingModels"
              class="flex items-center justify-center py-12"
            >
              <Loader2 class="w-6 h-6 animate-spin text-primary" />
            </div>

            <template v-else>
              <!-- 添加自定义映射名称（搜索内容不在列表中时显示） -->
              <div
                v-if="searchQuery && canAddAsCustom"
                class="px-3 py-2 border-b bg-background sticky top-0 z-30"
              >
                <div
                  class="flex items-center justify-between px-3 py-2 rounded-lg border border-dashed hover:border-primary hover:bg-primary/5 cursor-pointer transition-colors"
                  @click="addCustomName"
                >
                  <div class="flex items-center gap-2">
                    <Plus class="w-4 h-4 text-muted-foreground" />
                    <span class="text-sm font-mono">{{ searchQuery }}</span>
                  </div>
                  <span class="text-xs text-muted-foreground">添加自定义提供商模型</span>
                </div>
              </div>

              <!-- 自定义映射名称 -->
              <div v-if="customNames.length > 0">
                <div
                  class="flex items-center justify-between px-3 py-2 bg-muted sticky top-0 z-20 cursor-pointer hover:bg-muted/80 transition-colors"
                  @click="toggleGroupCollapse('custom')"
                >
                  <div class="flex items-center gap-2">
                    <ChevronDown
                      class="w-4 h-4 transition-transform shrink-0"
                      :class="collapsedGroups.has('custom') ? '-rotate-90' : ''"
                    />
                    <span class="text-xs font-medium">自定义模型</span>
                    <span class="text-xs text-muted-foreground">({{ customNames.length }})</span>
                  </div>
                </div>
                <div
                  v-show="!collapsedGroups.has('custom')"
                  class="space-y-1 p-2"
                >
                  <div
                    v-for="name in sortedCustomNames"
                    :key="name"
                    class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer"
                    @click="toggleName(name)"
                  >
                    <div
                      class="w-4 h-4 border rounded flex items-center justify-center shrink-0"
                      :class="selectedNames.includes(name) ? 'bg-primary border-primary' : ''"
                    >
                      <Check
                        v-if="selectedNames.includes(name)"
                        class="w-3 h-3 text-primary-foreground"
                      />
                    </div>
                    <span class="text-sm font-mono truncate flex-1">{{ name }}</span>
                  </div>
                </div>
              </div>

              <!-- 上游模型 -->
              <template v-if="filteredUpstreamModels.length > 0">
                <div
                  class="flex items-center justify-between px-3 py-2 bg-muted sticky top-0 z-20 cursor-pointer hover:bg-muted/80 transition-colors"
                  @click="toggleGroupCollapse('upstream')"
                >
                  <div class="flex items-center gap-2">
                    <ChevronDown
                      class="w-4 h-4 transition-transform shrink-0"
                      :class="collapsedGroups.has('upstream') ? '-rotate-90' : ''"
                    />
                    <span class="text-xs font-medium">上游模型</span>
                    <span class="text-xs text-muted-foreground">({{ upstreamModelNames.length }})</span>
                  </div>
                  <button
                    type="button"
                    class="text-xs text-primary hover:underline"
                    @click.stop="toggleAllUpstreamModels"
                  >
                    {{ isAllUpstreamModelsSelected ? '取消全选' : '全选' }}
                  </button>
                </div>
                <div
                  v-show="!collapsedGroups.has('upstream')"
                  class="space-y-1 p-2"
                >
                  <div
                    v-for="name in filteredUpstreamModels"
                    :key="name"
                    class="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted cursor-pointer"
                    @click="toggleName(name)"
                  >
                    <div
                      class="w-4 h-4 border rounded flex items-center justify-center shrink-0"
                      :class="selectedNames.includes(name) ? 'bg-primary border-primary' : ''"
                    >
                      <Check
                        v-if="selectedNames.includes(name)"
                        class="w-3 h-3 text-primary-foreground"
                      />
                    </div>
                    <span class="text-sm font-mono truncate flex-1">{{ name }}</span>
                  </div>
                </div>
              </template>

              <!-- 空状态 -->
              <div
                v-if="showEmptyState"
                class="flex flex-col items-center justify-center py-12 text-muted-foreground"
              >
                <Tag class="w-10 h-10 mb-2 opacity-30" />
                <p class="text-sm">
                  {{ searchQuery ? '无匹配结果' : '暂无可选模型' }}
                </p>
                <p class="text-xs mt-1">
                  输入模型名称后点击添加自定义提供商模型
                </p>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="space-y-4">
        <div class="space-y-1">
          <Label class="text-xs">请求覆盖</Label>
          <p class="text-xs text-muted-foreground">
            可按映射规则重写上游请求参数；通用覆盖和逐项映射二选一，避免配置冲突
          </p>
        </div>

        <div class="rounded-lg border p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-sm font-medium">
                推理强度
              </div>
              <div class="text-xs text-muted-foreground">
                对应 <span class="font-mono">reasoning.effort</span> 等语义字段
              </div>
            </div>
            <div class="w-44 shrink-0">
              <Select
                :model-value="formData.reasoningEffortMode"
                @update:model-value="setReasoningEffortMode"
              >
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不调整</SelectItem>
                  <SelectItem value="wildcard">通用覆盖</SelectItem>
                  <SelectItem value="per_value">逐项映射</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div
            v-if="formData.reasoningEffortMode === 'wildcard'"
            class="flex items-center gap-3"
          >
            <div class="flex-1 text-sm text-muted-foreground">
              effort <span class="font-mono">*</span> 统一改为
            </div>
            <div class="w-44 shrink-0">
              <Select
                :model-value="formData.reasoningEffortWildcard || '__none__'"
                @update:model-value="setReasoningEffortWildcard"
              >
                <SelectTrigger class="h-9">
                  <SelectValue placeholder="请选择" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="targetEffort in effortTargetOptions"
                    :key="targetEffort"
                    :value="targetEffort"
                  >
                    {{ targetEffort }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div
            v-else-if="formData.reasoningEffortMode === 'per_value'"
            class="rounded-md border divide-y"
          >
            <div
              v-for="effortKey in effortPerValueOrder"
              :key="effortKey"
              class="flex items-center gap-3 px-3 py-2"
            >
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium">
                  effort {{ effortKey }}
                </div>
                <div class="text-xs text-muted-foreground">
                  当请求 effort 为 {{ effortKey }} 时生效
                </div>
              </div>
              <div class="w-44 shrink-0">
                <Select
                  :model-value="getPerValueRuleValue(formData.reasoningEffortPerValueMap, effortKey)"
                  @update:model-value="setPerValueRuleValue('reasoningEffortPerValueMap', effortKey, $event)"
                >
                  <SelectTrigger class="h-9">
                    <SelectValue placeholder="不调整" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">不调整</SelectItem>
                    <SelectItem
                      v-for="targetEffort in effortTargetOptions"
                      :key="targetEffort"
                      :value="targetEffort"
                    >
                      {{ targetEffort }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>

        <div class="rounded-lg border p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-sm font-medium">
                输出详细度
              </div>
              <div class="text-xs text-muted-foreground">
                对应 <span class="font-mono">text.verbosity</span> / <span class="font-mono">verbosity</span>
              </div>
            </div>
            <div class="w-44 shrink-0">
              <Select
                :model-value="formData.verbosityMode"
                @update:model-value="setVerbosityMode"
              >
                <SelectTrigger class="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">不调整</SelectItem>
                  <SelectItem value="wildcard">通用覆盖</SelectItem>
                  <SelectItem value="per_value">逐项映射</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div
            v-if="formData.verbosityMode === 'wildcard'"
            class="flex items-center gap-3"
          >
            <div class="flex-1 text-sm text-muted-foreground">
              verbosity <span class="font-mono">*</span> 统一改为
            </div>
            <div class="w-44 shrink-0">
              <Select
                :model-value="formData.verbosityWildcard || '__none__'"
                @update:model-value="setVerbosityWildcard"
              >
                <SelectTrigger class="h-9">
                  <SelectValue placeholder="请选择" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem
                    v-for="targetVerbosity in verbosityTargetOptions"
                    :key="targetVerbosity"
                    :value="targetVerbosity"
                  >
                    {{ targetVerbosity }}
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div
            v-else-if="formData.verbosityMode === 'per_value'"
            class="rounded-md border divide-y"
          >
            <div
              v-for="verbosityKey in verbosityPerValueOrder"
              :key="verbosityKey"
              class="flex items-center gap-3 px-3 py-2"
            >
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium">
                  verbosity {{ verbosityKey }}
                </div>
                <div class="text-xs text-muted-foreground">
                  当请求 verbosity 为 {{ verbosityKey }} 时生效
                </div>
              </div>
              <div class="w-44 shrink-0">
                <Select
                  :model-value="getPerValueRuleValue(formData.verbosityPerValueMap, verbosityKey)"
                  @update:model-value="setPerValueRuleValue('verbosityPerValueMap', verbosityKey, $event)"
                >
                  <SelectTrigger class="h-9">
                    <SelectValue placeholder="不调整" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">不调整</SelectItem>
                    <SelectItem
                      v-for="targetVerbosity in verbosityTargetOptions"
                      :key="targetVerbosity"
                      :value="targetVerbosity"
                    >
                      {{ targetVerbosity }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button
        variant="outline"
        @click="$emit('update:open', false)"
      >
        取消
      </Button>
      <Button
        :disabled="submitting || !formData.modelId || selectedNames.length === 0"
        @click="handleSubmit"
      >
        <Loader2
          v-if="submitting"
          class="w-4 h-4 mr-2 animate-spin"
        />
        {{ editingGroup ? '保存' : '添加' }}
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Tag, Loader2, Plus, Search, Check, ChevronDown, RefreshCw, Zap } from 'lucide-vue-next'
import {
  Button,
  Input,
  Label,
  Dialog,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui'
import { useToast } from '@/composables/useToast'
import { parseApiError } from '@/utils/errorParser'
import {
  type Model,
  type ProviderModelAlias,
  type UpstreamModel,
} from '@/api/endpoints'
import { updateModel } from '@/api/endpoints/models'
import { useUpstreamModelsCache } from '../composables/useUpstreamModelsCache'

type OverrideMode = 'none' | 'wildcard' | 'per_value'

export interface AliasGroup {
  model: Model
  /** @deprecated */
  apiFormatsKey: string
  requestOverridesKey?: string
  /** @deprecated */
  apiFormats: string[]
  aliases: ProviderModelAlias[]
}

const props = defineProps<{
  open: boolean
  providerId: string
  models: Model[]
  editingGroup?: AliasGroup | null
  preselectedModelId?: string | null
  hasAutoFetchKey?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'saved': []
}>()

const { error: showError, success: showSuccess } = useToast()
const { fetchModels: fetchCachedModels } = useUpstreamModelsCache()

// 状态
const submitting = ref(false)
const loadingModels = ref(false)
const fetchingUpstreamModels = ref(false)
const upstreamModelsLoaded = ref(false)

// 搜索
const searchQuery = ref('')

// 折叠状态
const collapsedGroups = ref<Set<string>>(new Set())

// 上游模型
const upstreamModels = ref<UpstreamModel[]>([])

// 表单数据
const formData = ref<{
  modelId: string
  reasoningEffortMode: OverrideMode
  reasoningEffortWildcard: string
  reasoningEffortPerValueMap: Record<string, string>
  verbosityMode: OverrideMode
  verbosityWildcard: string
  verbosityPerValueMap: Record<string, string>
}>({
  modelId: '',
  reasoningEffortMode: 'none',
  reasoningEffortWildcard: '',
  reasoningEffortPerValueMap: {},
  verbosityMode: 'none',
  verbosityWildcard: '',
  verbosityPerValueMap: {}
})

const effortPerValueOrder = ['low', 'medium', 'high', 'xhigh'] as const
const effortTargetOptions = ['low', 'medium', 'high', 'xhigh'] as const
const verbosityPerValueOrder = ['low', 'medium', 'high'] as const
const verbosityTargetOptions = ['low', 'medium', 'high'] as const

// 选中的映射名称
const selectedNames = ref<string[]>([])

// 自定义名称列表（手动添加的）
const allCustomNames = ref<string[]>([])

// 所有已知名称集合
const allKnownNames = computed(() => {
  const set = new Set<string>()
  upstreamModels.value.forEach(m => set.add(m.id))
  return set
})

// 上游模型名称列表（去重后）
const upstreamModelNames = computed(() => {
  const names = new Set<string>()
  upstreamModels.value.forEach(m => {
    names.add(m.id)
  })
  return Array.from(names).sort()
})

// 自定义名称列表（排除上游模型中已有的）
const customNames = computed(() => {
  const upstreamSet = new Set(upstreamModelNames.value)
  return allCustomNames.value.filter(name => !upstreamSet.has(name))
})

// 排序后的自定义名称
const sortedCustomNames = computed(() => {
  const search = searchQuery.value.toLowerCase().trim()
  if (!search) return customNames.value

  const matched: string[] = []
  const unmatched: string[] = []
  for (const name of customNames.value) {
    if (name.toLowerCase().includes(search)) {
      matched.push(name)
    } else {
      unmatched.push(name)
    }
  }
  return [...matched, ...unmatched]
})

// 判断搜索内容是否可以作为自定义名称添加
const canAddAsCustom = computed(() => {
  const search = searchQuery.value.trim()
  if (!search) return false
  if (selectedNames.value.includes(search)) return false
  if (allCustomNames.value.includes(search)) return false
  if (allKnownNames.value.has(search)) return false
  return true
})

// 过滤后的上游模型
const filteredUpstreamModels = computed(() => {
  if (!searchQuery.value.trim()) return upstreamModelNames.value
  const query = searchQuery.value.toLowerCase()
  return upstreamModelNames.value.filter(name => name.toLowerCase().includes(query))
})

// 空状态判断
const showEmptyState = computed(() => {
  return filteredUpstreamModels.value.length === 0 && customNames.value.length === 0
})

// 上游模型是否全选
const isAllUpstreamModelsSelected = computed(() => {
  if (filteredUpstreamModels.value.length === 0) return false
  return filteredUpstreamModels.value.every(name => selectedNames.value.includes(name))
})

// 切换名称选中状态
function toggleName(name: string) {
  const idx = selectedNames.value.indexOf(name)
  if (idx === -1) {
    selectedNames.value.push(name)
  } else {
    selectedNames.value.splice(idx, 1)
  }
}

// 添加自定义名称
function addCustomName() {
  const name = searchQuery.value.trim()
  if (name && !selectedNames.value.includes(name)) {
    selectedNames.value.push(name)
    if (!allKnownNames.value.has(name) && !allCustomNames.value.includes(name)) {
      allCustomNames.value.push(name)
    }
    searchQuery.value = ''
  }
}

// 全选/取消全选上游模型
function toggleAllUpstreamModels() {
  const allNames = filteredUpstreamModels.value
  if (isAllUpstreamModelsSelected.value) {
    selectedNames.value = selectedNames.value.filter(name => !allNames.includes(name))
  } else {
    allNames.forEach(name => {
      if (!selectedNames.value.includes(name)) {
        selectedNames.value.push(name)
      }
    })
  }
}

// 切换折叠状态
function toggleGroupCollapse(group: string) {
  if (collapsedGroups.value.has(group)) {
    collapsedGroups.value.delete(group)
  } else {
    collapsedGroups.value.add(group)
  }
  collapsedGroups.value = new Set(collapsedGroups.value)
}

// 从提供商获取模型（使用缓存）
async function fetchUpstreamModels() {
  if (!props.providerId) return
  try {
    loadingModels.value = true
    fetchingUpstreamModels.value = true
    const result = await fetchCachedModels(props.providerId)
    if (result.models.length > 0) {
      upstreamModels.value = result.models
      upstreamModelsLoaded.value = true
      // 获取上游模型后，将不在上游列表中的已选名称添加到自定义列表
      const upstreamIds = new Set(result.models.map(m => m.id))
      const customFromSelected = selectedNames.value.filter(name => !upstreamIds.has(name))
      const mergedCustom = new Set([...allCustomNames.value, ...customFromSelected])
      allCustomNames.value = Array.from(mergedCustom).filter(name => !upstreamIds.has(name))
    }
    if (result.error) {
      showError(result.error, '获取上游模型失败')
    }
  } catch (err: unknown) {
    showError(parseApiError(err, '获取上游模型列表失败'), '错误')
  } finally {
    loadingModels.value = false
    fetchingUpstreamModels.value = false
  }
}

// 监听打开状态
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    initForm()
    if (props.hasAutoFetchKey) {
      await fetchUpstreamModels()
    }
  }
})

// 初始化表单
function initForm() {
  if (props.editingGroup) {
    const firstAlias = props.editingGroup.aliases[0]
    const reasoningEffortState = parseOverrideState(
      normalizeStringMap(firstAlias?.request_overrides?.reasoning_effort_map),
      effortPerValueOrder
    )
    const verbosityState = parseOverrideState(
      normalizeStringMap(firstAlias?.request_overrides?.verbosity_map),
      verbosityPerValueOrder
    )
    formData.value = {
      modelId: props.editingGroup.model.id,
      reasoningEffortMode: reasoningEffortState.mode,
      reasoningEffortWildcard: reasoningEffortState.wildcard,
      reasoningEffortPerValueMap: reasoningEffortState.perValueMap,
      verbosityMode: verbosityState.mode,
      verbosityWildcard: verbosityState.wildcard,
      verbosityPerValueMap: verbosityState.perValueMap
    }
    const existingNames = props.editingGroup.aliases.map(a => a.name)
    selectedNames.value = [...existingNames]
    allCustomNames.value = [...existingNames]
  } else {
    formData.value = {
      modelId: props.preselectedModelId || '',
      reasoningEffortMode: 'none',
      reasoningEffortWildcard: '',
      reasoningEffortPerValueMap: {},
      verbosityMode: 'none',
      verbosityWildcard: '',
      verbosityPerValueMap: {}
    }
    selectedNames.value = []
    allCustomNames.value = []
  }
  searchQuery.value = ''
  upstreamModels.value = []
  upstreamModelsLoaded.value = false
  collapsedGroups.value = new Set()
}

// 处理模型选择变更
function handleModelChange(value: string) {
  formData.value.modelId = value
}

function normalizeStringMap(
  input?: Record<string, unknown> | null
): Record<string, string> {
  if (!input || typeof input !== 'object') return {}

  const normalized: Record<string, string> = {}
  for (const [rawSource, rawTarget] of Object.entries(input)) {
    if (typeof rawTarget !== 'string') continue
    const source = rawSource.trim().toLowerCase()
    const target = rawTarget.trim().toLowerCase()
    if (!source || !target) continue
    normalized[source] = target
  }
  return normalized
}

function parseOverrideState(
  input: Record<string, string>,
  allowedKeys: readonly string[]
): {
  mode: OverrideMode
  wildcard: string
  perValueMap: Record<string, string>
} {
  const wildcard = input['*'] || ''
  const perValueMap: Record<string, string> = {}
  for (const key of allowedKeys) {
    if (input[key]) perValueMap[key] = input[key]
  }

  if (Object.keys(perValueMap).length > 0) {
    return {
      mode: 'per_value',
      wildcard: '',
      perValueMap
    }
  }

  if (wildcard) {
    return {
      mode: 'wildcard',
      wildcard,
      perValueMap: {}
    }
  }

  return {
    mode: 'none',
    wildcard: '',
    perValueMap: {}
  }
}

function buildOverrideMap(
  mode: OverrideMode,
  wildcard: string,
  perValueMap: Record<string, string>
): Record<string, string> {
  if (mode === 'wildcard' && wildcard) {
    return { '*': wildcard }
  }
  if (mode === 'per_value') {
    return normalizeStringMap(perValueMap)
  }
  return {}
}

function getPerValueRuleValue(map: Record<string, string>, key: string): string {
  return map[key] || '__none__'
}

function setPerValueRuleValue(
  field: 'reasoningEffortPerValueMap' | 'verbosityPerValueMap',
  key: string,
  value: string
) {
  const nextMap = { ...formData.value[field] }
  if (!value || value === '__none__') {
    delete nextMap[key]
  } else {
    nextMap[key] = value
  }
  formData.value[field] = nextMap
}

function setReasoningEffortMode(value: string) {
  formData.value.reasoningEffortMode = (value as OverrideMode) || 'none'
  if (formData.value.reasoningEffortMode !== 'wildcard') {
    formData.value.reasoningEffortWildcard = ''
  }
  if (formData.value.reasoningEffortMode !== 'per_value') {
    formData.value.reasoningEffortPerValueMap = {}
  }
}

function setReasoningEffortWildcard(value: string) {
  formData.value.reasoningEffortWildcard = value === '__none__' ? '' : value
}

function setVerbosityMode(value: string) {
  formData.value.verbosityMode = (value as OverrideMode) || 'none'
  if (formData.value.verbosityMode !== 'wildcard') {
    formData.value.verbosityWildcard = ''
  }
  if (formData.value.verbosityMode !== 'per_value') {
    formData.value.verbosityPerValueMap = {}
  }
}

function setVerbosityWildcard(value: string) {
  formData.value.verbosityWildcard = value === '__none__' ? '' : value
}

// 生成作用域唯一键
function getApiFormatsKey(formats: string[] | undefined): string {
  if (!formats || formats.length === 0) return ''
  return [...formats].sort().join(',')
}

function getRequestOverridesKey(alias: ProviderModelAlias): string {
  const reasoningEffortMap = normalizeStringMap(alias.request_overrides?.reasoning_effort_map)
  const verbosityMap = normalizeStringMap(alias.request_overrides?.verbosity_map)
  const entries = [
    ['reasoning_effort_map', Object.entries(reasoningEffortMap).sort(([a], [b]) => a.localeCompare(b))],
    ['verbosity_map', Object.entries(verbosityMap).sort(([a], [b]) => a.localeCompare(b))]
  ].filter(([, value]) => value.length > 0)
  if (entries.length === 0) return ''
  return JSON.stringify(entries)
}

// 提交表单
async function handleSubmit() {
  if (submitting.value) return
  if (!formData.value.modelId || selectedNames.value.length === 0) return

  submitting.value = true
  try {
    const targetModel = props.models.find(m => m.id === formData.value.modelId)
    if (!targetModel) {
      showError('模型不存在', '错误')
      return
    }

    const currentAliases = targetModel.provider_model_mappings || []
    let newAliases: ProviderModelAlias[]

    const buildAliases = (names: string[]): ProviderModelAlias[] => {
      const reasoningEffortMap = buildOverrideMap(
        formData.value.reasoningEffortMode,
        formData.value.reasoningEffortWildcard,
        formData.value.reasoningEffortPerValueMap
      )
      const verbosityMap = buildOverrideMap(
        formData.value.verbosityMode,
        formData.value.verbosityWildcard,
        formData.value.verbosityPerValueMap
      )
      const requestOverrides = {
        ...(Object.keys(reasoningEffortMap).length > 0 ? { reasoning_effort_map: reasoningEffortMap } : {}),
        ...(Object.keys(verbosityMap).length > 0 ? { verbosity_map: verbosityMap } : {})
      }
      return names.map((name) => ({
        name: name.trim(),
        priority: 1,
        ...(Object.keys(requestOverrides).length > 0 ? { request_overrides: requestOverrides } : {})
      }))
    }

    if (props.editingGroup) {
      const oldApiFormatsKey = props.editingGroup.apiFormatsKey
      const oldRequestOverridesKey = props.editingGroup.requestOverridesKey || ''
      const oldAliasNames = new Set(props.editingGroup.aliases.map(a => a.name))

      const filteredAliases = currentAliases.filter((a: ProviderModelAlias) => {
        const currentKey = getApiFormatsKey(a.api_formats)
        const currentRequestOverridesKey = getRequestOverridesKey(a)
        return !(
          currentKey === oldApiFormatsKey
          && currentRequestOverridesKey === oldRequestOverridesKey
          && oldAliasNames.has(a.name)
        )
      })

      const existingNames = new Set(filteredAliases.map((a: ProviderModelAlias) => a.name))
      const duplicates = selectedNames.value.filter(name => existingNames.has(name))
      if (duplicates.length > 0) {
        showError(`以下映射名称已存在：${duplicates.join(', ')}`, '错误')
        return
      }

      newAliases = [
        ...filteredAliases,
        ...buildAliases(selectedNames.value)
      ]
    } else {
      const existingNames = new Set(currentAliases.map((a: ProviderModelAlias) => a.name))
      const duplicates = selectedNames.value.filter(name => existingNames.has(name))
      if (duplicates.length > 0) {
        showError(`以下映射名称已存在：${duplicates.join(', ')}`, '错误')
        return
      }
      newAliases = [
        ...currentAliases,
        ...buildAliases(selectedNames.value)
      ]
    }

    await updateModel(props.providerId, targetModel.id, {
      provider_model_mappings: newAliases
    })

    showSuccess(props.editingGroup ? '映射组已更新' : '映射已添加')
    emit('update:open', false)
    emit('saved')
  } catch (err: unknown) {
    showError(parseApiError(err, '操作失败'), '错误')
  } finally {
    submitting.value = false
  }
}
</script>
