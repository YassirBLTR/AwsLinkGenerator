import boto3
import random
import string
import os
import datetime
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

# ============================
# AWS accounts (modify keys)
# ============================
accounts = [
    {
        "name": "aws1",
        "AWS_ACCESS_KEY": "AKIAZNI3ENVI6COTABV5",
        "AWS_SECRET_KEY": "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"
    },
    {
        "name": "aws2",
        "AWS_ACCESS_KEY": "AKIATBPR6LNM5Y6VVEGO",
        "AWS_SECRET_KEY": "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"
    },
    {
        "name": "aws3",
        "AWS_ACCESS_KEY": "AKIA2X7REWFSEXLVJXAI",
        "AWS_SECRET_KEY": "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"
    }
]

# ============================
# Available AWS regions
# ============================
available_regions = [
    'us-east-1', 'us-east-2',
    'us-west-1', 'us-west-2',
    'ca-central-1', 'ca-west-1',
    'eu-west-1', 'eu-west-2', 'eu-west-3',
    'eu-central-1', 'eu-central-2',
    'eu-north-1', 'eu-south-1', 'eu-south-2',
    'ap-south-1', 'ap-south-2',
    'ap-southeast-1', 'ap-southeast-2', 'ap-southeast-3', 'ap-southeast-4',
    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
    'ap-east-1',
    'sa-east-1',
    'me-south-1', 'me-central-1',
    'il-central-1',
    'af-south-1'
]

# ============================
# Helper functions
# ============================
def random_bucket_name():
    name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    parts = [name]
    for _ in range(2):
        parts.append(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
    return '-'.join(parts)

def random_object_name(length=30):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length)).strip()

# ============================
# MAIN SCRIPT
# ============================

# Show regions with numbers
print("🌍 Available AWS Regions:")
for i, region in enumerate(available_regions, start=1):
    print(f"{i}. {region}")

# Ask user to choose
selected_index = int(input("➡️ Select a region by number: ")) - 1
REGION = available_regions[selected_index]

# ============================
# STEP 1: Check bucket limits for each account
# ============================
bucket_limit = 100  # AWS default bucket limit per account

print("\n📊 Current bucket usage per account:")
account_buckets_info = {}

for account in accounts:
    try:
        s3 = boto3.client(
            's3',
            region_name=REGION,
            aws_access_key_id=account["AWS_ACCESS_KEY"],
            aws_secret_access_key=account["AWS_SECRET_KEY"]
        )

        # list buckets
        response = s3.list_buckets()
        existing_buckets = response.get('Buckets', [])
        count_existing = len(existing_buckets)

        account_buckets_info[account['name']] = {
            "existing": count_existing,
            "remaining": bucket_limit - count_existing
        }

        print(f"{account['name']} : {count_existing}/{bucket_limit}  (remaining: {bucket_limit - count_existing})")

    except Exception as e:
        print(f"❌ Error checking {account['name']}: {str(e)}")
        account_buckets_info[account['name']] = {"existing": None, "remaining": None}

# ============================
# STEP 2: Ask user how many buckets to create
# ============================
num_buckets = int(input("\n🪣 How many buckets to create per account? "))

# ============================
# STEP 3: Create buckets + upload
# ============================
with open("all_accounts_results.txt", "w") as result_file:

    for account in accounts:
        print(f"\n======================")
        print(f"🔑 Using account: {account['name']} | Region: {REGION}")
        print(f"======================")

        result_file.write(f"\n{account['name']}\n")

        try:
            s3 = boto3.client(
                's3',
                region_name=REGION,
                aws_access_key_id=account["AWS_ACCESS_KEY"],
                aws_secret_access_key=account["AWS_SECRET_KEY"]
            )

            creation_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result_file.write(f"date de creation: {creation_date}\n")

            existing = account_buckets_info[account['name']]["existing"]
            remaining = account_buckets_info[account['name']]["remaining"]

            if remaining is not None and num_buckets > remaining:
                print(f"⚠️ {account['name']} cannot create {num_buckets}, only {remaining} remaining. Skipping...")
                result_file.write(f"⚠️ Cannot create {num_buckets}, only {remaining} remaining.\n")
                continue

            for i in range(num_buckets):
                print(f"{account['name']} : {i+1}/{num_buckets}")

                bucket_name = random_bucket_name()

                # Create bucket
                if REGION == 'us-east-1':
                    s3.create_bucket(Bucket=bucket_name)
                else:
                    s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': REGION}
                    )

                # Configure public access
                s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': True,
                        'RestrictPublicBuckets': True
                    }
                )

                s3.put_bucket_ownership_controls(
                    Bucket=bucket_name,
                    OwnershipControls={
                        'Rules': [{'ObjectOwnership': 'BucketOwnerPreferred'}]
                    }
                )

                # Upload files (if exist)
                local_files = os.listdir(".")
                html_file = next((f for f in local_files if f.lower().endswith(".html")), None)
                image_file = next((f for f in local_files if f.lower().endswith(('.png', '.jpg', '.jpeg'))), None)

                if html_file and image_file:
                    html_key = random_object_name()
                    image_key = random_object_name()

                    # Upload HTML
                    s3.upload_file(html_file, bucket_name, html_key,
                                ExtraArgs={'ACL': 'public-read', 'ContentType': 'text/html'})
                    html_url = f"https://{bucket_name}.s3.{REGION}.amazonaws.com/{html_key}"
                    result_file.write(f"link html: {html_url}\n")

                    # Upload Image
                    ext = os.path.splitext(image_file)[1].lower()
                    content_type = "image/png" if ext == ".png" else "image/jpeg"
                    s3.upload_file(image_file, bucket_name, image_key,
                                ExtraArgs={'ACL': 'public-read', 'ContentType': content_type})
                    image_url = f"https://{bucket_name}.s3.{REGION}.amazonaws.com/{image_key}"
                    result_file.write(f"link image: {image_url}\n")

                else:
                    print("⚠️ HTML or image file not found in script folder.")

        except (ClientError, NoCredentialsError, EndpointConnectionError) as e:
            error_msg = f"❌ Error with {account['name']}: {str(e)}"
            print(error_msg)
            result_file.write(error_msg + "\n")
