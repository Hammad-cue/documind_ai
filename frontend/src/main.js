import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './style.css'

/** v-inview: the element rises in the first time it scrolls into view (see .inview in style.css). */
const inview = {
  mounted(el) {
    el.classList.add('inview')
    if (!('IntersectionObserver' in window)) { el.classList.add('is-in'); return }
    const io = new IntersectionObserver(entries => {
      for (const e of entries) {
        if (e.isIntersecting) { el.classList.add('is-in'); io.disconnect() }
      }
    }, { threshold: 0.12 })
    io.observe(el)
    el._inview = io
  },
  unmounted(el) { el._inview?.disconnect() },
}

createApp(App).use(router).directive('inview', inview).mount('#app')
