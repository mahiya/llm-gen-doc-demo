<template>
  <div class="row p-0 m-0">

    <!-- 左エリア -->
    <div class="col p-3 vh-100">

      <h2 class="h4 mb-3">リファレンスドキュメント</h2>
      
      <!-- ボタンエリア -->
      <div class="text-end">
        <button class="btn btn-primary" @click="listDocs()">最新情報に更新</button>
        <button class="btn btn-primary ms-2" @click="showUploadModal = true">アップロード</button>
        <button class="btn btn-danger ms-2" v-bind:disabled="!selectedDoc" @click="showDeleteModal = true">削除</button>
      </div>

      <!-- ドキュメント一覧のテーブル -->
      <table class="table table-hover" v-if="!loading">
        <thead>
          <tr>
            <th>ファイル名</th>
            <th>状態</th>
            <th>作成日時</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in docs"
            :key="doc.id"
            style="cursor: pointer"
            @click="selectedDoc = doc"
            v-bind:class="{ 'table-active': selectedDoc && selectedDoc.id == doc.id }"
          >
            <td>
              <img class="me-1 fileIcon" v-bind:src="`icons/${doc.file_extention}.svg`" />
              <span>{{doc.name}}</span>
            </td>
            <td>{{docStatusLabels[doc.status]}}</td>
            <td>{{$formatDate(doc.created_at)}}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="!loading && docs.length == 0">ドキュメントがアップロードされていません</div>

      <!-- Loading アイコン -->
      <div class="text-center w-100" v-if="loading">
        <div>
          <div class="spinner spinner-border text-secondary" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>

      <!-- ドキュメントアップロードのモーダル -->
      <Teleport to="body">
        <Modal :show="showUploadModal" @close="showUploadModal = false">
          <template #headerTitle>ドキュメントのアップロード</template>
          <template #body>
            <div>
              <input type="file" @change="uploadDoc" class="form-control" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.html,application/pdf,application/msword,application/vnd.ms-excel,application/vnd.ms-powerpoint,text/html" />
            </div>
          </template>
          <template #footer>
            <button type="button" class="btn btn-secondary" @click="showUploadModal = false">閉じる</button>
          </template>
        </Modal>
      </Teleport>
      
      <!-- ドキュメント削除のモーダル -->
      <Teleport to="body">
        <Modal :show="showDeleteModal" @close="showDeleteModal = false">
          <template #headerTitle>ドキュメントの削除</template>
          <template #body>選択したドキュメント "{{selectedDoc.name}}" を削除しますか？</template>
          <template #footer>
            <button type="button" class="btn btn-secondary me-2" @click="showDeleteModal = false">閉じる</button>
            <button type="button" class="btn btn-danger" @click="deleteDoc()" v-bind:disabled="deleting">削除</button>
          </template>
        </Modal>
      </Teleport>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Modal from "../components/ModalView.vue";

export default {
  name: "GenerateView",
  components: {
    Modal,
  },
  data() {
    return {
      loading: false,
      docs: [],
      selectedDoc: null,
      docStatusLabels: {
        uploaded: "アップロード済み",
        text_extracted: "テキスト抽出済み",
        chapter_titles_extracted: "章情報抽出済み",
        processed: "処理済み",
      },
      showUploadModal: false,
      showDeleteModal: false,
      deleting : false,
    };
  },
  async mounted() {
    await this.listDocs();
  },
  methods: {
    // ドキュメント一覧を取得する
    listDocs: async function () {
      this.loading = true;
      const url = `${this.$webApiEndpoint}/api/reference`;
      const resp = await axios.get(url);
      this.loading = false;
      this.docs = resp.data;
    },
    // ドキュメントをアップロードする
    uploadDoc: async function (e) {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      const headers = { "Content-Type": "multipart/form-data" };
      await axios.post(`${this.$webApiEndpoint}/api/reference/upload`, formData, { headers });

      this.showUploadModal = false;
      await this.listDocs();
    },
    // 指定したドキュメントを削除する
    deleteDoc: async function() {
      this.deleting = true;
      const url = `${this.$webApiEndpoint}/api/reference/${this.selectedDoc.id}`;
      await axios.delete(url);
      this.deleting = false;
      
      this.showDeleteModal = false;
      await this.listDocs();
    }
  },
};
</script>
