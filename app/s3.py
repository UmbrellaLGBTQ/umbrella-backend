import boto3
import uuid
from fastapi import UploadFile, HTTPException
import os
from typing import Optional
from botocore.exceptions import ClientError

# Load AWS credentials from environment variables
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET_NAME")

# Initialize S3 client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)


def validate_image_file(file: UploadFile) -> bool:
    """Validate that the uploaded file is a JPEG or PNG image."""
    allowed_content_types = ["image/jpeg", "image/png"]
    allowed_extensions = [".jpeg", ".jpg", ".png"]
    
    # Check content type
    if file.content_type not in allowed_content_types:
        return False
    
    # Check file extension
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    if file_ext not in allowed_extensions:
        return False
    
    return True


async def upload_image_to_s3(file: UploadFile, user_id: int) -> str:
    """
    Upload image to S3 bucket and return the URL
    
    Args:
        file: The uploaded file object
        user_id: The ID of the user

    Returns:
        str: The URL of the uploaded image
    
    Raises:
        HTTPException: If the file is invalid or upload fails
    """
    # Validate image
    if not validate_image_file(file):
        raise HTTPException(status_code=400, detail="Invalid image format. Only JPEG and PNG are allowed.")
    
    try:
        # Generate a unique file name
        file_extension = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
        unique_filename = f"profile-images/{user_id}/{uuid.uuid4()}{file_extension}"
        
        # Read file content
        file_content = await file.read()
        
        # Upload to S3
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Generate URL
        url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{unique_filename}"
        return url
        
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


def delete_image_from_s3(image_url: str) -> bool:
    """
    Delete image from S3 bucket
    
    Args:
        image_url: The URL of the image to delete
        
    Returns:
        bool: True if deletion was successful
        
    Raises:
        HTTPException: If deletion fails
    """
    try:
        # Extract the key (filename) from the URL
        # URL format: https://bucket-name.s3.region.amazonaws.com/path/to/file
        parts = image_url.split(".amazonaws.com/")
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid S3 URL format")
            
        key = parts[1]
        
        # Delete the file from S3
        s3_client.delete_object(
            Bucket=S3_BUCKET,
            Key=key
        )
        
        return True
        
    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 deletion failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")