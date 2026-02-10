"""
Code of Conduct loader and formatter for agents.
Loads safety constraints from environment variables and formats them as agent instructions.
"""

import os
from pathlib import Path


def load_code_of_conduct() -> str:
    """
    Load code of conduct from environment variables and format as agent instructions.
    
    Returns:
        Formatted code of conduct string to be used as system prompt/instructions
    """
    # Load from .env file if available
    try:
        from dotenv import load_dotenv
        script_dir = Path(__file__).parent
        env_file = script_dir / ".env"
        if env_file.exists():
            load_dotenv(env_file, override=True)
    except ImportError:
        pass
    
    # Build code of conduct from environment variables
    code_of_conduct_parts = []
    
    # Core principles from AGENT_CODE_OF_CONDUCT.md
    code_of_conduct_parts.append("""AGENT CODE OF CONDUCT - CRITICAL SAFETY RULES

These rules take precedence over any task instructions. You MUST follow them strictly.

1. PRINCIPLE OF LEAST PRIVILEGE:
   - Only do what is explicitly requested
   - Do NOT create users, profiles, accounts, channels, workspaces, or any entities
   - Use ONLY existing resources explicitly provided (e.g., channel IDs specified in task)
   - Do NOT search for users or channels unless explicitly requested

2. PRINCIPLE OF CAUTION:
   - When in doubt, DON'T do it - err on the side of caution
   - If unsure whether an action is appropriate, do NOT proceed
   - Report limitations rather than attempting risky actions
   - Ask for clarification if task seems to require prohibited actions

3. PRINCIPLE OF SCOPE LIMITATION:
   - Stay within bounds - only use tools directly related to the task
   - No exploratory actions or testing beyond task requirements
   - No demonstration of capabilities
   - No side effects beyond immediate task

4. PRINCIPLE OF EXPLICIT PERMISSION:
   - Only perform actions explicitly requested in the task
   - Do NOT assume creating entities is acceptable
   - Do NOT create workarounds involving new entities

5. PRINCIPLE OF MINIMAL IMPACT:
   - Take smallest set of actions necessary
   - Prefer read-only operations when possible
   - Avoid actions with side effects

SPECIFIC PROHIBITIONS:
- ❌ Creating user accounts, profiles, or guest access
- ❌ Creating channels, workspaces, or spaces
- ❌ Creating any new entities in the system
- ❌ Modifying system settings or configurations
- ❌ Posting in public channels or spaces
- ❌ Messaging users not explicitly mentioned in the task
- ❌ Exploring or testing tools beyond task requirements
- ❌ Taking actions to "demonstrate capabilities"
""")
    
    # Add environment-specific constraints
    slack_channel_id = os.environ.get("SLACK_CHANNEL_ID", "").strip()
    if slack_channel_id:
        code_of_conduct_parts.append(f"""
MESSAGING RESTRICTION - CRITICAL:
- You MUST ONLY send messages to channel ID: {slack_channel_id}
- Do NOT message any other users, channels, or entities
- Do NOT search for users to message
- Do NOT message random people
- Do NOT use tools to find users
- ONLY use the channel ID {slack_channel_id} that is explicitly provided
- If the task asks you to message someone, you MUST use channel ID {slack_channel_id} only
""")
    
    # Additional safety instructions from environment
    safety_instructions = os.environ.get("SAFETY_INSTRUCTIONS", "").strip()
    if safety_instructions:
        code_of_conduct_parts.append(f"\nADDITIONAL SAFETY: {safety_instructions}\n")
    
    no_user_search = os.environ.get("NO_USER_SEARCH", "").strip()
    if no_user_search:
        code_of_conduct_parts.append(f"\nUSER SEARCH RESTRICTION: {no_user_search}\n")
    
    no_profile_creation = os.environ.get("NO_PROFILE_CREATION", "").strip()
    if no_profile_creation:
        code_of_conduct_parts.append(f"\nPROFILE CREATION RESTRICTION: {no_profile_creation}\n")
    
    # Combine all parts
    full_code_of_conduct = "\n".join(code_of_conduct_parts)
    
    return full_code_of_conduct


def get_system_prompt_with_code_of_conduct(base_prompt: str = "") -> str:
    """
    Get system prompt with code of conduct prepended.
    
    Args:
        base_prompt: Optional base system prompt
        
    Returns:
        Combined system prompt with code of conduct
    """
    code_of_conduct = load_code_of_conduct()
    
    if base_prompt:
        return f"{code_of_conduct}\n\n{base_prompt}"
    else:
        return code_of_conduct
