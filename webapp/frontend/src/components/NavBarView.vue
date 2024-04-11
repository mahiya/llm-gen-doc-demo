<template>
  <div class="bg-dark text-white p-3 vh-100">
    <h1 class="text-white h5 me-3">
      <img src="@/assets/mslogo.png" />
      <span>Document Generator</span>
    </h1>

    <hr />

    <ul class="nav nav-pills flex-column mb-auto">
      <li class="nav-item">
        <router-link to="/" class="nav-link text-white" active-class="active" exact>
          <i class="bi bi-file-earmark-pdf-fill"></i>
          <span class="ps-2">リファレンスドキュメント</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/source" class="nav-link text-white" active-class="active" exact>
          <i class="bi bi-info-square-fill"></i>
          <span class="ps-2">情報源ドキュメント</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/generate" class="nav-link text-white" active-class="active" exact>
          <i class="bi bi-download"></i>
          <span class="ps-2">ドキュメント生成</span>
        </router-link>
      </li>
    </ul>

    <div id="loginUser" class="px-2 py-4">
      {{userName}}
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "NavBarView",
  data() {
    return {
      userId : "",
      userName: "",
    };
  },
  async mounted() {
    const resp = await axios.get(`${this.$webApiEndpoint}/api/user`);
    this.userId = resp.data.userId;
    this.userName = resp.data.userName;
  },
  methods: {
  },
};
</script>

<style scoped>
nav {
  width: 350px;
}

h1 img {
  height: 25px;
  position: relative;
  top: -2px;
  margin-right: 8px;
}

#loginUser {
  position: fixed;
  bottom: 0;
}
</style>
