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
import subprocess
import asyncio
import sys
import textwrap # Already used, but ensure it's imported


# --- Define Markers for Executable Code Blocks ---
# Use unique, unlikely strings. Put these around Python code in your .txt files.
PYTHON_EXEC_START_MARKER = "%%PYTHON_EXECUTE_BLOCK_START%%"
PYTHON_EXEC_END_MARKER = "%%PYTHON_EXECUTE_BLOCK_END%%"
# Example in QuestfallDocs.txt:
# Some documentation text...
# To calculate damage, use the following formula:
# %%PYTHON_EXECUTE_BLOCK_START%%
# def calculate_damage(attack, defense):
#     base_damage = max(1, attack - defense * 0.8)
#     crit_chance = 0.1
#     # import random # Avoid imports if possible, or pre-allow safe ones
#     # if random.random() < crit_chance:
#     #     base_damage *= 1.5
#     return round(base_damage)
#
# # Example usage (won't be run automatically, just context for the definition)
# # print(calculate_damage(100, 50))
# %%PYTHON_EXECUTE_BLOCK_END%%
# More documentation text...
# ----------------------------------------------------


# Set up logging
logger = logging.getLogger('discord_bot.ai_chat')

# Configure the Gemini API with the key from environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


# Set up the Gemini Pro model for chat with specific generation config
generation_config = genai.types.GenerationConfig(
    temperature=0.1,  # Lower temperature for more precise answers
    # top_p=0.8,
    # top_k=30,
    # max_output_tokens=200  # Adjust as needed
)

# Set up the Gemini model
model = genai.GenerativeModel('gemini-2.0-flash-lite', generation_config=generation_config)

# Knowledge base directory
# KNOWLEDGE_BASE_DIR = "knowledge_base"
# os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge_base")
os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
# print(f"KNOWLEDGE_BASE_DIR: {KNOWLEDGE_BASE_DIR}")
logger.info(f"KNOWLEDGE_BASE_DIR: {KNOWLEDGE_BASE_DIR}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"File exists: {os.path.exists(KNOWLEDGE_BASE_DIR)}")

# List all files in the directory
files = os.listdir(KNOWLEDGE_BASE_DIR)
logger.info(f"Files in knowledge base directory: {files}")

class AIChat(commands.Cog):
    """Cog for AI chat functionality using Google's Gemini model."""

    def __init__(self, bot):
        self.bot = bot
        self.conversations = {}  # Store conversation history by user
        self.knowledge_base = {}  # Store loaded knowledge base documents
        self.ai_stats = {
            "total_questions": 0,
            "total_resets": 0,
            "user_questions": {}  # Track questions per user
        }
        self.load_knowledge_base()
        logger.info("AI Chat cog initialized with Gemini model")


        ##########################################
               # Start the daily reset task
        self.daily_reset.start()

    @tasks.loop(time=time(20, 19))  # Run at 6:00 AM
    async def daily_reset(self):
        """Reset all user conversations at 6 AM."""
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
        await self.bot.wait_until_ready()

    def cog_unload(self):
        """Clean up when the cog is unloaded."""
        self.daily_reset.cancel()
        ##########################################

   # --- Helper to execute code safely using subprocess ---
    async def _execute_kb_code(self, code_to_run: str) -> str:
        """Executes code extracted from KB using subprocess. INTERNAL USE ONLY."""
        logger.info(f"Attempting to execute code extracted from KB:\n{code_to_run[:200]}")
        try:
            # Run in a separate process using asyncio.to_thread
            process = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, '-c', code_to_run], # Use sys.executable
                capture_output=True,
                text=True,
                timeout=10,  # Short timeout for KB code execution
                check=False
            )

            result_output = ""
            if process.stdout:
                result_output += f"**Execution Output:**\n```\n{process.stdout}\n```\n"
            if process.stderr:
                result_output += f"**Execution Errors:**\n```\n{process.stderr}\n```"
            if not result_output:
                result_output = "[No output from execution]"
            exit_code = process.returncode
            result_output += f"*Exit Code: {exit_code}*"
            print(f"Result_output: {result_output}")
            logger.info(f"KB code execution finished. Exit code: {exit_code}")
            return result_output

        except subprocess.TimeoutExpired:
            logger.warning("KB code execution timed out.")
            return "[Code execution timed out after 10 seconds]"
        except Exception as e:
            logger.exception(f"Error during subprocess execution of KB code: {e}")
            return f"[Error during code execution: {type(e).__name__}]"

        
    def load_knowledge_base(self):
        """Load all knowledge base documents from the knowledge base directory."""
        kb_files = glob.glob(os.path.join(KNOWLEDGE_BASE_DIR, "*.txt"))
        
        for kb_file in kb_files:
            try:
                kb_name = os.path.basename(kb_file).replace(".txt", "")
                with open(kb_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.knowledge_base[kb_name] = content
                logger.info(f"Loaded knowledge base: {kb_name} ({len(content)} chars)")
            except Exception as e:
                logger.error(f"Error loading knowledge base {kb_file}: {e}")
                
        # Log the result
        if self.knowledge_base:
            logger.info(f"Loaded {len(self.knowledge_base)} knowledge base documents")
        else:
            logger.info("No knowledge base documents found")

    @commands.hybrid_command(
        name="ask",
        description="Ask the AI a question and get a response"
    )
    async def ask(self, ctx, *, question: str):
        """Asks the AI a question and returns the response."""
        logger.info(f"Ask command received from {ctx.author.name}: {question}")
        if not GEMINI_API_KEY:
            await ctx.reply("⚠️ Gemini API key is not configured. Please ask the bot owner to set it up.")
            return

        # # Determine if the user invoking the command is the owner
        # is_owner_invoking = ctx.author.id == OWNER_ID
        # if OWNER_ID == 123456789012345678: # Check if placeholder ID is still used
        #      is_owner_invoking = False # Disable execution if owner ID not set
        #      logger.warning("OWNER_ID is not set. Execution of KB code blocks is disabled.")

        # Show typing indicator while generating response
        async with ctx.typing():
            try:
                # Get or create conversation for this user
                user_id = str(ctx.author.id)
                                
                # Enhance the prompt with KB content
                using_kb = True
                kb_name = 'QuestfallDocs'
                if using_kb and kb_name and kb_name in self.knowledge_base:
                    kb_content = self.knowledge_base[kb_name]
  
                if user_id not in self.conversations:
                    # Initialize conversation with system prompts - don't mention knowledge base in general usage
                    # initial_prompt = "You are a helpful AI assistant that answers questions based on your training."
                    initial_prompt = f"""You are an AI assistant with access to detailed documentation {kb_name} {kb_content} about Questfall project. Your role is to answer questions or provide explanations based solely on the information available in the documentation. Avoid assumptions or external knowledge unless explicitly asked. Provide clear, concise, and context-accurate responses. If there is a formula in LaTeX format use it to calculate the answer. If the documentation doesn’t contain the answer, state this politely"""
                    self.conversations[user_id] = model.start_chat(history=[])
                    
                    # Set the initial prompt as a system message
                    self.conversations[user_id].send_message(initial_prompt)
                
                chat = self.conversations[user_id]
                
                # Check if user wants to query specific knowledge base
                # kb_prefix = "using:"
                # kb_name = None
                # modified_question = question
                # using_kb = False
                
                # Only use knowledge base if the user explicitly requests it with the using: prefix
                # if kb_prefix in question.lower():
                #     parts = question.split(kb_prefix, 1)[1].strip().split(" ", 1)
                #     if len(parts) > 1:
                #         kb_name = parts[0].strip()
                #         modified_question = parts[1].strip()
                #         using_kb = True
                

                # Prepare the prompt - only use knowledge base when explicitly requested
                # prompt = modified_question
                # if using_kb and kb_name and kb_name in self.knowledge_base:
                    # Enhance the prompt with KB content
                    # kb_content = self.knowledge_base[kb_name]
#                     prompt = f"""Please answer the following question based ONLY on the provided knowledge base content.
# If the answer cannot be found in the knowledge base, say so clearly:

# KNOWLEDGE BASE: {kb_name}
# {kb_content}

# USER QUESTION: {modified_question}"""

#                     prompt = f"""I have a set of documentation {kb_name} {kb_content} that serves as the primary source of truth for Questfall project. Based on the content provided within this documentation, answer the following questions or address the topics raised with the most accurate and relevant information. Please ensure that responses are aligned with the tone and style of the documentation, and if uncertain, clearly state the limits of the information provided.
# USER QUESTION: {modified_question}"""
#                     prompt = f"""You are an AI assistant with access to detailed documentation {kb_name} {kb_content} about Questfall project. Your role is to answer questions or provide explanations based solely on the information available in the documentation. Avoid assumptions or external knowledge unless explicitly asked. Provide clear, concise, and context-accurate responses. If the documentation doesn’t contain the answer, state this politely
# USER QUESTION: {modified_question}"""
                prompt = f"""USER QUESTION: {question}"""

                logger.info(f"Using knowledge base '{kb_name}' for question")
                # elif using_kb and kb_name:
                #     # User tried to use a non-existent knowledge base
                #     await ctx.reply(f"⚠️ Knowledge base '{kb_name}' not found. Use `!kb_list` to see available knowledge bases.")
                #     return
                
                # Generate response from Gemini
                response = chat.send_message(f"{prompt}. Make sure to check for Python code. If the documentation contains Python code blocks marked with {PYTHON_EXEC_START_MARKER} and {PYTHON_EXEC_END_MARKER}, include the entire block (including start and end markers) in your response. Make sure to pass the variable to Python function when executing the code.")

                ai_response_text = response.text

                logger.info(f"AI Response: {ai_response_text}")

  # --- Post-Processing: Check for and Execute KB Code Blocks ---

                final_response_text = ""
                last_end_pos = 0
                pattern = re.compile(f"{re.escape(PYTHON_EXEC_START_MARKER)}(.*?){re.escape(PYTHON_EXEC_END_MARKER)}", re.DOTALL)

                # ---> ADD THIS PRINT <---
                print(f"--- INFO: Searching for pattern: {pattern.pattern} ---")

                match_found = False # Flag to check if loop runs
                for match in pattern.finditer(ai_response_text):
                    match_found = True # Mark that we entered the loop
                    print(f"--- INFO: Match Found! Span: {match.span()} ---") # See where it matched
                    code_to_execute = match.group(1).strip()
                    print(f"--- INFO: Extracted Code:\n{code_to_execute}\n---") # See what was extracted
                    start_pos, end_pos = match.span()
                    # ... rest of your loop logic ...

                    print(f"Found code block!!!!!!: {code_to_execute}")

                    # Append text before the match
                    final_response_text += ai_response_text[last_end_pos:start_pos]

                    if not code_to_execute:
                        final_response_text += "[Empty Python execution block found]"
                        logger.info("Found empty Python execution block in AI response.")

                    else:
                        # execution_result =exec(code_to_execute)
                        execution_result = await self._execute_kb_code(code_to_execute)
                        final_response_text += f"\n--- Executed Code Block ---\n{execution_result}\n--- End Execution ---\n"

                    # # *** SECURITY CHECK: Only execute if the command invoker is the owner ***
                    # elif is_owner_invoking:
                    #     logger.info(f"Owner {ctx.author.name} triggered execution of KB code block.")
                    #     execution_result = await self._execute_kb_code(code_to_execute)
                    #     final_response_text += f"\n--- Executed Code Block ---\n{execution_result}\n--- End Execution ---\n"
                    # else:
                    #     logger.info(f"Non-owner {ctx.author.name} triggered KB code block. Execution denied.")
                    #     final_response_text += f"\n[Code block found, execution restricted to bot owner]\n" # Placeholder

                    last_end_pos = end_pos

                # Append any remaining text after the last match
                final_response_text += ai_response_text[last_end_pos:]

                # If no matches were found, final_response_text is just the original response
                if last_end_pos == 0:
                     final_response_text = ai_response_text


                # --- Send Final Response to Discord ---
                if not final_response_text:
                     await ctx.reply("Received an empty response from the AI.")
                elif len(final_response_text) > 1990: # Use textwrap for splitting
                    parts = textwrap.wrap(final_response_text, 1990, replace_whitespace=False, drop_whitespace=False)
                    for i, part in enumerate(parts):
                        if i == 0: await ctx.reply(part)
                        else: await ctx.send(part)
                else:
                    await ctx.reply(final_response_text)


                
                # # # Format and send the response - but don't send duplicates
                # # # Only reply once - ctx.reply automatically sends to the channel
                # if len(response.text) > 2000:
                #     # Split into chunks if response is too long for Discord
                #     chunks = [response.text[i:i+2000] for i in range(0, len(response.text), 2000)]
                #     for i, chunk in enumerate(chunks):
                #         if i == 0:
                #             await ctx.reply(chunk)
                #         else:
                #             await ctx.send(chunk)
                # else:
                #     await ctx.reply(response.text)
                
                # print(f"AI: {response.text}")
                
                # Update AI usage statistics
                self.ai_stats["total_questions"] += 1
                
                # Update per-user stats
                user_id = str(ctx.author.id)
                if user_id not in self.ai_stats["user_questions"]:
                    self.ai_stats["user_questions"][user_id] = {
                        "username": ctx.author.name,
                        "count": 0,
                        "last_question": None,
                        "last_timestamp": None
                    }
                
                self.ai_stats["user_questions"][user_id]["count"] += 1
                self.ai_stats["user_questions"][user_id]["last_question"] = question[:100] + "..." if len(question) > 100 else question
                self.ai_stats["user_questions"][user_id]["last_timestamp"] = ctx.message.created_at.isoformat()
                
                logger.info(f"Generated AI response for {ctx.author.name} ({len(response.text)} chars)")
                
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
                await ctx.reply(f"⚠️ Sorry, I couldn't generate a response: {str(e)}")

    @commands.hybrid_command(
        name="reset_chat",
        description="Reset your conversation history with the AI"
    )
    async def reset_chat(self, ctx):
        """Resets the conversation history for the user."""
        user_id = str(ctx.author.id)
        
        if user_id in self.conversations:
            del self.conversations[user_id]
            
            # Update reset stats
            self.ai_stats["total_resets"] += 1
            
            await ctx.reply("✅ Your conversation history has been reset. Start a new conversation with `!ask`!")
            logger.info(f"Reset conversation history for {ctx.author.name}")
        else:
            await ctx.reply("You don't have any active conversations to reset.")
            
    @commands.hybrid_command(
        name="kb_list",
        description="List all available knowledge base documents"
    )
    @commands.has_permissions(manage_messages=True)
    async def kb_list(self, ctx):
        """Lists all available knowledge base documents."""
        if not self.knowledge_base:
            await ctx.reply("⚠️ No knowledge base documents have been added yet.")
            return
            
        # Create an embed with KB info
        embed = discord.Embed(
            title="Knowledge Base Documents",
            description="Here are the available knowledge base documents:",
            color=discord.Color.blue()
        )
        
        for kb_name, content in self.knowledge_base.items():
            # Truncate content if it's too long
            content_preview = content[:100] + "..." if len(content) > 100 else content
            embed.add_field(
                name=kb_name,
                value=f"Size: {len(content)} chars\nPreview: {content_preview}",
                inline=False
            )
            
        await ctx.reply(embed=embed)
        
    @commands.hybrid_command(
        name="kb_add",
        description="Add a new knowledge base document from a text file attachment"
    )
    @commands.has_permissions(administrator=True)
    async def kb_add(self, ctx, name: str):
        """Adds a new knowledge base document from a text file attachment."""
        if not ctx.message.attachments:
            await ctx.reply("⚠️ You must attach a text file containing the knowledge base content.")
            return
            
        attachment = ctx.message.attachments[0]
        if not attachment.filename.endswith('.txt'):
            await ctx.reply("⚠️ Only .txt files are supported for knowledge base documents.")
            return
            
        try:
            # Download the attachment
            content = await attachment.read()
            content_str = content.decode('utf-8')
            
            # Save to knowledge base directory
            kb_path = os.path.join(KNOWLEDGE_BASE_DIR, f"{name}.txt")
            with open(kb_path, 'w', encoding='utf-8') as f:
                f.write(content_str)
                
            # Add to in-memory knowledge base
            self.knowledge_base[name] = content_str
            
            await ctx.reply(f"✅ Knowledge base document '{name}' has been added successfully! ({len(content_str)} chars)")
            logger.info(f"Added knowledge base: {name} ({len(content_str)} chars)")
        except Exception as e:
            logger.error(f"Error adding knowledge base: {e}")
            await ctx.reply(f"⚠️ Error adding knowledge base: {str(e)}")
            
    @commands.hybrid_command(
        name="kb_remove",
        description="Remove a knowledge base document"
    )
    @commands.has_permissions(administrator=True)
    async def kb_remove(self, ctx, name: str):
        """Removes a knowledge base document."""
        if name not in self.knowledge_base:
            await ctx.reply(f"⚠️ Knowledge base '{name}' not found.")
            return
            
        try:
            # Remove from in-memory knowledge base
            del self.knowledge_base[name]
            
            # Remove file
            kb_path = os.path.join(KNOWLEDGE_BASE_DIR, f"{name}.txt")
            if os.path.exists(kb_path):
                os.remove(kb_path)
                
            await ctx.reply(f"✅ Knowledge base document '{name}' has been removed.")
            logger.info(f"Removed knowledge base: {name}")
        except Exception as e:
            logger.error(f"Error removing knowledge base: {e}")
            await ctx.reply(f"⚠️ Error removing knowledge base: {str(e)}")
            
    @commands.hybrid_command(
        name="kb_reload",
        description="Reload all knowledge base documents"
    )
    @commands.has_permissions(administrator=True)
    async def kb_reload(self, ctx):
        """Reloads all knowledge base documents."""
        try:
            # Clear existing knowledge base
            self.knowledge_base.clear()
            
            # Reload all documents
            self.load_knowledge_base()
            
            if self.knowledge_base:
                await ctx.reply(f"✅ Successfully reloaded {len(self.knowledge_base)} knowledge base documents!")
            else:
                await ctx.reply("✅ Knowledge base reloaded. No documents found.")
                
            logger.info(f"Reloaded knowledge base: {len(self.knowledge_base)} documents")
        except Exception as e:
            logger.error(f"Error reloading knowledge base: {e}")
            await ctx.reply(f"⚠️ Error reloading knowledge base: {str(e)}")
    
    def get_ai_stats(self):
        """Returns AI usage statistics for the web dashboard."""
        # Get total active conversations
        active_conversations = len(self.conversations)
        
        # Create a clean copy of stats for the dashboard
        stats = {
            "total_questions": self.ai_stats["total_questions"],
            "total_resets": self.ai_stats["total_resets"],
            "active_conversations": active_conversations,
            "kb_documents": len(self.knowledge_base),
            "kb_names": list(self.knowledge_base.keys()),
            "top_users": []
        }
        
        # Get top 5 users by question count
        if self.ai_stats["user_questions"]:
            sorted_users = sorted(
                self.ai_stats["user_questions"].items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )[:5]
            
            # Format for dashboard
            stats["top_users"] = [
                {
                    "username": user_data["username"],
                    "question_count": user_data["count"],
                    "last_question": user_data["last_question"] or "N/A",
                    "last_timestamp": user_data["last_timestamp"] or "N/A"
                }
                for _, user_data in sorted_users
            ]
        
        return stats

async def setup(bot):
    """Add the cog to the bot."""
    if GEMINI_API_KEY:
        await bot.add_cog(AIChat(bot))
        logger.info("Added AI chat cog to bot")
    else:
        logger.warning("Gemini API key not found. AI chat functionality disabled.")