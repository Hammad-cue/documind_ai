<template>
  <AmbientBackground />
  <router-view />
  <Toaster />
</template>

<script setup>
import AmbientBackground from './components/AmbientBackground.vue'
import Toaster from './components/Toaster.vue'
</script>
