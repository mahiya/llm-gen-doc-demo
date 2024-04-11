<template>
  <div class="row p-0 m-0">

    <!-- 左エリア -->
    <div class="col p-3 vh-100">

      <h2 class="h4 mb-3">情報源グループ</h2>
      
      <!-- ボタンエリア -->
      <div class="text-end">
        <button class="btn btn-primary" @click="listGroups()">最新情報に更新</button>
        <button class="btn btn-primary ms-2" @click="showGroupCreateModal = true">作成</button>
        <button class="btn btn-danger ms-2" v-bind:disabled="!selectedGroup" @click="showGroupDeleteModal = true">削除</button>
      </div>

      <!-- グループ一覧のテーブル -->
      <table class="table table-hover" v-if="!loadingGroup">
        <thead>
          <tr>
            <th>名前</th>
            <th>作成日時</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="group in groups"
            :key="group.id"
            style="cursor: pointer"
            @click="selectedGroup = group"
            v-bind:class="{ 'table-active': selectedGroup && selectedGroup.id == group.id }">
            <td>{{group.name}}</td>
            <td>{{$formatDate(group.created_at)}}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="!loadingGroup && groups.length == 0">グループが作成されていません</div>

      <!-- Loading アイコン -->
      <div class="text-center w-100" v-if="loadingGroup">
        <div>
          <div class="spinner spinner-border text-secondary" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>

      <!-- グループアップロードのモーダル -->
      <Teleport to="body">
        <Modal :show="showGroupCreateModal" @close="showGroupCreateModal = false">
          <template #headerTitle>グループの作成</template>
          <template #body>
            <div>
              <label for="groupName">名前</label>
              <input id="groupName" type="text" class="form-control" v-model="creatingGroupName" />
            </div>
          </template>
          <template #footer>
            <button type="button" class="btn btn-primary" @click="createGroup()">作成</button>
            <button type="button" class="btn btn-secondary" @click="showGroupCreateModal = false">閉じる</button>
          </template>
        </Modal>
      </Teleport>
      
      <!-- グループ削除のモーダル -->
      <Teleport to="body">
        <Modal :show="showGroupDeleteModal" @close="showGroupDeleteModal = false">
          <template #headerTitle>グループの削除</template>
          <template #body>選択したグループ "{{selectedGroup.name}}" を削除しますか？</template>
          <template #footer>
            <button type="button" class="btn btn-secondary me-2" @click="showGroupDeleteModal = false">閉じる</button>
            <button type="button" class="btn btn-danger" @click="deleteGroup(selectedGroup)" v-bind:disabled="deleting">削除</button>
          </template>
        </Modal>
      </Teleport>
    </div>
    
    <!-- 右エリア -->
    <div class="col p-3" v-if="selectedGroup">
      
      <h2 class="h4 mb-3">情報源ドキュメント</h2>
      
      <!-- ボタンエリア -->
      <div class="text-end">
        <button class="btn btn-primary" @click="listDocs()">最新情報に更新</button>
        <button class="btn btn-primary ms-2" @click="showDocUploadModal = true">アップロード</button>
        <button class="btn btn-danger ms-2" v-bind:disabled="!selectedDoc" @click="showDocDeleteModal = true">削除</button>
      </div>

      <!-- ドキュメント一覧のテーブル -->
      <table class="table table-hover" v-if="!loadingDocs">
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

      <div v-if="!loadingDocs && docs.length == 0">ドキュメントがアップロードされていません</div>

      <!-- Loading アイコン -->
      <div class="text-center w-100" v-if="loadingDocs">
        <div>
          <div class="spinner spinner-border text-secondary" role="status">
            <span class="visually-hidden">Loading...</span>
          </div>
        </div>
      </div>

      <!-- ドキュメントアップロードのモーダル -->
      <Teleport to="body">
        <Modal :show="showDocUploadModal" @close="showDocUploadModal = false">
          <template #headerTitle>ドキュメントのアップロード</template>
          <template #body>
            <div>
              <input type="file" @change="uploadDoc" class="form-control" accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.html,application/pdf,application/msword,application/vnd.ms-excel,application/vnd.ms-powerpoint,text/html" />
            </div>
          </template>
          <template #footer>
            <button type="button" class="btn btn-secondary" @click="showDocUploadModal = false">閉じる</button>
          </template>
        </Modal>
      </Teleport>
      
      <!-- ドキュメント削除のモーダル -->
      <Teleport to="body">
        <Modal :show="showDocDeleteModal" @close="showDocDeleteModal = false">
          <template #headerTitle>ドキュメントの削除</template>
          <template #body>選択したドキュメント "{{selectedDoc.name}}" を削除しますか？</template>
          <template #footer>
            <button type="button" class="btn btn-secondary me-2" @click="showDocDeleteModal = false">閉じる</button>
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
  name: "SourceView",
  components: {
    Modal,
  },
  data() {
    return {
      loadingGroup: false,
      groups: [],
      selectedGroup: null,
      creatingGroupName: "",
      showGroupCreateModal: false,
      showGroupDeleteModal: false,
      loadingDocs: false,
      docs: [],
      selectedDoc: null,
      docStatusLabels: {
        uploaded: "アップロード済み",
        text_extracted: "テキスト抽出済み",
        chapter_titles_extracted: "章情報抽出済み",
        processed: "処理済み",
      },
      showDocUploadModal: false,
      showDocDeleteModal: false,
      deleting: false,
    };
  },
  async mounted() {
    await this.listGroups();
  },
  watch: {
    selectedGroup: async function() {
      await this.listDocs();
    },
  },
  methods: {
    // グループ一覧を取得する
    listGroups: async function () {
      this.loadingGroup = true;
      const url = `${this.$webApiEndpoint}/api/sourceGroup`;
      const resp = await axios.get(url);
      this.loadingGroup = false;
      this.groups = resp.data;

      // グループが１つ以上作成されている場合は、一番上のグループを選択された状態にする
      if (this.groups.length > 0) {
        this.selectedGroup = this.groups[0];
      }
    },
    // グループを作成する
    createGroup: async function() {
      const url = `${this.$webApiEndpoint}/api/sourceGroup`;
      await axios.post(url, { name: this.creatingGroupName });
      this.showGroupCreateModal = false;
      this.listGroups(); // グループ一覧を再取得する
    },
    // 指定したグループを削除する処理
    deleteGroup: async function(group) {
      this.deleting = true;     
      const url = `${this.$webApiEndpoint}/api/sourceGroup/${group.id}`;
      await axios.delete(url);
      this.deleting = false;
      this.selectedGroup = null;
      this.selectedDoc = null;
      this.showGroupDeleteModal = false;
      this.listGroups(); // グループ一覧を再取得する
    },
    // 情報源ドキュメント一覧を取得する
    listDocs: async function () {
      this.loadingDocs = true;
      const url = `${this.$webApiEndpoint}/api/sourceGroup/${this.selectedGroup.id}/source`;
      const resp = await axios.get(url);
      this.loadingDocs = false;
      this.docs = resp.data;
    },
    // 情報源ドキュメントをアップロードする
    uploadDoc: async function (e) {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      const headers = { "Content-Type": "multipart/form-data" };
      await axios.post(`${this.$webApiEndpoint}/api/sourceGroup/${this.selectedGroup.id}/source/upload`, formData, { headers });

      this.showDocUploadModal = false;
      await this.listDocs();
    },
    // 指定したドキュメントを削除する
    deleteDoc: async function() {
      this.deleting = true;
      const url = `${this.$webApiEndpoint}/api/sourceGroup/${this.selectedGroup.id}/source/${this.selectedDoc.id}`;
      await axios.delete(url);
      this.deleting = false;
      this.showDocDeleteModal = false;
      await this.listDocs();
    }
  },
};
</script>

<style scoped></style>