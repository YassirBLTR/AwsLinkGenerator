import boto3
import random
import string
import os
import datetime
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from typing import List, Dict, Any, Tuple
from models import AWSKey

class AWSService:
    def __init__(self):
        self.available_regions = [
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

    def random_bucket_name(self):
        """Generate a random bucket name"""
        name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        parts = [name]
        for _ in range(2):
            parts.append(''.join(random.choices(string.ascii_lowercase + string.digits, k=6)))
        return '-'.join(parts)

    def random_object_name(self, length=30):
        """Generate a random object name"""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length)).strip()

    def get_bucket_count(self, aws_key: AWSKey, region: str) -> Dict[str, Any]:
        """Get current bucket count for an AWS account"""
        try:
            s3 = boto3.client(
                's3',
                region_name=region,
                aws_access_key_id=aws_key.access_key,
                aws_secret_access_key=aws_key.secret_key
            )
            
            response = s3.list_buckets()
            existing_buckets = response.get('Buckets', [])
            count_existing = len(existing_buckets)
            bucket_limit = 100  # AWS default bucket limit per account
            
            return {
                "key_name": aws_key.name,
                "existing": count_existing,
                "remaining": bucket_limit - count_existing,
                "limit": bucket_limit,
                "success": True
            }
        except Exception as e:
            return {
                "key_name": aws_key.name,
                "existing": None,
                "remaining": None,
                "limit": 100,
                "success": False,
                "error": str(e)
            }

    def create_buckets_for_user(self, user_keys: List[AWSKey], region: str, num_buckets: int) -> Dict[str, Any]:
        """Create buckets for a user using their assigned AWS keys"""
        results = {
            "region": region,
            "num_buckets_requested": num_buckets,
            "keys_results": [],
            "total_buckets_created": 0,
            "total_urls_generated": 0,
            "creation_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        for aws_key in user_keys:
            key_result = {
                "key_name": aws_key.name,
                "buckets_created": 0,
                "urls": [],
                "errors": []
            }

            try:
                s3 = boto3.client(
                    's3',
                    region_name=region,
                    aws_access_key_id=aws_key.access_key,
                    aws_secret_access_key=aws_key.secret_key
                )

                # Check bucket limits
                bucket_info = self.get_bucket_count(aws_key, region)
                if not bucket_info["success"]:
                    key_result["errors"].append(f"Failed to check bucket limits: {bucket_info.get('error', 'Unknown error')}")
                    results["keys_results"].append(key_result)
                    continue

                if bucket_info["remaining"] < num_buckets:
                    key_result["errors"].append(f"Cannot create {num_buckets} buckets, only {bucket_info['remaining']} remaining")
                    results["keys_results"].append(key_result)
                    continue

                # Create buckets
                for i in range(num_buckets):
                    try:
                        bucket_name = self.random_bucket_name()

                        # Create bucket
                        if region == 'us-east-1':
                            s3.create_bucket(Bucket=bucket_name)
                        else:
                            s3.create_bucket(
                                Bucket=bucket_name,
                                CreateBucketConfiguration={'LocationConstraint': region}
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

                        # Upload files if they exist
                        html_file = "index.html"
                        image_file = "uioccvb.jpg"

                        bucket_urls = []

                        if os.path.exists(html_file) and os.path.exists(image_file):
                            # Upload HTML
                            html_key = self.random_object_name()
                            s3.upload_file(html_file, bucket_name, html_key,
                                        ExtraArgs={'ACL': 'public-read', 'ContentType': 'text/html'})
                            html_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{html_key}"
                            bucket_urls.append({"type": "html", "url": html_url})

                            # Upload Image
                            image_key = self.random_object_name()
                            ext = os.path.splitext(image_file)[1].lower()
                            content_type = "image/png" if ext == ".png" else "image/jpeg"
                            s3.upload_file(image_file, bucket_name, image_key,
                                        ExtraArgs={'ACL': 'public-read', 'ContentType': content_type})
                            image_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{image_key}"
                            bucket_urls.append({"type": "image", "url": image_url})

                        key_result["urls"].extend(bucket_urls)
                        key_result["buckets_created"] += 1
                        results["total_buckets_created"] += 1
                        results["total_urls_generated"] += len(bucket_urls)

                    except Exception as bucket_error:
                        key_result["errors"].append(f"Failed to create bucket {i+1}: {str(bucket_error)}")

            except Exception as key_error:
                key_result["errors"].append(f"Failed to initialize AWS client: {str(key_error)}")

            results["keys_results"].append(key_result)

        return results

    def save_results_to_file(self, results: Dict[str, Any], filename: str = "bucket_creation_results.txt"):
        """Save bucket creation results to a file"""
        with open(filename, "w") as f:
            f.write(f"Bucket Creation Results\n")
            f.write(f"======================\n")
            f.write(f"Date: {results['creation_date']}\n")
            f.write(f"Region: {results['region']}\n")
            f.write(f"Buckets Requested per Key: {results['num_buckets_requested']}\n")
            f.write(f"Total Buckets Created: {results['total_buckets_created']}\n")
            f.write(f"Total URLs Generated: {results['total_urls_generated']}\n\n")

            for key_result in results["keys_results"]:
                f.write(f"\n{key_result['key_name']}\n")
                f.write(f"Buckets Created: {key_result['buckets_created']}\n")
                
                if key_result["errors"]:
                    f.write("Errors:\n")
                    for error in key_result["errors"]:
                        f.write(f"  - {error}\n")
                
                if key_result["urls"]:
                    f.write("Generated URLs:\n")
                    for url_info in key_result["urls"]:
                        f.write(f"  {url_info['type']}: {url_info['url']}\n")
                f.write("\n")

        return filename

    def validate_aws_key(self, access_key: str, secret_key: str) -> Tuple[str, str]:
        """
        Validate AWS credentials by attempting to list S3 buckets and create a test bucket
        Returns: (status, message)
        Status can be: 'active', 'invalid', 'expired', 'no_permissions'
        """
        try:
            # Create S3 client with provided credentials
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name='us-east-1'  # Default region for validation
            )
            
            # Test 1: Try to list buckets (basic permission check)
            try:
                s3_client.list_buckets()
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'InvalidAccessKeyId':
                    return 'invalid', 'Invalid Access Key ID'
                elif error_code == 'SignatureDoesNotMatch':
                    return 'invalid', 'Invalid Secret Access Key'
                elif error_code == 'TokenRefreshRequired':
                    return 'expired', 'Credentials have expired'
                elif error_code == 'AccessDenied':
                    return 'no_permissions', 'Access denied - insufficient permissions'
                else:
                    return 'invalid', f'AWS Error: {error_code}'
            
            # Test 2: Try to create a test bucket (more comprehensive check)
            test_bucket_name = f"test-validation-{random.randint(100000, 999999)}"
            try:
                s3_client.create_bucket(Bucket=test_bucket_name)
                # If successful, immediately delete the test bucket
                s3_client.delete_bucket(Bucket=test_bucket_name)
                return 'active', 'Key is valid and has bucket creation permissions'
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'AccessDenied':
                    # Can list buckets but can't create - limited permissions
                    return 'no_permissions', 'Key valid but lacks bucket creation permissions'
                elif error_code == 'BucketAlreadyExists':
                    # Bucket name collision, but key works
                    return 'active', 'Key is valid (bucket name collision during test)'
                else:
                    return 'no_permissions', f'Limited permissions: {error_code}'
                    
        except NoCredentialsError:
            return 'invalid', 'No credentials provided'
        except EndpointConnectionError:
            return 'invalid', 'Cannot connect to AWS (network issue)'
        except Exception as e:
            return 'invalid', f'Validation error: {str(e)}'
