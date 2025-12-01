import vertexai
from vertexai import rag
from vertexai.rag.utils import resources
from typing import Dict, Optional, Any
import os
from dotenv import load_dotenv
from google.cloud import storage

from google.adk.tools import FunctionTool

from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.generative_models import Tool, grounding

import google.cloud.aiplatform
print(f"Current version: {google.cloud.aiplatform.__version__}")

load_dotenv()
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
DEFAULT_CORPUS_NAME = os.getenv("DEFAULT_CORPUS_NAME")
DEFAULT_BUCKET_NAME = os.getenv("DEFAULT_BUCKET_NAME")
DEFAULT_CORPUS_ID = os.getenv("DEFAULT_CORPUS_ID")

PARSING_MODEL = "gemini-2.5-flash-lite"

RAG_CORPUS = f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}/ragCorpora/{DEFAULT_CORPUS_ID}"

# Initialize Vertex AI API
vertexai.init(project=GOOGLE_CLOUD_PROJECT_ID, location=GOOGLE_CLOUD_LOCATION)

def list_rag_corpora() -> Dict[str, Any]:
    """
    Lists all RAG corpora in the current project and location.
    
    Returns:
        A dictionary containing the list of corpora:
        - status: "success" or "error"
        - corpora: List of corpus objects with id, name, and display_name
        - count: Number of corpora found
        - error_message: Present only if an error occurred
    """
    try:
        corpora = rag.list_corpora()
        
        corpus_list = []
        for corpus in corpora:
            corpus_id = corpus.name.split('/')[-1]
            
            # Get corpus status
            status = None
            if hasattr(corpus, "corpus_status") and hasattr(corpus.corpus_status, "state"):
                status = corpus.corpus_status.state
            elif hasattr(corpus, "corpusStatus") and hasattr(corpus.corpusStatus, "state"):
                status = corpus.corpusStatus.state
            
            # Make an explicit API call to count files
            files_count = 0
            try:
                # List all files to get the count
                files_response = rag.list_files(corpus_name=corpus.name)
                
                if hasattr(files_response, "rag_files"):
                    files_count = len(files_response.rag_files)
            except Exception:
                # If counting files fails, continue with zero count
                pass
            
            corpus_list.append({
                "id": corpus_id,
                "name": corpus.name,
                "display_name": corpus.display_name,
                "description": corpus.description if hasattr(corpus, "description") else None,
                "create_time": str(corpus.create_time) if hasattr(corpus, "create_time") else None,
                "files_count": files_count,
                "status": status
            })
        
        return {
            "status": "success",
            "corpora": corpus_list,
            "count": len(corpus_list),
            "message": f"Found {len(corpus_list)} RAG corpora"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list RAG corpora: {str(e)}"
        }

def retrieve_context(query: str) -> str:
    """
    Retrieve context from the RAG engine based on the query.
    
    Args:
        query: The query to search for.
        corpus_name: The name of the corpus to search in.
        
    Returns:
        The retrieved context as a string.
    """
    try:

        retrival_config = resources.RagRetrievalConfig(top_k=5)

        response = rag.retrieval_query(
            rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS)],
            text=query
        )
        
        # Format the retrieved context
        context = ""
        if response.contexts and response.contexts.contexts:
            print("found relevant context")
            for i, ctx in enumerate(response.contexts.contexts):
                context += f"Context {i+1}:\n{ctx.text}\n\n"
        else:
            context = "No relevant context found."
            
        return context

    except Exception as e:
        return f"Error retrieving context: {str(e)}"

# Function for importing documents into a RAG corpus
def import_document_to_corpus( corpus_id: str, bucket_name: str, file_name: str) -> Dict[str, Any]:
    """
    Imports a document from Google Cloud Storage into a RAG corpus.
    Uses the minimal required parameters to avoid any compatibility issues.
    
    Args:
        corpus_id: The ID of the corpus to import the document into
        gcs_uri: GCS path of the document to import (gs://bucket-name/file-name)
    
    Returns:
        A dictionary containing:
        - status: "success" or "error"
        - corpus_id: The ID of the corpus
        - message: Status message
    """
    try:
        # Construct full corpus name
        corpus_name = f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}/ragCorpora/{corpus_id}"
        gcs_uri = f"gs://{bucket_name}/{file_name}"
        
        print(corpus_name)
        print(gcs_uri)

        # Import document with minimal configuration
        # Use the most basic form of the API call to avoid parameter issues

        # Create the configuration object first for clarity
        chunking = rag.ChunkingConfig(
            chunk_size=1024,
            chunk_overlap=200
        )

        # Define the LLM Parser Configuration
        # This tells Vertex AI to use a Generative Model to read the file
        llm_parser = rag.LlmParserConfig(
            model_name=PARSING_MODEL,
            max_parsing_requests_per_min=100  # Throttle to avoid hitting GenAI quotas
        )

        transformation = rag.TransformationConfig(
            chunking_config=chunking
        )

        result = rag.import_files(
            corpus_name,
            [gcs_uri], # Single path in a list
            transformation_config=transformation ,
            llm_parser=llm_parser,
        )

        print(f"------------ RESULT ------------")
        print(f"Successfully Imported: {result.imported_rag_files_count}")
        print(f"Failed to Import:      {result.failed_rag_files_count}")
        print(f"Skipped:               {result.skipped_rag_files_count}")
        print(f"-----------------------------")
        if result.failed_rag_files_count > 0:
            print("ERROR: The Vertex AI Service Agent failed to import.")

        # Return success result
        return {
            "status": "success",
            "corpus_id": corpus_id,
            "message": f"Successfully imported document {gcs_uri} to corpus '{corpus_id}'"
        }
    except Exception as e:
        return {
            "status": "error",
            "corpus_id": corpus_id,
            "error_message": str(e),
            "message": f"Failed to import document: {str(e)}"
        }

def verify_corpus_files(corpus_id: str):
    corpus_name = f"projects/{GOOGLE_CLOUD_PROJECT_ID}/locations/{GOOGLE_CLOUD_LOCATION}/ragCorpora/{corpus_id}"
    
    print(f"Checking files in: {corpus_name}")
    
    # List all files in the corpus
    files = rag.list_files(corpus_name=corpus_name)
    
    count = 0
    for f in files:
        count += 1
        print(f"Found file: {f.display_name} (ID: {f.name})")
        
    if count == 0:
        print("No files found in this corpus.")
    else:
        print(f"Total files verified: {count}")

import_document_to_corpus_tool = FunctionTool(func=import_document_to_corpus)
retrieve_context_tool = FunctionTool(func=retrieve_context)

def check_file_status(uri: str):
    if not uri.startswith("gs://"):
        print("❌ Error: URI must start with gs://")
        return

    parts = uri[5:].split("/", 1)
    bucket_name = parts[0]
    blob_name = parts[1]

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Check if file exists and gather stats
        blob.reload() 
        print(f"✅ File Found: {blob_name}")
        print(f"   Size: {blob.size} bytes")
        print(f"   Content Type: {blob.content_type}")
        
        if blob.size == 0:
            print("❌ FAILURE REASON: The file is empty (0 bytes).")
        else:
            print("✅ File looks valid. The issue is likely hidden in Cloud Logs.")

    except Exception as e:
        print(f"❌ Error finding file: {e}")
        print("Double check the bucket and file name.")

if __name__ == "__main__":
    print(list_rag_corpora())
    print("-----------------------------------------------------------")
    check_file_status("gs://"+DEFAULT_BUCKET_NAME+"/book2.jpg")
    print("-----------------------------------------------------------")
    print(import_document_to_corpus(DEFAULT_CORPUS_ID, DEFAULT_BUCKET_NAME, "book2.jpg"))
    print("-----------------------------------------------------------")
    print(verify_corpus_files(DEFAULT_CORPUS_ID))
    print("-----------------------------------------------------------")
