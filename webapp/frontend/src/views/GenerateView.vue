<template>
  <div class="row p-0 m-0">

    <!-- 左エリア -->
    <div class="col p-3">
      
      <h2 class="h4 mb-3">生成したドキュメント</h2>
      
      <!-- ボタンエリア -->
      <div class="text-end">
        <button class="btn btn-primary" @click="listGeneratedDocs()">最新情報に更新</button>
        <button class="btn btn-primary ms-2" @click="showGenerateModal = true">新規生成</button>
        <button class="btn btn-danger ms-2" v-bind:disabled="!selectedGeneratedDoc" @click="showDeleteModal = true">削除</button>
      </div>

      <!-- 生成したドキュメント一覧のテーブル -->
      <table class="table table-hover" v-if="!loading">
        <thead>
          <tr>
            <th>リファレンスドキュメント</th>
            <th>情報源グループ</th>
            <th>状態</th>
            <th>作成日時</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="doc in generatedDocs"
            :key="doc.id"
            style="cursor: pointer"
            @click="selectedGeneratedDocId = doc.id"
            v-bind:class="{ 'table-active': selectedGeneratedDocId == doc.id }">
            <td>{{doc.reference_doc_name}}</td>
            <td>{{doc.source_group_name}}</td>
            <td>{{docStatusLabels[doc.status]}}</td>
            <td>{{$formatDate(doc.created_at)}}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!loading && generatedDocs.length == 0">ドキュメントが生成されていません</div>

      <!-- ドキュメント生成リクエストのモーダル -->
      <Teleport to="body">
        <Modal :show="showGenerateModal" @close="showGenerateModal = false">
          <template #headerTitle>ドキュメントの生成</template>
          <template #body>
            <div>
              <div class="mb-3">
                  <label for="referenceDoc" class="form-label">使用するリファレンスドキュメント</label>
                  <select id="referenceDoc" class="form-select" v-model="selectedReferenceDocId">
                      <option disabled value="">選択してください</option>
                      <option v-for="doc in referenceDocs" v-bind:key="doc.id" :value="doc.id">{{ doc.name }}</option>
                  </select>
              </div>
              <div class="mb-3">
                  <label for="sourceGroup" class="form-label">使用する情報源グループ</label>
                  <select id="sourceGroup" class="form-select" v-model="selectedGroupId">
                      <option disabled value="">選択してください</option>
                      <option v-for="group in groups" v-bind:key="group.id" :value="group.id">{{ group.name }}</option>
                  </select>
              </div>
            </div>
          </template>
          <template #footer>
            <button class="btn btn-primary" @click="startGenerateDocument()">ドキュメント生成を開始</button>
            <button type="button" class="btn btn-secondary" @click="showGenerateModal = false">閉じる</button>
          </template>
        </Modal>
      </Teleport>
      
      <!-- ドキュメント削除のモーダル -->
      <Teleport to="body">
        <Modal :show="showDeleteModal" @close="showDeleteModal = false">
          <template #headerTitle>ドキュメントの削除</template>
          <template #body>選択した生成したドキュメントを削除しますか？</template>
          <template #footer>
            <button type="button" class="btn btn-secondary me-2" @click="showDeleteModal = false">閉じる</button>
            <button type="button" class="btn btn-danger" @click="deleteGeneratedDoc()" v-bind:disabled="deleting">削除</button>
          </template>
        </Modal>
      </Teleport>
    </div>

    <!-- 右エリア -->
    <div class="col p-3 vh-100 generated-chapter-contents" v-if="selectedGeneratedDoc">
      <!-- ドキュメント生成の進捗状況表示 -->
      <div v-if="selectedGeneratedDoc.status != 'processed'">
        <div>{{progressMessage}}</div>
        <div class="progress">
          <div class="progress-bar progress-bar-striped progress-bar-animated" role="progressbar"
              v-bind:style="{ width: progress + '%' }"></div>
        </div>
      </div>
      <!-- ボタンエリア -->
      <div class="text-end" v-else>
        <button class="btn btn-primary" @click="downloadDocument()" v-bind:disabled="downloading">ダウンロード</button>
      </div>
      <!-- 生成されたドキュメントの内容を表示するエリア -->
      <div class="generated-chapter-content" v-for="chapter_title, i in selectedGeneratedDoc.chapter_titles" v-bind:key="i">
        <div v-if="selectedGeneratedDoc.generated_contents.length > i" 
             v-html="convertToHTML(selectedGeneratedDoc.generated_contents[i])">
        </div>
        <div v-else>
          <h1>{{chapter_title}}</h1>
        </div>
      </div>
      <!-- Loading アイコン -->
      <div class="text-center w-100" v-if="selectedGeneratedDoc.status == 'requested'">
          <div>
              <div class="spinner spinner-border text-secondary" role="status">
                  <span class="visually-hidden">Loading...</span>
              </div>
          </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.generated-chapter-contents {
  overflow-y: scroll; 
  border-left: 1px solid #f0f0f0;
}
</style>

<script>
import axios from "axios";
import Modal from "../components/ModalView.vue";
import { marked } from "marked"

export default {
  name: "GenerateView",
  components: {
    Modal
  },
  data() {
    return {
      loading: false,
      generatedDocs: [],
      referenceDocs: [],
      groups: [],
      selectedGeneratedDocId: null,
      selectedGeneratedDoc: null,
      selectedReferenceDocId: null,
      selectedGroupId: null,
      showGenerateModal: false,
      showDeleteModal: false,
      deleting: false,
      docStatusLabels: {
        requested: "リクエスト済み",
        generating: "生成中",
        processed: "生成済み",
      },
      progressMessage: "",
      downloading: false,
      timer: null,
    };
  },
  watch: {
    // 生成ドキュメント一覧でドキュメントが選択された時の処理
    selectedGeneratedDocId: async function() {
      if(this.selectedGeneratedDocId) {
        this.selectedGeneratedDoc = await this.getGeneratedDoc(this.selectedGeneratedDocId);
      } else {
        this.selectedGeneratedDoc = null;
      }
    },
    // 生成中のドキュメントの場合、定期的に状態を更新するタイマーを起動する
    selectedGeneratedDoc: function() {
      if(this.selectedGeneratedDoc 
        && (this.selectedGeneratedDoc.status == "requested" || this.selectedGeneratedDoc.status == "generating"))
      {
        if(this.timer == null) {
          this.timer = setInterval(async () => {
            this.selectedGeneratedDoc = await this.getGeneratedDoc(this.selectedGeneratedDocId);
          }, 3000);
        }
        return;
      }
      
      // 生成中でない場合はタイマーを停止する
      clearInterval(this.timer);
        this.timer = null;
      }
  },
  computed: {
    progress: function() {
      if(!this.selectedGeneratedDoc) return 0;
      if(this.selectedGeneratedDoc.status == "requested") {
        this.progressMessage = `各章のテキストを生成しています`
        return 0;
      }
      if(this.selectedGeneratedDoc.status == "generating") {
        if(!this.selectedGeneratedDoc.chapter_titles) return 0;
        const total = this.selectedGeneratedDoc.chapter_titles.length;
        const generated = this.selectedGeneratedDoc.generated_contents.length;
        this.progressMessage = `各章のテキストを生成しています (${generated}/${total})`
        return generated / total * 100;
      }
      if(this.selectedGeneratedDoc.status == "processed") return 100;
    }
  },
  async mounted() {
    this.listGeneratedDocs();
    this.listReferenceDocs();
    this.listGroups();
  },
  methods: {
    // 生成したドキュメント一覧を取得する
    listGeneratedDocs: async function () {
      this.loading = true;
      const url = `${this.$webApiEndpoint}/api/generated`;
      const resp = await axios.get(url);
      this.generatedDocs = resp.data;
      this.loading = false;
      if (this.generatedDocs.length > 0) {
        this.selectedGeneratedDocId = this.generatedDocs[0].id;
      }
    },
    // 選択中の生成ドキュメントを再取得する
    getGeneratedDoc: async function(docId) {
      const url = `${this.$webApiEndpoint}/api/generated/${docId}`;
      const resp = await axios.get(url);
      return resp.data;
    },
    // リファレンスドキュメント一覧を取得する
    listReferenceDocs: async function () {
      const url = `${this.$webApiEndpoint}/api/reference`;
      const resp = await axios.get(url);
      this.referenceDocs = resp.data;
      if(this.referenceDocs.length > 0)
        this.selectedReferenceDocId = this.referenceDocs[0].id;
    },
    // グループ一覧を取得する
    listGroups: async function () {
      const url = `${this.$webApiEndpoint}/api/sourceGroup`;
      const resp = await axios.get(url);
      this.groups = resp.data;
      if(this.groups.length > 0)
        this.selectedGroupId = this.groups[0].id;
    },
    // ドキュメント生成を開始する
    startGenerateDocument: async function() {
      const url = `${this.$webApiEndpoint}/api/generated`;
      const data = {
        referenceDocId: this.selectedReferenceDocId,
        sourceGroupId: this.selectedGroupId
      };
      await axios.post(url, data);
      this.showGenerateModal = false;
      await this.listGeneratedDocs();
    },
    // 指定したドキュメントを削除する
    deleteGeneratedDoc: async function() {
      if (!this.selectedGeneratedDocId) return;
      this.deleting = true;
      const url = `${this.$webApiEndpoint}/api/generated/${this.selectedGeneratedDocId}`;
      await axios.delete(url);
      this.deleting = false;
      this.showDeleteModal = false;
      this.selectedGeneratedDocId = null;
      this.listGeneratedDocs();
    },    
    // Markdown形式のドキュメントの内容をHTML形式に変換する
    convertToHTML: function(text) {
      return marked(text);
    },
    // ドキュメントをWord形式でダウンロードする
    downloadDocument: async function() {
      this.downloading = true;
      const url = `${this.$webApiEndpoint}/api/generated/${this.selectedGeneratedDoc.id}/download`;
      const resp = await axios.get(url);
      const downloadUrl = resp.data;
      window.open(downloadUrl, '_blank');
      this.downloading = false;
    }
  },
};
</script>