import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def detect_intent_and_extract(user_input):
    """
    Detect user intent and extract a clean query using GPT-4o.
    Falls back to rule-based detection only if GPT fails.
    """
    try:
        result = detect_intent_and_extract_gpt(user_input)
        if result and result.get("intent"):
            return result
    except Exception as e:
        print("❌ GPT intent fallback error:", e)

    # 🔁 Fallback: basic rule-based detection (very minimal)
    input_lower = user_input.strip().lower()
    file_keywords = ["file", "document", "report", "sheet", "policy"]
    for kw in file_keywords:
        if kw in input_lower:
            return {
                "intent": "file_search",
                "data": input_lower.replace(kw, "").strip()
            }

    return {"intent": "general_response", "data": ""}



def detect_intent_and_extract_gpt(user_input):
    """
    Use GPT-4o to classify intent and extract file search keyword(s) in strict JSON.
    """
    system_prompt = (
        "You're an AI assistant for a document assistant application. Your job is to classify user input as either a file search or a general response.\n\n"
        "Reply strictly in JSON format only, like:\n"
        "{\"intent\": \"file_search\", \"data\": \"maternity\"}\n"
        "OR\n"
        "{\"intent\": \"general_response\", \"data\": \"\"}\n\n"
        "Rules:\n"
        "- Use intent 'file_search' if user is trying to get, share, show, download, send, or find a document, info, policy, file, report, or manual.\n"
        "- If the input includes file-related terms like 'file', 'document', or 'report', assume it's a file search — even if the topic sounds HR-related like 'leave policy'.\n"
        "- Extract the clean keyword(s) related to the file — remove filler like: file, document, report, info, etc.\n"
        "- Do not invent keywords. If unclear, return intent as 'general_response'.\n"
        "- Use lowercase unless proper name (e.g., 'Anup').\n"
        "- NEVER return anything except the strict JSON format.\n\n"
        f"User input:\n{user_input}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    except Exception as e:
        print("❌ GPT error during intent detection:", e)
        return {"intent": "general_response", "data": ""}


def answer_general_query(user_input):
    """
    Handles general queries. Attempts basic doc-related answer first.
    Falls back to broader ChatGPT-style answer if appropriate.
    """
    try:
        # If it's a greeting or small talk, use doc-assistant tone
        low_context_phrases = ["hi", "hello", "thank you", "who are you", "what can you do"]

        if any(p in user_input.lower() for p in low_context_phrases):
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": (
                        "You are a polite and helpful assistant inside a document assistant chatbot. "
                        "Respond to greetings and user messages in a friendly, short way."
                    )},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.5
            )
            return response.choices[0].message.content.strip()

        # ✅ Otherwise, try answering broadly like ChatGPT
        return answer_with_chatgpt_style(user_input)

    except Exception as e:
        print("❌ GPT error during general query:", e)
        return "⚠️ I'm having trouble responding. Please try again shortly."

def answer_with_chatgpt_style(user_input):
    """
    Uses GPT-4o with a broad, open-ended ChatGPT-style system prompt.
    Allows answering general world questions, news-style questions, etc.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are ChatGPT, an intelligent assistant that can answer general world knowledge, "
                        "recent events, news-style questions, and everyday queries. "
                        "Even if some events are recent, do your best to provide an informed response."
                    )
                },
                {"role": "user", "content": user_input}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ Error in ChatGPT-style fallback:", e)
        return "⚠️ I'm having trouble providing that answer right now."