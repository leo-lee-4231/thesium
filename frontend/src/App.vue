<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">T</span>
        <span class="brand-text">
          <strong>Thesium</strong>
          <small>Your thesis, kept honest.</small>
        </span>
      </RouterLink>
      <nav class="nav">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
        <span class="phase-pill">P3 · thesis</span>
      </nav>
    </header>

    <main class="main">
      <RouterView />
    </main>

    <footer class="footer">
      <span>对话只读 · 不执行交易 · 不构成投资建议</span>
      <span class="mono">v0.1.0</span>
    </footer>
  </div>
</template>