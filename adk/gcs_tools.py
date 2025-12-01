from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError
from google.adk.tools import FunctionTool
from typing import Dict, Any, Optional
import os
from dotenv import load_dotenv

load_dotenv()
GCS_LIST_BUCKETS_MAX_RESULTS = int(os.getenv("GCS_LIST_BUCKETS_MAX_RESULTS"))
GCS_LIST_BLOBS_MAX_RESULTS = int(os.getenv("GCS_LIST_BLOBS_MAX_RESULTS"))
GOOGLE_CLOUD_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Tools definition for Google Cloud Storage Interaction

def list_gcs_buckets(
    prefix: Optional[str] = None,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    """
    Lists Google Cloud Storage buckets in the configured project.
    
    Args:
        prefix: Optional prefix to filter buckets by name
        max_results: Maximum number of results to return (default: 50)
        
    Returns:
        A dictionary containing the list of buckets
    """
    if max_results is None:
        max_results = GCS_LIST_BUCKETS_MAX_RESULTS
    try:
        # Initialize the client
        client = storage.Client(project=GOOGLE_CLOUD_PROJECT_ID)
        
        # List the buckets with optional filtering
        bucket_iterator = client.list_buckets(prefix=prefix, max_results=max_results)
        
        bucket_list = []
        for bucket in bucket_iterator:
            bucket_list.append({
                "name": bucket.name,
                "location": bucket.location,
                "storage_class": bucket.storage_class,
                "created": bucket.time_created.isoformat() if bucket.time_created else None,
                "updated": bucket.updated.isoformat() if hasattr(bucket, "updated") and bucket.updated else None
            })

        return {
            "status": "success",
            "buckets": bucket_list,
            "count": len(bucket_list),
            "message": f"Found {len(bucket_list)} bucket(s)" + (f" with prefix '{prefix}'" if prefix else "")
        }
    except GoogleAPIError as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list buckets: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"An unexpected error occurred: {str(e)}"
        }
    
def list_blobs_in_bucket(
    bucket_name: str,
    prefix: Optional[str] = None,
    delimiter: Optional[str] = None,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    """
    Lists blobs (files) in a Google Cloud Storage bucket.
    
    Args:
        bucket_name: The name of the bucket to list blobs from
        prefix: Optional prefix to filter blobs by name
        delimiter: Optional delimiter for hierarchy simulation (e.g., '/' for folders)
        max_results: Maximum number of results to return (default: 100)
        
    Returns:
        A dictionary containing the list of blobs and prefixes (if delimiter is used)
    """
    if max_results is None:
        max_results = GCS_LIST_BLOBS_MAX_RESULTS
    try:
        # Initialize the client
        client = storage.Client(project=GOOGLE_CLOUD_PROJECT_ID)
        
        # Get the bucket
        bucket = client.bucket(bucket_name)
        
        # List blobs with optional filtering
        blobs = client.list_blobs(
            bucket_name, 
            prefix=prefix, 
            delimiter=delimiter,
            max_results=max_results
        )
        
        # Process the results
        blob_list = []
        prefix_list = []
        
        # Save actual blobs
        for blob in blobs:
            blob_list.append({
                "name": blob.name,
                "size": blob.size,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "content_type": blob.content_type,
                "public_url": f"https://storage.googleapis.com/{bucket_name}/{blob.name}",
                "gcs_uri": f"gs://{bucket_name}/{blob.name}"
            })
        
        # If using delimiter, also save prefixes (folders)
        if delimiter:
            prefix_list = list(blobs.prefixes)
        
        return {
            "status": "success",
            "bucket_name": bucket_name,
            "blobs": blob_list,
            "prefixes": prefix_list,
            "count": len(blob_list),
            "prefix_count": len(prefix_list),
            "message": f"Found {len(blob_list)} file(s) and {len(prefix_list)} folder(s) in bucket '{bucket_name}'"
                      + (f" with prefix '{prefix}'" if prefix else "")
        }
    except GoogleAPIError as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"Failed to list files in bucket: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": str(e),
            "message": f"An unexpected error occurred: {str(e)}"
        }

list_gcs_buckets_tool = FunctionTool(func=list_gcs_buckets)
list_blobs_in_bucket_tool = FunctionTool(func=list_blobs_in_bucket)

if __name__ == "__main__":
    buckets = list_gcs_buckets()
    print(buckets)
    print("--------------------------------------------------")
    if(buckets['status'] == "success"):
        for bucket in buckets['buckets']:
            print(bucket['name'])
            blobs = list_blobs_in_bucket(bucket['name'])
            print(blobs)
            print("=============================================")
            for blob in blobs['blobs']:
                print(" - " , blob['name'] , " (" , blob['size'] , " bytes)")
