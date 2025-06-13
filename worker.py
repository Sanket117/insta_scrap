import boto3
import json
import subprocess
import os
import time
import sys
import shutil
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()
QUEUE_URL = os.getenv('QUEUE_URL', "https://sqs.ap-south-1.amazonaws.com/471112784201/ImageAnalysisQueue")
S3_BUCKET = "smm-analysis-bucket"

print(f"QUEUE_URL: {QUEUE_URL}")
print(f"S3_BUCKET: {S3_BUCKET}")

# Initialize AWS clients
print("Initializing AWS clients...")
sqs_client = boto3.client("sqs", region_name="ap-south-1")
s3_client = boto3.client("s3", region_name="ap-south-1")
dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
table = dynamodb.Table("ImageAnalysisTasks")
print("AWS clients initialized.")

# Use the Python executable from the current virtual environment
PYTHON_EXECUTABLE = sys.executable
print(f"Python executable: {PYTHON_EXECUTABLE}")

# Base temporary directories
TEMP_BASE_DIR = "temp"
TEMP_PRODUCT_BASE = os.path.join(TEMP_BASE_DIR, "product_images")
TEMP_COMPETITOR_BASE = os.path.join(TEMP_BASE_DIR, "competitor_images")
os.makedirs(TEMP_PRODUCT_BASE, exist_ok=True)
os.makedirs(TEMP_COMPETITOR_BASE, exist_ok=True)
print("Base temporary directories created.")

def run_script(script, company_name, task_id, product_image_paths=None, competitor_image_paths=None):
    """Run a script with the given company name and task ID, and return success status."""
    print(f"Running script: {script} for company {company_name} with task_id {task_id}")
    start_time = time.time()
    env = os.environ.copy()
    env["TASK_ID"] = task_id
    env["COMPANY_NAME"] = company_name
    if product_image_paths:
        env["PRODUCT_IMAGE_PATHS"] = json.dumps(product_image_paths)
        print(f"Set PRODUCT_IMAGE_PATHS: {env['PRODUCT_IMAGE_PATHS']}")
    if competitor_image_paths:
        env["COMPETITOR_IMAGE_PATHS"] = json.dumps(competitor_image_paths)
        print(f"Set COMPETITOR_IMAGE_PATHS: {env['COMPETITOR_IMAGE_PATHS']}")
    try:
        result = subprocess.run(
            [PYTHON_EXECUTABLE, script, company_name],
            capture_output=True,
            text=True,
            env=env,
            timeout=1200  # 20-minute timeout
        )
        success = result.returncode == 0
        message = result.stderr or result.stdout
        print(f"Script {script} completed. Success: {success}, Message: {message}")
    except subprocess.TimeoutExpired as e:
        print(f"Script {script} timed out after 20 minutes: {e}")
        return False, f"Script {script} timed out after 20 minutes"
    except Exception as e:
        print(f"Error running script {script}: {e}")
        return False, str(e)
    finally:
        execution_time = time.time() - start_time
        print(f"Script {script} execution time: {execution_time:.2f} seconds")
    return success, message

def upload_to_s3(local_path, s3_key):
    """Upload a file to S3."""
    try:
        s3_client.upload_file(local_path, S3_BUCKET, s3_key)
        print(f"Uploaded {local_path} to S3: {s3_key}")
        return True
    except Exception as e:
        print(f"Failed to upload {local_path} to S3: {e}")
        return False

def download_from_s3(s3_key, local_path):
    """Download a file from S3 to a local path, creating directories if needed."""
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        s3_client.download_file(S3_BUCKET, s3_key, local_path)
        print(f"Downloaded {s3_key} to {local_path}")
        return True
    except Exception as e:
        print(f"Failed to download {s3_key}: {e}")
        return False

def check_s3_file_exists(s3_key):
    """Check if a file exists in S3."""
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        print(f"S3 file exists: {s3_key}")
        return True
    except Exception as e:
        print(f"S3 file does not exist: {s3_key}, Error: {e}")
        return False

def upload_local_pdfs(task_id):
    """Upload local PDFs to S3 with detailed logging."""
    local_pdf_dir = "data/reports/report_stats"
    pdf_files = ["1.pdf", "2.pdf", "3.pdf", "objective.pdf", "last.pdf"]
    uploaded_files = []
    missing_files = []

    for pdf_file in pdf_files:
        local_path = os.path.join(local_pdf_dir, pdf_file)
        s3_key = f"reports/{task_id}/{pdf_file}"
        if os.path.exists(local_path):
            print(f"Found local file: {local_path}")
            if upload_to_s3(local_path, s3_key):
                uploaded_files.append(pdf_file)
                print(f"Successfully uploaded {pdf_file} to {s3_key}")
            else:
                print(f"Failed to upload {pdf_file} to {s3_key} despite file existence")
        else:
            print(f"Local PDF not found: {local_path}")
            missing_files.append(pdf_file)

    if missing_files:
        print(f"Warning: The following local PDFs were not found: {missing_files}")
        return False
    if not uploaded_files:
        print("Error: No PDFs were uploaded to S3")
        return False
    print(f"Successfully uploaded PDFs: {uploaded_files}")
    return True

def process_task(task_data):
    """Process a single task from SQS."""
    print("Processing task...")
    task_id = task_data["task_id"]
    company_name = task_data["company_name"]
    product_image_keys = task_data["product_images"]
    competitor_image_keys = task_data["competitor_images"]
    print(f"Task ID: {task_id}, Company: {company_name}")

    # Define task-specific temporary directories
    temp_product_dir = os.path.join(TEMP_PRODUCT_BASE, task_id)
    temp_competitor_dir = os.path.join(TEMP_COMPETITOR_BASE, task_id)
    os.makedirs(temp_product_dir, exist_ok=True)
    os.makedirs(temp_competitor_dir, exist_ok=True)
    print(f"Task-specific temp directories created: {temp_product_dir}, {temp_competitor_dir}")

    # Update task status to pending in DynamoDB
    print("Updating task status to pending in DynamoDB...")
    try:
        table.update_item(
            Key={"task_id": task_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "pending"}
        )
        print("Task status updated to pending.")
    except Exception as e:
        print(f"Failed to update task status to pending: {e}")
        return False

    # Download product images from S3
    print("Downloading product images from S3...")
    product_image_paths = []
    for key in product_image_keys:
        relative_path = key.replace(f"product_images/{task_id}/", "")
        local_path = os.path.join(temp_product_dir, relative_path)
        if download_from_s3(key, local_path):
            product_image_paths.append(local_path)
        else:
            print(f"Failed to download product image {key}.")
            return False

    # Download competitor images from S3
    print("Downloading competitor images from S3...")
    competitor_image_paths = []
    for key in competitor_image_keys:
        relative_path = key.replace(f"competitor_images/{task_id}/", "")
        local_path = os.path.join(temp_competitor_dir, relative_path)
        if download_from_s3(key, local_path):
            competitor_image_paths.append(local_path)
        else:
            print(f"Failed to download competitor image {key}.")
            return False

    print(f"Product image paths: {product_image_paths}")
    print(f"Competitor image paths: {competitor_image_paths}")

    # List of scripts to run
    scripts = [
        ("src/input_analysis/product-analysis/product_analysis.py", True),
        ("src/input_analysis/competitor-analysis/competitor_analysis.py", True),
        ("src/input_analysis/Standarddeviation.py", False),
        ("src/input_analysis/renamebranding.py", False),
        ("src/input_analysis/path.py", False),
        ("src/input_analysis/feedback.py", False),
        ("src/templates/brand.py", True),
        ("src/templates/content.py", True),
        ("src/templates/social.py", True),
        ("src/Report/updated1.py", False),
        ("src/Report/Report.py", False)
    ]

    # Run product_analysis.py and competitor_analysis.py concurrently
    print("Running product_analysis.py and competitor_analysis.py concurrently...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_script = {
            executor.submit(
                run_script,
                script,
                company_name,
                task_id,
                product_image_paths if requires_images else None,
                competitor_image_paths if requires_images else None
            ): script
            for script, requires_images in scripts[:2]
        }

        for future in as_completed(future_to_script):
            script = future_to_script[future]
            try:
                success, message = future.result()
                if not success:
                    print(f"Script {script} failed. Updating task status to error.")
                    table.update_item(
                        Key={"task_id": task_id},
                        UpdateExpression="SET #status = :status, error_message = :msg",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={":status": "error", ":msg": message}
                    )
                    return False
                print(f"Script {script} completed successfully.")
            except Exception as e:
                print(f"Exception in script {script}: {e}")
                table.update_item(
                    Key={"task_id": task_id},
                    UpdateExpression="SET #status = :status, error_message = :msg",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": "error", ":msg": str(e)}
                )
                return False

    # Run the remaining scripts sequentially
    print("Running remaining scripts sequentially...")
    for script, requires_images in scripts[2:]:
        if script == "src/Report/Report.py":
            print("Uploading local PDFs to S3...")
            if not upload_local_pdfs(task_id):
                print("Failed to upload local PDFs to S3. Aborting.")
                table.update_item(
                    Key={"task_id": task_id},
                    UpdateExpression="SET #status = :status, error_message = :msg",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": "error", ":msg": "Failed to upload local PDFs to S3"}
                )
                return False

        success, message = run_script(
            script,
            company_name,
            task_id,
            product_image_paths if requires_images else None,
            competitor_image_paths if requires_images else None
        )
        if not success:
            print(f"Script {script} failed. Updating task status to error.")
            table.update_item(
                Key={"task_id": task_id},
                UpdateExpression="SET #status = :status, error_message = :msg",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "error", ":msg": message}
            )
            return False
        print(f"Script {script} completed successfully.")

    # After all scripts have run successfully, update report_s3_keys in DynamoDB
    print("Preparing to update report_s3_keys in DynamoDB...")
    report_s3_keys = {
        "final_report": f"reports/{task_id}/final_report.pdf",
        "brand_marketing": f"reports/{task_id}/pdfs/brand_marketing.pdf",
        "content_marketing": f"reports/{task_id}/pdfs/content_marketing.pdf",
        "social_media_marketing": f"reports/{task_id}/pdfs/social_media_marketing.pdf"
    }

    all_reports_exist = True
    for key, s3_path in report_s3_keys.items():
        if not check_s3_file_exists(s3_path):
            print(f"Report {key} not found in S3 at {s3_path}. Aborting DynamoDB update.")
            all_reports_exist = False
            table.update_item(
                Key={"task_id": task_id},
                UpdateExpression="SET #status = :status, error_message = :msg",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "error", ":msg": f"Report {key} not found in S3 at {s3_path}"}
            )
            return False

    if all_reports_exist:
        try:
            table.update_item(
                Key={"task_id": task_id},
                UpdateExpression="SET report_s3_keys = :keys",
                ExpressionAttributeValues={":keys": report_s3_keys},
                ReturnValues="UPDATED_NEW"
            )
            print(f"Successfully updated DynamoDB with report_s3_keys: {report_s3_keys}")
        except Exception as e:
            print(f"Failed to update report_s3_keys in DynamoDB: {e}")
            table.update_item(
                Key={"task_id": task_id},
                UpdateExpression="SET #status = :status, error_message = :msg",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": "error", ":msg": f"Failed to update report_s3_keys: {str(e)}"}
            )
            return False

    # Update task status to done with end_time in DynamoDB
    print("Updating task status to done in DynamoDB with end_time...")
    try:
        end_time = int(time.time())
        table.update_item(
            Key={"task_id": task_id},
            UpdateExpression="SET #status = :status, end_time = :end_time",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "done", ":end_time": end_time}
        )
        print(f"Task status updated to done with end_time: {end_time}.")
    except Exception as e:
        print(f"Failed to update task status to done with end_time: {e}")
        return False

    # Clean up task-specific temporary directories
    print("Cleaning up task-specific temporary directories...")
    try:
        shutil.rmtree(temp_product_dir, ignore_errors=True)
        shutil.rmtree(temp_competitor_dir, ignore_errors=True)
        print(f"Removed task-specific directories: {temp_product_dir}, {temp_competitor_dir}")
    except Exception as e:
        print(f"Error cleaning up task-specific directories: {e}")

    return True

# Poll SQS indefinitely
print("Starting SQS polling loop...")
while True:
    try:
        print("Polling SQS for messages...")
        response = sqs_client.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10  # Long polling
        )
        print(f"SQS response: {response}")
        if "Messages" in response:
            for message in response["Messages"]:
                print("Received message from SQS.")
                try:
                    task_data = json.loads(message["Body"])
                    print(f"Task data: {task_data}")
                except json.JSONDecodeError as e:
                    print(f"Failed to parse message body: {e}")
                    continue

                required_fields = ["task_id", "company_name", "product_images", "competitor_images"]
                if not all(field in task_data for field in required_fields):
                    print("Message missing required fields. Skipping.")
                    continue

                success = process_task(task_data)
                if success:
                    print("Task processed successfully. Deleting message from SQS.")
                    sqs_client.delete_message(
                        QueueUrl=QUEUE_URL,
                        ReceiptHandle=message["ReceiptHandle"]
                    )
                else:
                    print("Task processing failed. Message will remain in SQS for retry.")
        else:
            print("No messages in SQS queue.")
        time.sleep(1)  # Avoid tight loop
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt. Exiting gracefully...")
        break
    except Exception as e:
        print(f"Error in SQS polling loop: {e}")
        time.sleep(5)  # Wait before retrying