import os
import logging
import discord
from discord.ext import commands, tasks
import google.generativeai as genai
from discord import app_commands
import json
import glob
from datetime import time
# --- Add these imports ---
import re
import subprocess # Kept import in case user wants to switch later
import asyncio
import sys
import textwrap # Already used, but ensure it's imported
import io
import contextlib # Potentially useful for cleaner stdout redirection if needed


# Set up logging
# Ensure logger setup happens *before* first use, ideally at the top level
# Example basic config (adjust format/level as needed):
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger('discord_bot.ai_chat') # Use a specific name for this cog's logger

# Configure the Gemini API with the key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY environment variable not set. AI features will be disabled.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured.")


# --- Define Markers for Executable Code Blocks ---
# Use unique, unlikely strings. Put these around Python code in your .txt files.
PYTHON_EXEC_START_MARKER = "%%PYTHON_EXECUTE_BLOCK_START%%"
PYTHON_EXEC_END_MARKER = "%%PYTHON_EXECUTE_BLOCK_END%%"
# Example in QuestfallDocs.txt:
# Some documentation text...
# To calculate damage, use the following formula:
# %%PYTHON_EXECUTE_BLOCK_START%%
# ```python
# def calculate_damage(attack, defense):
#     # Ensure values are numbers, default to 0 if not
#     try:
#         attack = float(attack)
#         defense = float(defense)
#     except (ValueError, TypeError):
#         print("Error: Attack and defense must be numeric.")
#         return None # Or raise an error, or return 0
#
#     base_damage = max(1, attack - defense * 0.8)
#     crit_chance = 0.1
#     # Simulating a crit without random for deterministic example:
#     # if attack > 100: base_damage *= 1.5 # Example condition
#     return round(base_damage)
#
# # Example usage with print statement for output capture
# player_attack = 120
# enemy_defense = 50
# damage_dealt = calculate_damage(player_attack, enemy_defense)
# if damage_dealt is not None:
#     print(f"Calculated damage for attack={player_attack}, defense={enemy_defense}: {damage_dealt}")
# else:
#     print(f"Could not calculate damage for attack={player_attack}, defense={enemy_defense}.")
# ```
# %%PYTHON_EXECUTE_BLOCK_END%%
# More documentation text...
# ----------------------------------------------------


# Set up the Gemini Pro model for chat with specific generation config
generation_config = genai.types.GenerationConfig(
    temperature=0.1,  # Lower temperature for more precise answers
    # top_p=0.8,
    # top_k=30,
    # max_output_tokens=2000 # Increase if needed for combined explanation + code
    # tools=[genai.types.Tool(code_execution=genai.types.ToolCodeExecution)] # Keep commented unless using built-in execution
)
logger.info(f"Gemini Generation Config: {generation_config}")

# Set up the Gemini model - Only if API key is present
model = None
if GEMINI_API_KEY:
    try:
        model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config) # Use recommended model
        logger.info("Gemini model 'gemini-1.5-flash' initialized.")
    except Exception as e:
        logger.critical(f"Failed to initialize Gemini model: {e}", exc_info=True)
        # Depending on severity, might want to exit or disable the cog

# Knowledge base directory setup
try:
    # Assume script is in a 'cogs' folder, KB is one level up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)
    KNOWLEDGE_BASE_DIR = os.path.join(base_dir, "knowledge_base")
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    logger.info(f"Knowledge base directory set to: {KNOWLEDGE_BASE_DIR}")
    if not os.path.exists(KNOWLEDGE_BASE_DIR):
         logger.error(f"Knowledge base directory does NOT exist: {KNOWLEDGE_BASE_DIR}")
    else:
        logger.info(f"Knowledge base directory exists: {KNOWLEDGE_BASE_DIR}")
        # files = os.listdir(KNOWLEDGE_BASE_DIR) # List files after confirming existence
        # logger.info(f"Files currently in knowledge base directory: {files}")

except Exception as e:
    logger.critical(f"Error setting up knowledge base directory: {e}", exc_info=True)
    KNOWLEDGE_BASE_DIR = None # Ensure it's None if setup fails

class AIChat(commands.Cog):
    """Cog for AI chat functionality using Google's Gemini model."""

    def __init__(self, bot):
        self.bot = bot
        self.conversations = {}  # Store conversation history by user
        self.knowledge_base = {}  # Store loaded knowledge base documents
        self.ai_stats = {
            "total_questions": 0,
            "total_resets": 0,
            "code_executions": 0, # Track code executions
            "code_execution_errors": 0, # Track errors during execution
            "user_questions": {}  # Track questions per user
        }
        if KNOWLEDGE_BASE_DIR: # Only load if directory setup was successful
            self.load_knowledge_base()
        else:
            logger.error("Knowledge base directory not configured, cannot load KBs.")

        # Set model based on global variable availability
        self.model = model
        if not self.model:
             logger.error("Gemini model not initialized. AI Chat cog may not function.")

        logger.info("AI Chat cog initialized.")


        ##########################################
               # Start the daily reset task
        self.daily_reset.start()
        logger.info("Daily reset task started.")

    # Task runs at 06:00 UTC by default, adjust time zone if needed
    @tasks.loop(time=time(6, 0)) # Example: Run at 6:00 AM UTC
    async def daily_reset(self):
        """Reset all user conversations daily."""
        if not self.conversations:
            logger.info("Daily reset: No active conversations to reset.")
            return

        # Reset all conversations
        num_conversations = len(self.conversations)
        self.conversations.clear()

        # Update reset stats
        self.ai_stats["total_resets"] += num_conversations

        logger.info(f"Daily reset: Cleared {num_conversations} active conversations.")

    @daily_reset.before_loop
    async def before_daily_reset(self):
        """Wait for the bot to be ready before starting the task."""
        logger.info("Waiting for bot to be ready before starting daily_reset loop...")
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, daily_reset loop will start.")

    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        self.daily_reset.cancel()
        logger.info("Daily reset task cancelled on cog unload.")
        ##########################################

    # --- Helper to execute code safely using exec ---
    # WARNING: Using exec() is inherently insecure if the code source is not fully trusted.
    # Even though we instruct the AI to generate safe code based on the KB,
    # vulnerabilities in the AI or crafted KB entries could lead to malicious code execution.
    # A sandboxed environment (like Docker containers or restricted interpreters) is strongly recommended for production use.
    async def _execute_kb_code(self, code_to_run: str) -> str:
        """Executes code extracted from KB using exec within a controlled context. INTERNAL USE ONLY."""
        logger.info(f"Attempting to execute code block (length: {len(code_to_run)} chars).")
        logger.info(f"Code to execute:\n---\n{code_to_run}\n---")

        self.ai_stats["code_executions"] += 1 # Increment execution attempts stat

        code_output_buffer = io.StringIO()
        original_stdout = sys.stdout
        execution_output = ""
        execution_error = None

        try:
            # Redirect standard output to our buffer
            logger.debug("Redirecting stdout to buffer.")
            sys.stdout = code_output_buffer

            # Execute the generated code in a restricted scope (empty dict)
            logger.info("Executing code using exec()...")
            # Use asyncio.to_thread to run the blocking exec call in a separate thread
            # This prevents blocking the bot's main event loop.
            await asyncio.to_thread(exec, code_to_run, {})
            # exec(code_to_run, {}) # Original synchronous call - BLOCKS BOT!

            logger.info("Code execution via exec() completed.")

            # Get the captured output
            execution_output = code_output_buffer.getvalue()
            logger.info(f"Captured output length: {len(execution_output)}")
            logger.debug(f"Raw captured output:\n---\n{execution_output}\n---")


        except Exception as e:
            self.ai_stats["code_execution_errors"] += 1 # Increment execution error stat
            logger.error(f"Exception during code execution via exec(): {type(e).__name__}: {e}", exc_info=True) # Log traceback
            execution_error = e # Store error
            # Try to get any output captured before the error
            execution_output = code_output_buffer.getvalue() # Output buffer might have content before error
            logger.warning(f"Captured output length before error: {len(execution_output)}")
            logger.debug(f"Raw captured output (before error):\n---\n{execution_output}\n---")

        finally:
            # Always restore standard output
            logger.debug("Restoring original stdout.")
            sys.stdout = original_stdout
            code_output_buffer.close()
            logger.debug("Stdout restored, buffer closed.")

        # Format the result string
        formatted_result = ""
        if execution_output.strip():
             # Indent slightly for clarity within the final message
            # formatted_output = "\n".join([f"  {line}" for line in execution_output.strip().splitlines()])
            # Limit output preview length to avoid huge messages
            max_output_len = 500
            output_preview = execution_output.strip()
            if len(output_preview) > max_output_len:
                output_preview = output_preview[:max_output_len] + "\n... (output truncated)"
            formatted_result += f"**Execution Output:**\n```\n{output_preview}\n```\n"
        else:
            # Still note if no output was produced, unless there was an error
            if not execution_error:
                 formatted_result += "**Execution Output:**\n[No output produced by the code]\n"

        if execution_error:
             # Indent error message as well
            error_details = f"{type(execution_error).__name__}: {execution_error}"
             # Limit error length too
            max_error_len = 300
            if len(error_details) > max_error_len:
                 error_details = error_details[:max_error_len] + "... (error truncated)"
            # formatted_error = "\n".join([f"  {line}" for line in error_details.splitlines()])
            formatted_result += f"**Execution Error:**\n```\n{error_details}\n```"

        logger.info("Formatted execution result ready.")
        logger.debug(f"Formatted result string:\n---\n{formatted_result}\n---")

        # Return the combined formatted string
        return formatted_result.strip() if formatted_result else "[Code execution completed with no output or error message]"


    def load_knowledge_base(self):
        """Load all knowledge base documents from the knowledge base directory."""
        if not KNOWLEDGE_BASE_DIR or not os.path.exists(KNOWLEDGE_BASE_DIR):
            logger.error("Cannot load knowledge base: Directory path is invalid or not set.")
            return

        kb_files = glob.glob(os.path.join(KNOWLEDGE_BASE_DIR, "*.txt"))
        logger.info(f"Found {len(kb_files)} potential knowledge base files.")
        self.knowledge_base.clear() # Clear existing before loading

        for kb_file in kb_files:
            try:
                kb_name = os.path.basename(kb_file).replace(".txt", "")
                with open(kb_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.knowledge_base[kb_name] = content
                logger.info(f"Loaded knowledge base: '{kb_name}' ({len(content):,} chars)")
            except Exception as e:
                logger.error(f"Error loading knowledge base file {kb_file}: {e}", exc_info=True)

        # Log the result
        if self.knowledge_base:
            logger.info(f"Successfully loaded {len(self.knowledge_base)} knowledge base documents: {list(self.knowledge_base.keys())}")
        else:
            logger.warning("No knowledge base documents were loaded.")

    @commands.hybrid_command(
        name="ask",
        description="Ask the AI a question based on the Questfall documentation"
    )
    @app_commands.describe(question="Your question about Questfall")
    async def ask(self, ctx: commands.Context, *, question: str):
        """Asks the AI a question and returns the response, potentially executing formulas."""
        logger.info(f"Ask command received from {ctx.author.name} (ID: {ctx.author.id}) in channel {ctx.channel.id}. Question: '{question[:100]}...'")

        if not self.model:
            await ctx.reply("⚠️ The AI model is not available. Please contact the bot owner.")
            logger.error("Ask command failed: AI model not loaded.")
            return

        if not self.knowledge_base:
             await ctx.reply("⚠️ The knowledge base is currently empty or unavailable. Cannot answer questions.")
             logger.error("Ask command failed: Knowledge base not loaded.")
             return

        # Show typing indicator while generating response
        async with ctx.typing():
            try:
                # Get or create conversation for this user
                user_id = str(ctx.author.id)

                # Use 'QuestfallDocs' as the primary KB, ensure it exists
                kb_name = 'QuestfallDocs'
                if kb_name not in self.knowledge_base:
                    await ctx.reply(f"⚠️ Critical error: The primary knowledge base '{kb_name}' is missing.")
                    logger.critical(f"Primary knowledge base '{kb_name}' not found in loaded KBs: {list(self.knowledge_base.keys())}")
                    return
                kb_content = self.knowledge_base[kb_name]
                logger.info(f"Using knowledge base '{kb_name}' for question (length: {len(kb_content):,} chars).")


                if user_id not in self.conversations:
                     logger.info(f"Creating new conversation history for user {user_id}.")
                     # Start chat history. No complex initial prompt needed here as we send context each time.
                     self.conversations[user_id] = self.model.start_chat(history=[])

                chat = self.conversations[user_id]

                # Construct the full prompt for *this* specific request, including KB and instructions
                prompt_instructions = textwrap.dedent(f"""
                You are an AI assistant expert on the 'Questfall' project. Answer the user's question based *only* on the following documentation context for '{kb_name}'.

                --- DOCUMENTATION START ---
                {kb_content}
                --- DOCUMENTATION END ---

                Instructions for responding:
                1. Base all answers strictly on the provided documentation content above. Do not add external knowledge or make assumptions.
                2. If the documentation contains a mathematical formula **directly relevant** to the user's query:
                   - Explain the formula using the documentation's context.
                   - **Generate executable Python code** to calculate the formula. This code MUST include:
                     a) The function definition.
                     b) Example usage that CALLS the function. Use values from the user's question if applicable and sensible, otherwise use clear default/example values from the documentation.
                     c) `print()` statements within the example usage to output the calculation results clearly.
                   - **Wrap this entire executable Python code block** (definition, calls, prints) within the exact markers:
                     {PYTHON_EXEC_START_MARKER}
                     ```python
                     # Your Python code here...
                     # e.g., result = calculate_something(10, 5)
                     # print(f"Calculation result: {{result}}")
                     ```
                     {PYTHON_EXEC_END_MARKER}
                   - Integrate the explanation and the execution block smoothly into your overall answer. The code block should appear after the explanation.
                3. If no specific mathematical formula from the documentation is relevant, or if the user's question doesn't require a calculation, just answer based on the text.
                4. If the documentation does not contain the answer, clearly state that the information is not available in the provided docs.
                5. Be concise and maintain the tone of the documentation.
                """)

                full_prompt = f"{prompt_instructions}\n\nUSER QUESTION: {question}"

                # Log prompt length for potential token limit issues
                logger.info(f"Sending full prompt to Gemini for user {user_id} (prompt length approx: {len(full_prompt):,} chars).")
                # Avoid logging full prompt+KB in production if KB is sensitive/large
                logger.debug(f"Full prompt preview (first 500 chars):\n{full_prompt[:500]}...")

                # Generate response from Gemini
                try:
                    response = await asyncio.to_thread(chat.send_message, full_prompt)
                    # response = chat.send_message(full_prompt) # Original sync call - BLOCKS BOT!
                    ai_response_text = response.text
                    logger.info(f"Raw AI Response received (length: {len(ai_response_text):,}): {ai_response_text[:500]}...")
                except Exception as gemini_error:
                    logger.error(f"Error communicating with Gemini API: {gemini_error}", exc_info=True)
                    await ctx.reply("⚠️ Sorry, there was an error communicating with the AI service.")
                    return


                # --- Post-Processing: Check for and Execute KB Code Blocks ---
                final_response_text = ""
                last_end_pos = 0
                # Use the compiled pattern with re.DOTALL to match across newlines
                pattern = re.compile(f"{re.escape(PYTHON_EXEC_START_MARKER)}(.*?){re.escape(PYTHON_EXEC_END_MARKER)}", re.DOTALL)

                logger.info(f"Searching for code blocks using pattern: {pattern.pattern}")

                match_found = False # Flag to check if any blocks were processed
                matches = list(pattern.finditer(ai_response_text)) # Find all matches at once
                logger.info(f"Found {len(matches)} potential code blocks.")

                for match in matches:
                    match_found = True
                    start_pos, end_pos = match.span()
                    # Extract the code, removing potential ```python ``` markdown if AI added it inside markers
                    code_content_raw = match.group(1).strip()
                    # Remove outer code fences (```python ... ```) if present
                    code_to_execute = re.sub(r'^\s*```python\s*\n?', '', code_content_raw, flags=re.IGNORECASE)
                    code_to_execute = re.sub(r'\n?\s*```\s*$', '', code_to_execute)
                    code_to_execute = code_to_execute.strip() # Final strip

                    logger.info(f"Processing code block. Start: {start_pos}, End: {end_pos}")
                    # Limit logged code length
                    logger.debug(f"Extracted code content (first 300 chars):\n---\n{code_to_execute[:300]}\n---")

                    # Append text segment before the current code block match
                    final_response_text += ai_response_text[last_end_pos:start_pos]

                    if not code_to_execute:
                        # Append placeholder for empty block
                        placeholder = "\n[Notice: An empty Python execution block was generated by the AI.]\n"
                        if final_response_text and not final_response_text.endswith('\n\n'): placeholder = '\n' + placeholder # Add spacing
                        final_response_text += placeholder
                        logger.warning("Found and skipped empty Python execution block in AI response.")
                    else:
                        # Execute the code and get formatted result string
                        logger.info("Calling _execute_kb_code...")
                        execution_result_formatted = await self._execute_kb_code(code_to_execute)
                        logger.info("Received result from _execute_kb_code.")
                        # Append the formatted result
                        # Add newlines for separation and formatting
                        # bh commented
                        # separator_start = "\n\n--- Code Execution Result ---\n"
                        # separator_end = "\n--- End Code Execution ---\n\n"
                        if final_response_text and not final_response_text.endswith('\n'): separator_start = '\n' + separator_start # Ensure newline before
                        final_response_text += f"{separator_start}{execution_result_formatted}{separator_end}"


                    # Update the position for the next segment
                    last_end_pos = end_pos

                # Append any remaining text after the last code block (or the whole text if no blocks found)
                final_response_text += ai_response_text[last_end_pos:]

                if not match_found:
                    logger.info("No executable code blocks found in the AI response.")
                    # final_response_text already contains the full ai_response_text in this case
                else:
                     logger.info(f"Processed {len(matches)} code blocks. Final response length: {len(final_response_text):,}")


                # --- Send Final Response to Discord ---
                logger.info("Preparing to send final response to Discord.")
                if not final_response_text.strip():
                     logger.warning("Final response text is empty or whitespace after processing.")
                     await ctx.reply("Received an empty response from the AI.")
                else:
                    # Use textwrap for splitting long messages
                    max_length = 1990 # Discord limit slightly lower than 2000 for safety
                    if len(final_response_text) > max_length:
                        logger.info(f"Response length ({len(final_response_text):,}) exceeds {max_length} chars, splitting.")
                        parts = textwrap.wrap(final_response_text, max_length, replace_whitespace=False, drop_whitespace=False, break_long_words=False, break_on_hyphens=False)
                        for i, part in enumerate(parts):
                            if i == 0:
                                await ctx.reply(part)
                            else:
                                await ctx.send(part) # Use send for subsequent parts
                            logger.debug(f"Sent part {i+1}/{len(parts)} of the response (length: {len(part):,}).")
                    else:
                        logger.info(f"Sending response (length: {len(final_response_text):,}) as a single message.")
                        await ctx.reply(final_response_text)
                logger.info(f"Final response sent successfully to {ctx.author.name}.")


                # Update AI usage statistics
                self.ai_stats["total_questions"] += 1

                # Update per-user stats
                user_id = str(ctx.author.id) # Ensure user_id is string for dict key
                if user_id not in self.ai_stats["user_questions"]:
                    self.ai_stats["user_questions"][user_id] = {
                        "username": ctx.author.name, # Store username for display
                        "count": 0,
                        "last_question": None,
                        "last_timestamp": None
                    }

                self.ai_stats["user_questions"][user_id]["count"] += 1
                # Truncate long questions for stats
                truncated_question = question[:100] + "..." if len(question) > 100 else question
                self.ai_stats["user_questions"][user_id]["last_question"] = truncated_question
                self.ai_stats["user_questions"][user_id]["last_timestamp"] = ctx.message.created_at.isoformat() # Use ISO format for consistency

                logger.info(f"Updated stats for user {ctx.author.name}. Total questions: {self.ai_stats['total_questions']}")

            except Exception as e:
                logger.error(f"Error during ask command processing: {e}", exc_info=True)
                await ctx.reply(f"⚠️ An unexpected error occurred while processing your request. Please try again later or contact support.")

    @commands.hybrid_command(
        name="reset_chat",
        description="Reset your conversation history with the AI"
    )
    async def reset_chat(self, ctx: commands.Context):
        """Resets the conversation history for the user."""
        user_id = str(ctx.author.id)
        logger.info(f"Reset_chat command received from {ctx.author.name} (ID: {user_id})")

        if user_id in self.conversations:
            del self.conversations[user_id]

            # Update reset stats
            self.ai_stats["total_resets"] += 1

            await ctx.reply("✅ Your conversation history has been reset. Start a new conversation with `/ask`!")
            logger.info(f"Reset conversation history for {ctx.author.name}. Total resets: {self.ai_stats['total_resets']}")
        else:
            await ctx.reply("You don't have an active conversation history to reset.")
            logger.info(f"User {ctx.author.name} attempted reset, but had no active conversation.")

    @commands.hybrid_command(
        name="kb_list",
        description="List all available knowledge base documents"
    )
    @commands.has_permissions(manage_messages=True) # Example permission
    async def kb_list(self, ctx: commands.Context):
        """Lists all available knowledge base documents."""
        logger.info(f"kb_list command received from {ctx.author.name}")
        if not self.knowledge_base:
            await ctx.reply("⚠️ No knowledge base documents are currently loaded.")
            return

        # Create an embed with KB info
        embed = discord.Embed(
            title="Available Knowledge Base Documents",
            description=f"Found {len(self.knowledge_base)} document(s):",
            color=discord.Color.blue()
        )

        for kb_name, content in self.knowledge_base.items():
            # Truncate content preview safely
            content_preview = textwrap.shorten(content, width=150, placeholder="...")
            embed.add_field(
                name=f"📄 {kb_name}",
                value=f"Size: {len(content):,} characters\n*Preview:* {content_preview}",
                inline=False
            )

        await ctx.reply(embed=embed)
        logger.info(f"Displayed {len(self.knowledge_base)} KBs to {ctx.author.name}")

    @commands.hybrid_command(
        name="kb_add",
        description="Add/Update a knowledge base document from a .txt file attachment"
    )
    @commands.has_permissions(administrator=True) # Restrict to Admins
    @app_commands.describe(name="The name to assign to this knowledge base (e.g., QuestfallDocs)")
    async def kb_add(self, ctx: commands.Context, name: str):
        """Adds or updates a knowledge base document from a text file attachment."""
        logger.info(f"kb_add command received from {ctx.author.name} for KB name '{name}'")
        if not KNOWLEDGE_BASE_DIR:
             await ctx.reply("⚠️ Cannot add knowledge base: Base directory is not configured correctly.")
             logger.error("kb_add failed: KNOWLEDGE_BASE_DIR not set.")
             return

        if not ctx.message.attachments:
            await ctx.reply("⚠️ You must attach a single text file (`.txt`) containing the knowledge base content.")
            return

        if len(ctx.message.attachments) > 1:
             await ctx.reply("⚠️ Please attach only one file at a time.")
             return

        attachment = ctx.message.attachments[0]
        if not attachment.filename.lower().endswith('.txt'):
            await ctx.reply("⚠️ Invalid file type. Only `.txt` files are supported for knowledge base documents.")
            return

        # Sanitize the name slightly (e.g., remove path traversal, limit chars)
        safe_name = re.sub(r'[^\w\-]+', '_', name) # Allow word chars, hyphen, replace others with underscore
        if not safe_name or len(safe_name) > 50:
             await ctx.reply("⚠️ Invalid name provided. Please use a shorter name with letters, numbers, hyphens, or underscores.")
             return
        if safe_name != name:
             logger.warning(f"Sanitized KB name from '{name}' to '{safe_name}'")
             name = safe_name # Use the sanitized name

        try:
            # Download the attachment content
            content_bytes = await attachment.read()
            try:
                 content_str = content_bytes.decode('utf-8')
            except UnicodeDecodeError:
                 await ctx.reply("⚠️ Error decoding the file. Please ensure it is UTF-8 encoded.")
                 logger.error(f"Failed to decode attached file {attachment.filename} as UTF-8.")
                 return

            # Save to knowledge base directory
            kb_path = os.path.join(KNOWLEDGE_BASE_DIR, f"{name}.txt")
            with open(kb_path, 'w', encoding='utf-8') as f:
                f.write(content_str)

            # Add/Update in-memory knowledge base
            self.knowledge_base[name] = content_str

            await ctx.reply(f"✅ Knowledge base document '{name}' has been added/updated successfully! ({len(content_str):,} chars)")
            logger.info(f"Added/Updated knowledge base: '{name}' ({len(content_str):,} chars) from file {attachment.filename}")

        except discord.HTTPException as e:
             logger.error(f"Discord HTTP error downloading attachment for kb_add '{name}': {e}", exc_info=True)
             await ctx.reply(f"⚠️ Failed to download the attachment: {e}")
        except IOError as e:
             logger.error(f"IOError writing knowledge base file for '{name}': {e}", exc_info=True)
             await ctx.reply(f"⚠️ Failed to save the knowledge base file to disk: {e}")
        except Exception as e:
            logger.error(f"Unexpected error adding knowledge base '{name}': {e}", exc_info=True)
            await ctx.reply(f"⚠️ An unexpected error occurred while adding the knowledge base: {str(e)}")

    @commands.hybrid_command(
        name="kb_remove",
        description="Remove a knowledge base document"
    )
    @commands.has_permissions(administrator=True) # Restrict to Admins
    @app_commands.describe(name="The exact name of the knowledge base to remove")
    async def kb_remove(self, ctx: commands.Context, name: str):
        """Removes a knowledge base document by name."""
        logger.info(f"kb_remove command received from {ctx.author.name} for KB name '{name}'")

        if name not in self.knowledge_base:
            await ctx.reply(f"⚠️ Knowledge base '{name}' not found. Use `/kb_list` to see available KBs.")
            return

        if not KNOWLEDGE_BASE_DIR:
             await ctx.reply("⚠️ Cannot remove knowledge base file: Base directory is not configured correctly.")
             logger.error("kb_remove failed: KNOWLEDGE_BASE_DIR not set.")
             # Still try to remove from memory
             try:
                 del self.knowledge_base[name]
                 await ctx.reply(f"✅ Knowledge base '{name}' removed from memory, but unable to delete file (directory issue).")
                 logger.warning(f"Removed KB '{name}' from memory but couldn't access filesystem.")
             except Exception as e_mem:
                 logger.error(f"Error removing KB '{name}' from memory: {e_mem}")
                 await ctx.reply(f"⚠️ Error removing KB '{name}' from memory: {e_mem}")
             return

        try:
            # Remove from in-memory knowledge base first
            del self.knowledge_base[name]
            logger.info(f"Removed '{name}' from in-memory knowledge base.")

            # Remove file from disk
            kb_path = os.path.join(KNOWLEDGE_BASE_DIR, f"{name}.txt")
            if os.path.exists(kb_path):
                os.remove(kb_path)
                logger.info(f"Deleted knowledge base file: {kb_path}")
                await ctx.reply(f"✅ Knowledge base document '{name}' has been removed successfully (from memory and disk).")
            else:
                 logger.warning(f"Knowledge base file not found on disk for removal: {kb_path}, but removed from memory.")
                 await ctx.reply(f"✅ Knowledge base document '{name}' removed from memory (file was not found on disk).")

        except KeyError:
             # Should not happen due to initial check, but handle defensively
             await ctx.reply(f"⚠️ Knowledge base '{name}' was not found in memory (concurrent modification?).")
             logger.warning(f"KB '{name}' disappeared before memory deletion in kb_remove.")
        except OSError as e:
             logger.error(f"OSError removing knowledge base file for '{name}': {e}", exc_info=True)
             await ctx.reply(f"⚠️ Error removing the knowledge base file from disk: {e}. It has been removed from active memory.")
        except Exception as e:
            logger.error(f"Unexpected error removing knowledge base '{name}': {e}", exc_info=True)
            # Attempt to restore in-memory KB if deletion failed unexpectedly after file ops? Maybe too complex.
            await ctx.reply(f"⚠️ An unexpected error occurred while removing the knowledge base: {str(e)}")

    @commands.hybrid_command(
        name="kb_reload",
        description="Reload all knowledge base documents from disk"
    )
    @commands.has_permissions(administrator=True) # Restrict to Admins
    async def kb_reload(self, ctx: commands.Context):
        """Reloads all knowledge base documents from the configured directory."""
        logger.info(f"kb_reload command received from {ctx.author.name}")
        if not KNOWLEDGE_BASE_DIR:
             await ctx.reply("⚠️ Cannot reload knowledge base: Base directory is not configured correctly.")
             logger.error("kb_reload failed: KNOWLEDGE_BASE_DIR not set.")
             return

        try:
            # Clear existing knowledge base (in memory)
            num_before = len(self.knowledge_base)
            self.knowledge_base.clear()
            logger.info(f"Cleared {num_before} KBs from memory.")

            # Reload all documents
            self.load_knowledge_base() # This function already logs details
            num_after = len(self.knowledge_base)

            if num_after > 0:
                await ctx.reply(f"✅ Successfully reloaded {num_after} knowledge base documents!")
            else:
                await ctx.reply("✅ Knowledge base reloaded. No `.txt` documents were found in the directory.")

            logger.info(f"Reloaded knowledge base: {num_after} documents loaded.")
        except Exception as e:
            logger.error(f"Error during knowledge base reload: {e}", exc_info=True)
            await ctx.reply(f"⚠️ An error occurred while reloading the knowledge base: {str(e)}")

    def get_ai_stats(self):
        """Returns AI usage statistics, potentially for a web dashboard or stats command."""
        logger.debug("get_ai_stats called.")
        # Get total active conversations
        active_conversations = len(self.conversations)

        # Create a clean copy of stats for the dashboard/output
        # Use .get() for stats that might not exist yet if no activity occurred
        stats = {
            "total_questions": self.ai_stats.get("total_questions", 0),
            "total_resets": self.ai_stats.get("total_resets", 0),
            "active_conversations": active_conversations,
            "code_executions_attempted": self.ai_stats.get("code_executions", 0),
            "code_execution_errors": self.ai_stats.get("code_execution_errors", 0),
            "kb_documents_loaded": len(self.knowledge_base),
            "kb_names": list(self.knowledge_base.keys()),
            "top_users": [] # Populated below
        }

        # Get top 5 users by question count
        user_questions_data = self.ai_stats.get("user_questions", {})
        if user_questions_data:
            # Sort items (user_id, data_dict) by the 'count' within the data_dict
            sorted_users = sorted(
                user_questions_data.items(),
                key=lambda item: item[1].get("count", 0), # Safe access to count
                reverse=True
            )[:5] # Limit to top 5

            # Format for dashboard/output
            stats["top_users"] = [
                {
                    # Use .get() for safer access to dictionary keys
                    "username": user_data.get("username", "Unknown"),
                    "question_count": user_data.get("count", 0),
                    "last_question": user_data.get("last_question", "N/A"),
                    "last_timestamp": user_data.get("last_timestamp", "N/A")
                }
                for user_id, user_data in sorted_users # Iterate through the sorted list of tuples
            ]
        else:
             logger.info("No user question data available for stats.")


        logger.debug(f"Returning AI stats: {stats}")
        return stats

    # Example command to display stats (optional)
    @commands.hybrid_command(name="ai_stats", description="Show usage statistics for the AI chat.")
    @commands.cooldown(1, 10, commands.BucketType.user) # Prevent spamming
    async def ai_stats_command(self, ctx: commands.Context):
        """Displays AI usage statistics."""
        logger.info(f"ai_stats command received from {ctx.author.name}")
        stats = self.get_ai_stats()

        embed = discord.Embed(title="AI Chat Statistics", color=discord.Color.green())
        embed.add_field(name="Total Questions Asked", value=f"{stats['total_questions']:,}", inline=True)
        embed.add_field(name="Active Conversations", value=f"{stats['active_conversations']:,}", inline=True)
        embed.add_field(name="Total Resets", value=f"{stats['total_resets']:,}", inline=True)

        embed.add_field(name="Code Executions Attempted", value=f"{stats['code_executions_attempted']:,}", inline=True)
        embed.add_field(name="Code Execution Errors", value=f"{stats['code_execution_errors']:,}", inline=True)
        embed.add_field(name="Knowledge Docs Loaded", value=f"{stats['kb_documents_loaded']:,}", inline=True)

        if stats['kb_names']:
             embed.add_field(name="Loaded KB Names", value=", ".join(stats['kb_names']) or "None", inline=False)

        if stats['top_users']:
             top_users_str = "\n".join([
                 f"**{user['username']}**: {user['question_count']} questions (Last: *{user['last_question']}*)"
                 for user in stats['top_users']
             ])
             embed.add_field(name="Top Users (by questions)", value=top_users_str, inline=False)
        else:
             embed.add_field(name="Top Users", value="No user activity recorded yet.", inline=False)

        embed.set_footer(text="Stats since last bot restart or cog load.")
        await ctx.reply(embed=embed)


async def setup(bot):
    """Add the cog to the bot."""
    # Check prerequisites before adding cog
    if not GEMINI_API_KEY:
        logger.critical("Cannot add AI Chat cog: GEMINI_API_KEY is not set.")
        # Optionally raise an error or handle this depending on bot structure
        # raise commands.ExtensionFailed("AIChat", "GEMINI_API_KEY not set.")
        return # Prevent adding the cog

    if not model:
         logger.critical("Cannot add AI Chat cog: Gemini model failed to initialize.")
         # raise commands.ExtensionFailed("AIChat", "Gemini model initialization failed.")
         return # Prevent adding the cog

    if not KNOWLEDGE_BASE_DIR:
         logger.error("Adding AI Chat cog, but Knowledge Base directory setup failed. KB features might be limited.")
         # Decide if this is critical enough to prevent loading

    try:
        await bot.add_cog(AIChat(bot))
        logger.info("Successfully added AI Chat cog (AIChat) to bot.")
    except Exception as e:
        logger.critical(f"Failed to add AI Chat cog: {e}", exc_info=True)
        # raise commands.ExtensionFailed("AIChat", f"Failed to add cog: {e}")