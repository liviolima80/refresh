# REFRESH
This repository contains the source code and resources for REFRESH (Responsible Educational Friend Running Engaging Study Helper), a multi-agent system designed to help students track their study progress.

Built using the Google Agent Developer Kit (ADK), this project was submitted as a capstone for the 5-Day AI Agents Intensive Course with Google (https://www.kaggle.com/learn-guide/5-day-agents).

For a full detailed write-up, please visit the Kaggle Project Page (https://www.kaggle.com/competitions/agents-intensive-capstone-project/writeups/refresh-ai-project)

## Requirements:
**1) Docker & Docker Compose**

The project has been validated on the following setups:
- Windows: Docker v28.2.2 / Docker Compose v2.36.2
- Ubuntu 22.04: Docker v26.1.3 / Docker Compose v2.27.0
  
**2) Google Cloud Configuration**

You need an active Google Cloud project with the following resources:
- Cloud Storage Bucket
- Vertex AI RAG Corpus
- _Note: All resources must be deployed in the same region (e.g., europe-west8)._

**3) Database Tool**

- A PostgreSQL client (e.g., DBeaver) to inspect the database.

### <ins>Steps to configure Google Cloud</ins>
**1) Create a Project:**

   Go to the Google Cloud Console and create a new Project (e.g., refresh). Select this new project as your active project.
   
**2) Create a Storage Bucket:**

Navigate to Cloud Storage and create a new bucket (e.g., refresh-data-bucket).
   - Location type: Select "Region" (not Multi-region).
   - Region: Choose a specific region (e.g., europe-west8).
   - Leave all other settings at their defaults.

**3) Configure Vertex AI:**

Navigate to Vertex AI RAG Engine.
   - Enable the Vertex AI API if prompted.
   - Create a new RAG Corpus (e.g., refresh-data-corpus).
   - Region: Ensure you select the same region used for the Storage Bucket.
   - Skip the data import step for now and leave other options as default.
     
**4) Install the SDK:**

Install the gcloud CLI (https://docs.cloud.google.com/sdk/docs/install?hl=en)
    
**5) Run Terminal Commands:**
   - ensure you are logged in as a user who has Owner or Editor rights on the project
     ```
     gcloud auth login
     ```
   - Set Environment Variables
     ```
     export PROJECT_ID="refresh-xxxxx" (check the project id on Cloud Console)
     export SA_NAME="refresh-service-account"
     export SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
     export KEY_FILE="service-account-key.json"
     ```
   - Configure the active Project and Enable APIs
     ```
     gcloud config set project $PROJECT_ID #Set the active project
     gcloud services enable storage-api.googleapis.com storage-component.googleapis.com # Enable the Cloud Storage API
     ```
   - Create the Service Account
     ```
     gcloud iam service-accounts create $SA_NAME --description="Service account for Python GCS Tools" --display-name="GCS Tools Agent"
     ```
   - Grant Permissions
     ```
     gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/storage.admin"
     ```
   - Generate the JSON Key File
     ```
     gcloud iam service-accounts keys create $KEY_FILE --iam-account=$SA_EMAIL
     ```
   - Enable the Vertex AI API
     ```
     gcloud services enable aiplatform.googleapis.com
     ```
   - Grant Your Service Account Access to Vertex AI
     ```
     gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:${SA_EMAIL}" --role="roles/aiplatform.user"
     ```
   - Enable the Generative Language API
     ```
     gcloud services enable generativelanguage.googleapis.com --project=$PROJECT_ID
     ```
   - Create an API Key and check the uuid
     ```
     gcloud services api-keys create --display-name="Refresh Generative Language API Key" --project=$PROJECT_ID
     gcloud services api-keys list --project=$PROJECT_ID
     ```
   - Restrict the API Key so it can only be used for the Generative Language API
     ```
     gcloud services api-keys update ***YOUR_KEY_UID*** --api-targets=service=generativelanguage.googleapis.com --project=$PROJECT_ID
     ```
     

### <ins>Project configuration</ins>
Once the Google Cloud prerequisites above are met:
- **Service Account Key**: Move the service-account-key.json file you generated earlier into the adk/ directory.
- **Environment Variables**: Open the .env file located in the adk/ directory and update the variables with your Google Cloud Project ID and Region.
- **Database Config**: (Optional) If you wish to change the default database password, edit the config.yaml file.

## Test and Debug

The docker compose config file has been configured in order to expose the HTTP ports used by all the containers in order to enable the test of each individual service

1) PostgreSQL database:
   - Use DBeaver (or similar) to connect to the database at: 127.0.0.1:15432
   - Username: postgres
   - Password: The value configured in config.yaml
   - Verification: Ensure the refresh database exists and contains the students and sessions tables.
  
2) MCP Toolbox for Database
   - The MCP server is configured with the UI enabled.
   - Navigate to http://127.0.0.1:15000/ui to view and test the available tools.
  
3) Agent Engine
   - You can interact with the Agent Engine via an HTTP POST request to: http://127.0.0.1:18000/chat
   - Request model:
   ```
   class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
   ```
  - Response Format:
    ```
    JSON
    {
      "response": ### agent reply ###,  
      "session_id": ### session id to use in API requests ###,
      "user_id": ### user_id ###,
      "login_status": ### login status [ "True" / "False" ] ###
    }
    ```

4) Front End: The .NET frontend is accessible at: http://127.0.0.1:18888

5) Example images (in Italian text) are provided in 'images' folder

