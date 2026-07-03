import boto3

from app.core.config import settings



def _bedrock_boto3_kwargs() -> dict:
    """Return boto3 keyword args for Bedrock clients.

    Priority:
    1. BEDROCK_API_KEY — dummy IAM creds; token injected via _apply_bedrock_api_key.
    2. BEDROCK_CROSS_ACCOUNT_ROLE_ARN — assumes the role, returns short-lived creds.
    3. Empty dict — boto3 uses the pod's IRSA role directly.
    """
    if settings.BEDROCK_API_KEY:
        return {"aws_access_key_id": "dummy", "aws_secret_access_key": "dummy"}
    if not settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN:
        return {}
    sts = boto3.client("sts", region_name=settings.AWS_REGION)
    assumed = sts.assume_role(
        RoleArn=settings.BEDROCK_CROSS_ACCOUNT_ROLE_ARN,
        RoleSessionName="stagecraft-api-bedrock",
        DurationSeconds=3600,
    )
    creds = assumed["Credentials"]
    return {
        "aws_access_key_id": creds["AccessKeyId"],
        "aws_secret_access_key": creds["SecretAccessKey"],
        "aws_session_token": creds["SessionToken"],
    }


def _apply_bedrock_api_key(client) -> None:
    """If BEDROCK_API_KEY is set, inject it as a Bearer token on every Bedrock request."""
    if not settings.BEDROCK_API_KEY:
        return
    api_key = settings.BEDROCK_API_KEY

    def _inject_bearer(request, **kwargs):
        request.headers["Authorization"] = f"Bearer {api_key}"

    client.meta.events.register("before-send.bedrock-runtime", _inject_bearer)
