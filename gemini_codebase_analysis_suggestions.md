Excellent question. This is a classic UX design problem in CLI and AI-powered tools: balancing explicit user control with intelligent, "magical" assistance. Doing too little makes the tool feel dumb, but doing too much magic can be confusing and disempowering for the user.

The best approach is a combination of your suggestions:

1.  **Create a new, dedicated `analyze_code` tool** for the primary, explicit workflow.
2.  **Make the existing `ask` tool smarter** to detect intent and guide users toward the new, more powerful tool.

This hybrid approach provides the best of both worlds: clarity for users who know what they want, and helpful guidance for those who don't.

---

### Recommended Solution: A Two-Pronged Approach

#### 1. The Explicit Tool: `analyze_code`

This should be the primary, recommended way for users to perform code analysis. It makes the user's intent clear and allows you to design the parameters specifically for this task. It follows the **Single Responsibility Principle**, where one tool does one thing well.

**Design Rationale:**

*   **Clarity:** The user knows they are initiating a code analysis task. The tool's name (`analyze_code`) is self-documenting.
*   **Power:** You can add specific parameters like `path`, `exclude`, `auto_summarize`, and `interactive` that wouldn't make sense on a generic `ask` tool.
*   **Predictability:** The user can expect this tool to always interact with the filesystem. There are no surprises.

**Proposed Implementation:**

Here’s how you could define the `analyze_code` tool.

```python
import os
from typing import List, Optional
# Assuming you have a code2prompt utility available
from .utils import run_code2prompt, get_file_tree, prompt_user_for_confirmation

# This would be your MCP tool decorator
# from mcp import mcp 

@mcp.tool()
def analyze_code(
    prompt: str,
    path: str = ".",
    auto_summarize: bool = True,
    interactive: bool = False,
    exclude: List[str] = [".git", "node_modules", "__pycache__"],
    agent_name: str = "session",
) -> dict:
    """
    Analyzes a codebase by gathering context and then asking a question.

    :param prompt: The question to ask about the code.
    :param path: The root directory or specific file to analyze. Defaults to the current directory.
    :param auto_summarize: If True, automatically runs code2prompt to generate a context summary.
    :param interactive: If True, prompts the user to confirm the files before analysis.
    :param exclude: A list of file/directory patterns to exclude from analysis.
    :param agent_name: The agent to use for the final query.
    """
    print(f"🔍 Analyzing code at path: '{os.path.abspath(path)}'")
    
    code_context = ""
    if auto_summarize:
        try:
            print("📦 Generating codebase summary with code2prompt...")
            # This is a placeholder for your actual code2prompt call
            code_context = run_code2prompt(root_folder=path, exclude_patterns=exclude)
            print("✅ Summary generated.")
        except Exception as e:
            return {"error": f"Failed to run code2prompt: {e}"}
    else:
        # If not auto-summarizing, we can just get a file tree as context
        print("🌳 Generating file tree...")
        code_context = get_file_tree(root_folder=path, exclude_patterns=exclude)

    if interactive:
        # Show the user what's about to be sent and ask for confirmation
        preview = (code_context[:500] + '...') if len(code_context) > 500 else code_context
        message = f"\nGenerated context preview:\n---\n{preview}\n---\nProceed with this context? (y/N): "
        if not prompt_user_for_confirmation(message):
            return {"status": "Analysis cancelled by user."}

    # Here, we can call the original 'ask' tool's underlying logic, 
    # or directly call the LLM service. Re-using 'ask' is a good pattern.
    print(f"💬 Sending enriched prompt to agent '{agent_name}'...")
    
    # We are now calling the 'ask' tool programmatically with the context we've built
    return ask(
        prompt=prompt,
        files=[], # We've already embedded the context in the prompt or another field
        # Instead of files, you might have a dedicated 'context' parameter
        # For simplicity, let's prepend it to the prompt.
        contextual_prompt=f"Based on the following code context:\n\n{code_context}\n\nPlease answer this question: {prompt}",
        agent_name=agent_name,
    )

# The 'ask' tool would need a slight modification to handle the new prompt structure
@mcp.tool()
def ask(
    prompt: str = None,
    agent_name: str = "session",
    files: List[str] = [],
    contextual_prompt: Optional[str] = None,
    # other params...
) -> dict:
    """Sends a prompt to the specified agent."""
    final_prompt = contextual_prompt if contextual_prompt else prompt
    
    if not final_prompt:
        return {"error": "Prompt cannot be empty."}

    # Handle manually attached files, if any
    file_context = ""
    if files:
        # logic to read files and add to context
        pass
    
    # ... rest of the logic to call the LLM with final_prompt and file_context ...
    print(f"Executing ask with final prompt: {final_prompt[:100]}...")
    return {"response": "LLM response based on the context."}
```

---

#### 2. The Intelligent Guardrail: Enhancing `ask`

Now, address the problem of users still typing "review my code" into the `ask` tool. Instead of silently failing or doing the wrong thing, `ask` can detect this intent and guide the user.

**Design Rationale:**

*   **User Education:** It teaches users the better way to use the tool without a breaking change.
*   **Helpful Assistance:** It feels like the tool understands you and is trying to help, which is a great user experience.
*   **Respects User Intent:** Crucially, this logic only triggers if the user *hasn't* already provided files. If they use `ask --files ...`, we assume they are a power user who knows what they're doing.

**Proposed Implementation:**

Modify the existing `ask` function to include this pre-check.

```python
CODE_REVIEW_KEYWORDS = ["review", "analyze", "refactor", "explain", "debug", "audit", "test"]
CODE_NOUN_KEYWORDS = ["code", "codebase", "file", "directory", "repo", "script", "module", "component"]

@mcp.tool()
def ask(
    prompt: str,
    agent_name: str = "session", 
    files: List[str] = [],
    # other params...
) -> dict:
    """Sends a prompt to the specified agent. Includes an intelligent check for code analysis requests."""

    # 1. Check for intent IF no files were manually provided.
    if not files and any(kw in prompt.lower() for kw in CODE_REVIEW_KEYWORDS) and any(kw in prompt.lower() for kw in CODE_NOUN_KEYWORDS):
        # 2. Inform and guide the user.
        print("💡 It looks like you're asking to review code.")
        print("For best results, the `analyze_code` tool can automatically gather context for you.")
        print("\nExample usage:")
        print(f"  mcp analyze_code --prompt \"{prompt}\"")
        
        # 3. Offer to proceed anyway or cancel.
        if not prompt_user_for_confirmation("\nDo you want to continue with the 'ask' tool anyway? (y/N): "):
            return {"status": "Cancelled. Try using the 'analyze_code' tool for better results."}

    # ... (rest of the original 'ask' logic) ...
    print(f"Executing original 'ask' logic for prompt: {prompt}")
    return {"response": "LLM response based on the prompt."}

# Helper for user confirmation
def prompt_user_for_confirmation(message: str) -> bool:
    response = input(message).lower().strip()
    return response == 'y'

```

### Summary of the User Experience

This new design creates clear and helpful user journeys:

1.  **The Expert User:**
    *   `mcp analyze_code --prompt "Is my error handling robust?" --path ./src`
    *   **Result:** The tool works as expected, summarizing the `src` directory and feeding it to the LLM. **(Clear & Powerful)**

2.  **The New User (using the "wrong" tool):**
    *   `mcp ask --prompt "Can you review my codebase for bugs?"`
    *   **Result:** The tool responds: `💡 It looks like you're asking to review code. For best results, use the 'analyze_code' tool...` and provides an example. The user learns the correct command. **(Helpful & Educational)**

3.  **The Power User (using `ask` intentionally):**
    *   `mcp ask --prompt "Compare the logic in these two files" --files service.py utils.py`
    *   **Result:** The intent detection is skipped because `--files` was provided. The tool proceeds as commanded, respecting the user's explicit instructions. **(Respectful & Unobtrusive)**

4.  **The Standard User (non-code question):**
    *   `mcp ask --prompt "What is the capital of Mongolia?"`
    *   **Result:** The keyword check fails, and the tool executes the simple `ask` command as expected. **(No Interference)**

This pattern of **Explicit Tools + Intelligent Guardrails** is a robust and user-friendly way to build complex functionality into your MCP tool.
