import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import axios from 'axios'
import VueAxios from 'vue-axios'

const app = createApp(App);

// アップロード日時を"yyyy/MM/dd HH:mm:ss"のフォーマットに変換する処理
app.config.globalProperties.$formatDate = function (date) {
    const d = new Date(date);
    const jstDate = new Date(d.getTime() + d.getTimezoneOffset() * 60 * 1000 + 9 * 60 * 60 * 1000);
    return `${jstDate.getFullYear()}/${('0' + (jstDate.getMonth() + 1)).slice(-2)}/${('0' + jstDate.getDate()).slice(-2)} ${('0' + jstDate.getHours()).slice(-2)}:${('0' + jstDate.getMinutes()).slice(-2)}:${('0' + jstDate.getSeconds()).slice(-2)}`;
};

// Web API エンドポイントの定義
app.config.globalProperties.$webApiEndpoint = process.env.NODE_ENV == "development"
    ? "http://127.0.0.1:80"
    : "";

app.use(router).use(VueAxios, axios).mount('#app')
