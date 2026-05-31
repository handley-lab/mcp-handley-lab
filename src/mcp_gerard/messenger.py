"""Lightweight Telegram Bot Bridge for mcp-gerard.

Listens for Telegram messages, uses Claude to route requests, and implements
an Inbox/Outbox for zero-cost heavy LLM offloading to the Antigravity IDE.
"""

import asyncio
import os
import json
import httpx
from pathlib import Path

# Parse .env manually
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            os.environ[key.strip()] = val.strip()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
    print("Error: TELEGRAM_BOT_TOKEN and ANTHROPIC_API_KEY must be set in .env")
    exit(1)

import anthropic

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

# Global variables to track the user for outbox notifications
LAST_CHAT_ID = None
PROJECT_ROOT = Path(__file__).parent.parent.parent
INBOX_FILE = PROJECT_ROOT / "laplace_inbox.md"
OUTBOX_FILE = PROJECT_ROOT / "laplace_outbox.md"

def capture_idea(text: str) -> str:
    from mcp_gerard.vault import vault_capture
    try:
        return vault_capture(text)
    except Exception as e:
        return f"Error capturing idea: {e}"

def sync_github_projects() -> str:
    from mcp_gerard.projects import projects_sync_all
    try:
        return projects_sync_all()
    except Exception as e:
        return f"Error syncing projects: {e}"

def run_laplace(task_description: str) -> str:
    """Writes the task to the laplace_inbox.md so the Antigravity cron job can pick it up."""
    try:
        with open(INBOX_FILE, "a", encoding="utf-8") as f:
            f.write(f"- [ ] {task_description}\n")
        return "Task successfully added to Laplace Inbox. The Antigravity agent will pick it up on its next cron cycle."
    except Exception as e:
        return f"Failed to write to inbox: {e}"

TOOLS = [
    {
        "name": "capture_idea",
        "description": "Capture a quick idea or goal to the local vault.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The idea or goal to save."}
            },
            "required": ["text"]
        }
    },
    {
        "name": "sync_github_projects",
        "description": "Sync all local git repositories to GitHub.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "run_laplace",
        "description": "Trigger the heavy Laplace Engine research workflow by sending a task to the IDE inbox.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "The detailed task you want Laplace to execute."}
            },
            "required": ["task_description"]
        }
    }
]

async def handle_message(chat_id: int, text: str):
    global LAST_CHAT_ID
    LAST_CHAT_ID = chat_id
    print(f"Received from {chat_id}: {text}")
    try:
        messages = [{"role": "user", "content": text}]
        
        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            system="You are Gerard's remote assistant running on his PC. Use tools to interact with his local environment. Keep responses very short and concise for mobile.",
            messages=messages,
            tools=TOOLS
        )

        reply_text = "Done."

        if response.stop_reason == "tool_use":
            tool_results = []
            messages.append({"role": "assistant", "content": response.content})
            
            for block in response.content:
                if block.type == "tool_use":
                    name = block.name
                    args = block.input
                    print(f"Claude calling tool: {name} with args: {args}")
                    
                    if name == "capture_idea":
                        tool_result = capture_idea(**args)
                    elif name == "sync_github_projects":
                        tool_result = sync_github_projects()
                    elif name == "run_laplace":
                        tool_result = run_laplace(**args)
                    else:
                        tool_result = f"Unknown tool: {name}"
                    
                    print(f"Tool result: {tool_result}")
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(tool_result)
                    })
            
            messages.append({"role": "user", "content": tool_results})
            
            followup = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1024,
                system="You are Gerard's remote assistant running on his PC. Use tools to interact with his local environment. Keep responses very short and concise for mobile.",
                messages=messages,
                tools=TOOLS
            )
            
            for block in followup.content:
                if block.type == "text":
                    reply_text = block.text
        else:
            for block in response.content:
                if block.type == "text":
                    reply_text = block.text

        async with httpx.AsyncClient() as http:
            await http.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text}
            )
            
    except Exception as e:
        print(f"Error handling message: {e}")
        async with httpx.AsyncClient() as http:
            await http.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": f"Error: {str(e)}"}
            )

async def check_outbox():
    """Checks the laplace_outbox.md file and sends its contents to Telegram if found."""
    global LAST_CHAT_ID
    if LAST_CHAT_ID and OUTBOX_FILE.exists():
        content = OUTBOX_FILE.read_text(encoding="utf-8").strip()
        if content:
            print(f"Found outbox message. Sending to {LAST_CHAT_ID}...")
            try:
                async with httpx.AsyncClient() as http:
                    await http.post(
                        f"{TELEGRAM_API}/sendMessage",
                        json={"chat_id": LAST_CHAT_ID, "text": f"🧠 Laplace Engine Update:\n\n{content}"}
                    )
                # Clear outbox after sending
                OUTBOX_FILE.unlink()
            except Exception as e:
                print(f"Failed to send outbox message: {e}")

async def poll_telegram():
    offset = 0
    print("Telegram Bot Bridge is running with Inbox/Outbox syncing...")
    
    async with httpx.AsyncClient(timeout=60.0) as http:
        while True:
            # Check outbox every loop iteration
            await check_outbox()

            try:
                # Use a small timeout so we can check the outbox frequently
                response = await http.get(
                    f"{TELEGRAM_API}/getUpdates",
                    params={"offset": offset, "timeout": 5}
                )
                data = response.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        
                        if "message" in update and "text" in update["message"]:
                            chat_id = update["message"]["chat"]["id"]
                            text = update["message"]["text"]
                            
                            asyncio.create_task(handle_message(chat_id, text))
            
            except httpx.ReadTimeout:
                continue
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

def main():
    try:
        asyncio.run(poll_telegram())
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
