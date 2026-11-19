import asyncio
import os

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from instructions import AGENT_INSTRUCTIONS
from tools import TOOLS

load_dotenv()


async def main() -> None:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )
    agent = Agent(client=client, instructions=AGENT_INSTRUCTIONS, tools=TOOLS)
    await ResponsesHostServer(agent).run_async()


if __name__ == "__main__":
    asyncio.run(main())
