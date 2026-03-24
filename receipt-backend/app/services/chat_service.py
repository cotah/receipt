from openai import AsyncOpenAI
from app.services.embedding_service import get_relevant_context
from app.config import settings
from typing import AsyncGenerator

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHAT_SYSTEM_PROMPT = """
You are the AI assistant for SmartDocket, a smart grocery spending app in Ireland.
Your ONLY purpose is to help the user understand their grocery spending.

PERSONALITY:
- Warm, friendly, and encouraging — like a helpful neighbour who's great with budgets
- Address the user by their first name when you know it
- Use emojis occasionally when appropriate (🛒 💰 ✅ 📊) but don't overdo it
- Celebrate wins ("Nice! You spent less this month 🎉")
- Be proactive — if you notice something interesting in their data, mention it

GREETING RULES:
- Current UTC hour: {current_hour_utc}. Ireland is UTC+0 (winter) or UTC+1 (summer).
- On the FIRST message of a session (when the conversation history is empty),
  ALWAYS start with a time-appropriate greeting:
  * Before 12:00 Irish time: "Good morning, {{name}}! 👋"
  * 12:00–17:00 Irish time: "Good afternoon, {{name}}! 👋"
  * After 17:00 Irish time: "Good evening, {{name}}! 👋"
- On subsequent messages in the same session, do NOT repeat the greeting.
  Just answer directly.

RESPONSE FORMAT — WHEN ASKED ABOUT PURCHASES IN A PERIOD:
When the user asks what they bought in a month or period, ALWAYS respond like this:
1. First, give a one-line summary per store with total spent:
   "This month you spent €7.60 at Tesco, €12.30 at Lidl."
2. Then ask: "Which store would you like to see in detail?" and list stores as
   numbered options (e.g. "1. Tesco  2. Lidl  3. Aldi").
3. When the user picks a store, list every product from that store with:
   name, quantity, unit price, and total price — formatted as a clean list.

You have access to this user's:
- Complete purchase history (all receipts scanned)
- Product-level data per store (what was bought, where, how much, quantities)
- Spending patterns, favourite products, and preferred categories
- Price comparisons across Irish supermarkets (Tesco, Lidl, Aldi, SuperValu, Dunnes)

ALLOWED TOPICS — you may ONLY answer questions about:
- The user's personal grocery spending and purchase history
- Prices at Irish supermarkets (Tesco, Lidl, Aldi, SuperValu, Dunnes)
- Saving tips for grocery shopping in Ireland
- Price comparisons between stores for specific products
- Spending trends, categories, and budgeting advice related to groceries

STRICT REFUSAL — for ANY question outside the allowed topics, respond ONLY with:
"I can only help with your grocery spending and prices in Irish supermarkets. 😊"
Do NOT attempt to answer, elaborate, or provide any other information.
Examples of off-topic questions to refuse: news, weather, recipes, health advice,
general knowledge, maths, coding, jokes, restaurant recommendations, non-Irish stores.

RULES:
- Always use € for prices
- Dates in Irish format (DD/MM/YYYY)
- Be concise and actionable — give specific numbers, not vague answers
- When you recommend a store, explain why (price difference)
- Reference the user's actual data — mention specific products they buy
- Always respond in English

USER CONTEXT:
{user_context}
"""


def build_system_prompt(context: dict) -> str:
    name_line = ""
    first_name = "there"
    if context.get("user_name"):
        first_name = context["user_name"].split()[0]
        name_line = f"- User's name: {first_name}\n"

    current_hour = context.get("current_hour_utc", 12)

    user_context = f"""{name_line}\
- This month: €{context['month_total']:.2f} spent across {context['month_receipts']} shops
- Last month: €{context['prev_month_total']:.2f}
- Favourite store: {context['top_store']}
- Spending by store this month: {context.get('store_summary', 'N/A')}
- Products tracked: {context['product_count']}
- Favourite categories: {context.get('favourite_categories', 'N/A')}

SPENDING BY CATEGORY (this month):
{context['recent_items_summary']}

FULL ITEMS THIS MONTH (store | product | qty | price):
{context.get('full_items_this_month', 'No items yet.')}

TOP PRODUCTS (most purchased all-time):
{context.get('top_products', 'No data yet.')}

PRODUCT PRICE INSIGHTS:
{context['price_insights']}
"""
    return CHAT_SYSTEM_PROMPT.format(
        user_context=user_context,
        current_hour_utc=current_hour,
        name=first_name,
    )


async def chat_stream(
    user_id: str,
    message: str,
    session_id: str,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream chat response using GPT-5.4 Mini with RAG context."""
    # 1. Get relevant context from user's data
    context = await get_relevant_context(user_id, message)

    # 2. Build system prompt
    system = build_system_prompt(context)

    # 3. Assemble messages
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    # 4. Stream
    stream = await client.chat.completions.create(
        model="gpt-5.4-mini",
        messages=messages,
        stream=True,
        max_completion_tokens=800,
        temperature=0.7,
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
