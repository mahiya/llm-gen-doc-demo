#!/bin/bash -e

# デプロイするリージョン(Document Intelligence 以外)
LOCATION="japaneast"

# リソース共通の名前の接尾辞
RESOURCE_POSTFIX=$(date | md5sum | head -c 6)

# Azure Resource Group
RESOURCE_GROUP_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"

# Azure Blob Storage
STORAGE_ACCOUNT_NAME="demollmdocgen$RESOURCE_POSTFIX"
STORAGE_CONTAINER_NAME="llm-doc-gen"

# Azure Cosmos DB
COSMOS_ACCOUNT_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"
COSMOS_DB_NAME="db"
COSMOS_DOCS_CONTAINER_NAME="llm-doc-gen-docs"
COSMOS_GROUPS_CONTAINER_NAME="llm-doc-gen-groups"

# Azure AI Search
AI_SEARCH_ACCOUNT_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"
AI_SEARCH_INDEX_NAME="llm-doc-gen"
AI_SEARCH_API_VERSION="2023-10-01-Preview"

# Azure Document Intelligence
DOC_INTELLIGENCE_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"

# Azure OpenAI Service
AZURE_OPENAI_RESOURCE_GROUP=""
AZURE_OPENAI_ACCOUNT_NAME=""
AZURE_OPENAI_CHAT_MODEL="gpt-4"
AZURE_OPENAI_EMBED_MODEL="text-embedding-3-large"

# Azure Container Registory
CONTAINER_REGISTORY_NAME="demollmdocgen$RESOURCE_POSTFIX"
FUNCTION_IMAGE_NAME="backend-function-app"
FUNCTION_IMAGE_VERSION="latest"
WEBAPP_IMAGE_NAME="frontend-web-app"
WEBAPP_IMAGE_VERSION="latest"

# Azure Application Insights
APP_INSIGHTS_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"

# Azure App Service Plan, Web Apps, Functions
APP_PLAN_NAME="demo-llm-doc-gen-$RESOURCE_POSTFIX"
FUNCTION_NAME="demo-llm-doc-gen-func-$RESOURCE_POSTFIX"
WEBAPP_NAME="demo-llm-doc-gen-web-$RESOURCE_POSTFIX"

# Azure CLI の拡張機能の動的インストールを有効にする
az config set extension.use_dynamic_install=yes_without_prompt

# リソースグループを作成する
az group create \
    --location $LOCATION \
    --resource-group $RESOURCE_GROUP_NAME

# Azure Blob Storage アカウントを作成する
az storage account create \
    --location $LOCATION \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $STORAGE_ACCOUNT_NAME \
    --sku Standard_LRS

# Azure Cosmos DB アカウントを作成する
az cosmosdb create \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $COSMOS_ACCOUNT_NAME \
    --default-consistency-level Eventual \
    --locations regionName="$LOCATION" failoverPriority=0 isZoneRedundant=False \
    --capabilities EnableServerless

# Azure Cosmos DB データベースを作成する
az cosmosdb sql database create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --name $COSMOS_DB_NAME

# Azure Cosmos DB コンテナを作成する
az cosmosdb sql container create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $COSMOS_DB_NAME \
    --name $COSMOS_DOCS_CONTAINER_NAME \
    --partition-key-path "/pk"
az cosmosdb sql container create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $COSMOS_DB_NAME \
    --name $COSMOS_GROUPS_CONTAINER_NAME \
    --partition-key-path "/pk"
az cosmosdb sql container create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --database-name $COSMOS_DB_NAME \
    --name "leases" \
    --partition-key-path "/id"

# Azure AI Search アカウントを作成する
az search service create \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $AI_SEARCH_ACCOUNT_NAME \
    --sku standard

# Azure AI Search アカウントのAPIアクセス制御方法を変更する
AI_SEARCH_MANAGED_ID=`az search service update \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $AI_SEARCH_ACCOUNT_NAME \
    --auth-options aadOrApiKey \
    --aad-auth-failure-mode http403 \
    --identity-type SystemAssigned \
    --query "identity.principalId" \
    --output tsv`

# Azure AI Search のインデックスを作成する
AI_SEARCH_ACCOUNT_KEY=`az search admin-key show --service-name $AI_SEARCH_ACCOUNT_NAME --resource-group $RESOURCE_GROUP_NAME --query 'primaryKey' --output tsv`
curl -X PUT https://$AI_SEARCH_ACCOUNT_NAME.search.windows.net/indexes/$AI_SEARCH_INDEX_NAME?api-version=2024-03-01-Preview \
    -H 'Content-Type: application/json' \
    -H 'api-key: '$AI_SEARCH_ACCOUNT_KEY \
    -d "$(sed -e "s|{{AZURE_OPENAI_ACCOUNT_NAME}}|https://$AZURE_OPENAI_ACCOUNT_NAME.openai.azure.com|; \
                  s|{{AZURE_OPENAI_EMBED_MODEL}}|$AZURE_OPENAI_EMBED_MODEL|;" \
                  "search/index.json")"

# Azure Document Intelligence アカウントを作成する
az cognitiveservices account create \
    --location "eastus" \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $DOC_INTELLIGENCE_NAME \
    --custom-domain $DOC_INTELLIGENCE_NAME \
    --kind "FormRecognizer" \
    --sku "S0"

# Azure Container Registry アカウントを作成する
az acr create \
    --location $LOCATION \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $CONTAINER_REGISTORY_NAME \
    --sku Standard

# Azure Application Insights アカウントを作成する
az monitor app-insights component create \
    --location $LOCATION \
    --resource-group $RESOURCE_GROUP_NAME \
    --app $APP_INSIGHTS_NAME

# Azure App Service プランを作成する
az appservice plan create \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $APP_PLAN_NAME \
    --is-linux \
    --number-of-workers 1 \
    --sku P1v2

# Functions のコードを Docker イメージをビルドして、Container Registry にプッシュする
az acr build \
    --registry $CONTAINER_REGISTORY_NAME \
    --image $FUNCTION_IMAGE_NAME:$FUNCTION_IMAGE_VERSION \
    --file ./function/Dockerfile ./function

# Azure Application Insights のインストルメンテーションキーを取得する
APP_INSIGHTS_INSTRUMENTATION_KEY=`az monitor app-insights component show \
    --resource-group $RESOURCE_GROUP_NAME \
    --app $APP_INSIGHTS_NAME \
    --query "instrumentationKey" \
    --output tsv`
    
# Azure Application Insights の接続文字列を取得する
APP_INSIGHTS_CONNECTION_STRING=`az monitor app-insights component show \
    --resource-group $RESOURCE_GROUP_NAME \
    --app $APP_INSIGHTS_NAME \
    --query "connectionString" \
    --output tsv`

# Azure Container Registry のパスワードを取得する
az acr update -n $CONTAINER_REGISTORY_NAME --admin-enabled true
CONTAINER_REGISTORY_PASSWORD=`az acr credential show --name $CONTAINER_REGISTORY_NAME --query "[passwords[0].value]" --output tsv`

# Azure Functions を作成する
az functionapp create \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $FUNCTION_NAME \
    --storage-account $STORAGE_ACCOUNT_NAME \
    --plan $APP_PLAN_NAME \
    --image "$CONTAINER_REGISTORY_NAME.azurecr.io/$FUNCTION_IMAGE_NAME:$FUNCTION_IMAGE_VERSION" \
    --registry-username $CONTAINER_REGISTORY_NAME \
    --registry-password $CONTAINER_REGISTORY_PASSWORD \
    --app-insights $APP_INSIGHTS_NAME \
    --app-insights-key $APP_INSIGHTS_INSTRUMENTATION_KEY \
    --functions-version 4 \
    --assign-identity [system]

# Azure Functions の環境変数を更新する
az functionapp config appsettings set \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $FUNCTION_NAME \
    --settings AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT_NAME \
               AZURE_STORAGE_CONTAINER_NAME=$STORAGE_CONTAINER_NAME \
               AZURE_COSMOS_CONNECTION__credential="managedidentity" \
               AZURE_COSMOS_CONNECTION__accountEndpoint="https://$COSMOS_ACCOUNT_NAME.documents.azure.com:443/" \
               AZURE_COSMOS_ACCOUNT_NAME=$COSMOS_ACCOUNT_NAME \
               AZURE_COSMOS_DB_NAME=$COSMOS_DB_NAME \
               AZURE_COSMOS_DOCS_CONTAINER_NAME=$COSMOS_DOCS_CONTAINER_NAME \
               AZURE_COSMOS_GROUPS_CONTAINER_NAME=$COSMOS_GROUPS_CONTAINER_NAME \
               AI_SEARCH_ACCOUNT_NAME=$AI_SEARCH_ACCOUNT_NAME \
               AI_SEARCH_INDEX_NAME=$AI_SEARCH_INDEX_NAME \
               AI_SEARCH_API_VERSION=$AI_SEARCH_API_VERSION \
               AZURE_OPENAI_ACCOUNT_NAME=$AZURE_OPENAI_ACCOUNT_NAME \
               AZURE_OPENAI_CHAT_MODEL=$AZURE_OPENAI_CHAT_MODEL \
               AZURE_OPENAI_EMBED_MODEL=$AZURE_OPENAI_EMBED_MODEL \
               AZURE_DOC_INTELLIGENCE_NAME=$DOC_INTELLIGENCE_NAME \
               APP_INSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CONNECTION_STRING

# Web Apps のコードを Docker イメージをビルドして、Container Registry にプッシュする
az acr build \
    --registry $CONTAINER_REGISTORY_NAME \
    --image $WEBAPP_IMAGE_NAME:$WEBAPP_IMAGE_VERSION \
    --file ./webapp/Dockerfile ./webapp

# Azure Web Apps を作成する
az webapp create \
    --resource-group $RESOURCE_GROUP_NAME \
    --plan $APP_PLAN_NAME \
    --name $WEBAPP_NAME \
    --deployment-container-image-name "$CONTAINER_REGISTORY_NAME.azurecr.io/$WEBAPP_IMAGE_NAME:$WEBAPP_IMAGE_VERSION" \
    --docker-registry-server-user $CONTAINER_REGISTORY_NAME \
    --docker-registry-server-password $CONTAINER_REGISTORY_PASSWORD \
    --assign-identity [system]

# Azure Web Apps の環境変数を更新する
az webapp config appsettings set \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $WEBAPP_NAME \
    --settings AZURE_STORAGE_ACCOUNT_NAME=$STORAGE_ACCOUNT_NAME \
               AZURE_STORAGE_CONTAINER_NAME=$STORAGE_CONTAINER_NAME \
               AZURE_COSMOS_ACCOUNT_NAME=$COSMOS_ACCOUNT_NAME \
               AZURE_COSMOS_DB_NAME=$COSMOS_DB_NAME \
               AZURE_COSMOS_DOCS_CONTAINER_NAME=$COSMOS_DOCS_CONTAINER_NAME \
               AZURE_COSMOS_GROUPS_CONTAINER_NAME=$COSMOS_GROUPS_CONTAINER_NAME \
               AI_SEARCH_ACCOUNT_NAME=$AI_SEARCH_ACCOUNT_NAME \
               AI_SEARCH_INDEX_NAME=$AI_SEARCH_INDEX_NAME \
               AI_SEARCH_API_VERSION=$AI_SEARCH_API_VERSION \
               AZURE_DOC_INTELLIGENCE_NAME=$DOC_INTELLIGENCE_NAME \
               APPINSIGHTS_INSTRUMENTATIONKEY=$APP_INSIGHTS_INSTRUMENTATION_KEY \
               APPLICATIONINSIGHTS_CONNECTION_STRING=$APP_INSIGHTS_CONNECTION_STRING

# サブスクリプションIDを取得する
SUBSCRIPTION_ID=`az account show --query id --output tsv`

# Azure Functions のマネージドIDを取得する
FUNCTION_MANAGED_ID=`az functionapp identity show \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $FUNCTION_NAME \
    --query principalId \
    --output tsv`

# Functions -> Storage のアクセス権限を付与する(Storage Blob Data Contributor)
az role assignment create \
    --role "Storage Blob Data Contributor" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME" \
    --assignee $FUNCTION_MANAGED_ID

# Functions -> Cosmos DB のアクセス権限を付与する(Cosmos DB 組み込みデータ共同作成者)
az cosmosdb sql role assignment create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --principal-id $FUNCTION_MANAGED_ID \
    --role-definition-name "Cosmos DB Built-in Data Contributor" \
    --scope "/"

# Functions -> AI Search のアクセス権限を付与する(Search Index Data Contributor)
az role assignment create \
    --role "Search Index Data Contributor" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Search/searchServices/$AI_SEARCH_ACCOUNT_NAME" \
    --assignee $FUNCTION_MANAGED_ID

# Functions -> Document Intelligence のアクセス権限を付与する(Cognitive Services User)
az role assignment create \
    --role "Cognitive Services User" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.CognitiveServices/accounts/$DOC_INTELLIGENCE_NAME" \
    --assignee $FUNCTION_MANAGED_ID

# Functions -> OpenAI Service のアクセス権限を付与する(Cognitive Services User)
az role assignment create \
    --role "Cognitive Services User" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AZURE_OPENAI_RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AZURE_OPENAI_ACCOUNT_NAME" \
    --assignee $FUNCTION_MANAGED_ID

# Azure Web Apps のマネージドIDを取得する
WEBAPP_MANAGED_ID=`az webapp identity show \
    --resource-group $RESOURCE_GROUP_NAME \
    --name $WEBAPP_NAME \
    --query principalId \
    --output tsv`

# Web Apps -> Storage のアクセス権限を付与する(Storage Blob Data Contributor)
az role assignment create \
    --role "Storage Blob Data Contributor" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT_NAME" \
    --assignee $WEBAPP_MANAGED_ID

# Web Apps -> Cosmos DB のアクセス権限を付与する(Cosmos DB 組み込みデータ共同作成者)
az cosmosdb sql role assignment create \
    --resource-group $RESOURCE_GROUP_NAME \
    --account-name $COSMOS_ACCOUNT_NAME \
    --principal-id $WEBAPP_MANAGED_ID \
    --role-definition-name "Cosmos DB Built-in Data Contributor" \
    --scope "/"

# Web Apps -> AI Search のアクセス権限を付与する(Search Index Data Contributor)
az role assignment create \
    --role "Search Index Data Contributor" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP_NAME/providers/Microsoft.Search/searchServices/$AI_SEARCH_ACCOUNT_NAME" \
    --assignee $WEBAPP_MANAGED_ID

# AI Search -> OpenAI Service のアクセス制御を付与する(Cognitive Services OpenAI User)
az role assignment create \
    --role "Cognitive Services OpenAI User" \
    --scope "subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AZURE_OPENAI_RESOURCE_GROUP/providers/Microsoft.CognitiveServices/accounts/$AZURE_OPENAI_ACCOUNT_NAME" \
    --assignee $AI_SEARCH_MANAGED_ID