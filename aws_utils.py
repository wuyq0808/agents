"""
AWS utilities for retrieving credentials and testing Bedrock connectivity.

This module provides common functions for AWS credential management used across
multiple notebooks and scripts.
"""

import subprocess
import re
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def get_aws_credentials():
    """Get AWS credentials using saml2aws script command.
    
    Returns:
        dict: Dictionary containing AWS credentials, or None if failed
    """
    try:
        # Run saml2aws script command
        result = subprocess.run(
            ["saml2aws", "script", "--profile", "default"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        
        # Parse the export statements
        exports = result.stdout.strip()
        credentials = {}
        
        for line in exports.split('\n'):
            if line.startswith('export '):
                # Extract key=value from export statements
                match = re.match(r'export ([^=]+)=(.*)', line)
                if match:
                    key, value = match.groups()
                    credentials[key] = value
        
        return credentials
        
    except subprocess.CalledProcessError as e:
        print(f"❌ saml2aws failed: {e}")
        print("Trying mshell login...")
        try:
            subprocess.run(["mshell", "login"], check=True)
            # Retry saml2aws after mshell login
            return get_aws_credentials()
        except subprocess.CalledProcessError:
            print("❌ mshell login also failed")
            return None
    except FileNotFoundError:
        print("❌ saml2aws not found. Please install saml2aws or set environment variables manually")
        return None


def setup_aws_credentials(region='eu-west-1'):
    """Set up AWS credentials and return them in a convenient format.
    
    Args:
        region (str): AWS region to use (default: 'eu-west-1')
        
    Returns:
        tuple: (aws_access_key, aws_secret_key, aws_session_token, aws_region) or (None, None, None, None)
    """
    creds = get_aws_credentials()

    if creds:
        aws_access_key = creds.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = creds.get('AWS_SECRET_ACCESS_KEY') 
        aws_session_token = creds.get('AWS_SESSION_TOKEN')
        aws_region = region
        
        print(f"✅ AWS credentials retrieved successfully")
        print(f"🔑 Access Key: {aws_access_key[:8]}...")
        print(f"🌍 Region: {aws_region}")
        if creds.get('AWS_CREDENTIAL_EXPIRATION'):
            print(f"⏰ Expires: {creds['AWS_CREDENTIAL_EXPIRATION']}")
            
        return aws_access_key, aws_secret_key, aws_session_token, aws_region
    else:
        print("❌ Failed to get AWS credentials")
        return None, None, None, None


def test_bedrock_connectivity(aws_access_key, aws_secret_key, aws_session_token, aws_region, model_id):
    """Test connectivity to AWS Bedrock with the given credentials.
    
    Args:
        aws_access_key (str): AWS access key
        aws_secret_key (str): AWS secret key  
        aws_session_token (str): AWS session token
        aws_region (str): AWS region
        model_id (str): Bedrock model ID to test
        
    Returns:
        bool: True if connectivity test passed, False otherwise
    """
    print("\n🧪 Testing Bedrock connectivity...")
    try:
        # Create Bedrock client
        bedrock_client = boto3.client(
            'bedrock-runtime',
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            aws_session_token=aws_session_token
        )
        
        # Test with a simple invoke
        test_query = "Hi, can you respond with just 'Hello from Bedrock!'?"
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 50,
            "messages": [{"role": "user", "content": test_query}]
        }
        
        print(f"📤 Query: {test_query}")
        
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType='application/json'
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            response_text = response_body['content'][0]['text']
            
            print("✅ Bedrock connectivity test successful!")
            print(f"✅ Model {model_id} is accessible")
            print(f"📥 Response: {response_text}")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDeniedException':
                print(f"⚠️  Bedrock accessible but model {model_id} access denied")
                print("   Go to AWS Console > Bedrock > Model access to request access")
            elif error_code == 'ValidationException':
                print("✅ Bedrock connectivity successful (validation error is expected)")
                return True
            else:
                print(f"⚠️  Bedrock error: {error_code} - {e.response['Error']['Message']}")
            return False
                
    except ImportError:
        print("❌ boto3 not available - install with: pip install boto3")
        return False
    except NoCredentialsError:
        print("❌ AWS credentials not properly configured")
        return False
    except Exception as e:
        print(f"❌ Bedrock connectivity test failed: {e}")
        return False