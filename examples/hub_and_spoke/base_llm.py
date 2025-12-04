"""
Base LLM wrapper for AWS Bedrock.
Shared by all agents.
"""

import boto3


class BedrockLLM:
    """Simple Bedrock LLM wrapper."""

    def __init__(self, model_id: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime")

    async def invoke(self, system_prompt: str, user_message: str) -> str:
        """Call Bedrock and return the response."""
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": user_message}]}],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.7},
        )
        return response["output"]["message"]["content"][0]["text"]
