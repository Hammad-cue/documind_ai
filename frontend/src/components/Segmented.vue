<template>
  <div ref="root" role="tablist" :aria-label="label" class="glass-soft relative inline-flex rounded-[14px] p-1">
    <!-- the white thumb glides to the selected option -->
    <span aria-hidden="true" class="absolute top-1 bottom-1 rounded-[10px] bg-white shadow-[0_2px_8px_rgb(28_38_90/0.1),inset_0_1px_0_white] transition-[left,width] duration-300 ease-[var(--ease-out)]"
          :style="{ left: `${thumb.left}px`, width: `${thumb.width}px`, opacity: thumb.width ? 1 : 0 }" />
    <button v-for="o in options" :key="o.value" ref="buttons" type="button" role="tab" :aria-selected="modelValue === o.value"
            @click="emit('update:modelValue', o.value)"
            :class="['relative z-10 min-h-9 rounded-[10px] px-4 text-sm whitespace-nowrap transition-colors duration-200',
                     modelValue === o.value ? 'font-semibold text-ink' : 'text-ink-2 hover:text-ink']">
      {{ o.label }}
    </button>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

const props = defineProps({ modelValue: [String, Number], options: Array, label: String })
const emit = defineEmits(['update:modelValue'])
const root = ref(null)
const buttons = ref([])
const thumb = reactive({ left: 0, width: 0 })

async function place() {
  await nextTick()
  const i = props.options.findIndex(o => o.value === props.modelValue)
  const el = buttons.value[i]
  if (!el) { thumb.width = 0; return }
  thumb.left = el.offsetLeft
  thumb.width = el.offsetWidth
}

let ro = null
onMounted(() => {
  place()
  ro = new ResizeObserver(place)
  ro.observe(root.value)
  document.fonts?.ready.then(place)
})
onBeforeUnmount(() => ro?.disconnect())
watch(() => [props.modelValue, props.options.map(o => o.label).join('|')], place)
</script>
