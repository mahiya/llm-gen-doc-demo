<template>
  <div v-cloak class="container-fluid">
    <div class="row">
      <nav class="col-auto p-0">
        <NavBar></NavBar>
      </nav>
      <div class="col bg-light p-0">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script>
import NavBar from "./components/NavBarView.vue";

export default {
  components: {
    NavBar,
  },
};
</script>

<style scoped>
[v-cloak] {
  display: none;
}
</style>
