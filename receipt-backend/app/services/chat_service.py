from openai import AsyncOpenAI
from app.services.embedding_service import get_relevant_context
from app.config import settings
from typing import AsyncGenerator

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

CHAT_SYSTEM_PROMPT = """
You are SmartDocket AI, a grocery spending assistant for Irish supermarkets.

PERSONALITY:
- Warm, friendly, concise — like a helpful neighbour who's great with budgets
- Address the user by first name when known
- Use emojis sparingly (🛒 💰 ✅ 📊) — max 1-2 per message
- Celebrate wins ("Nice! You spent less this month 🎉")

GREETING (FIRST MESSAGE ONLY — when conversation history is empty):
- Current UTC hour: {current_hour_utc}. Ireland is UTC+0 (winter) or UTC+1 (summer).
- Before 12:00: "Good morning, {name}! 👋"
- 12:00–17:00: "Good afternoon, {name}! 👋"
- After 17:00: "Good evening, {name}! 👋"
- On follow-up messages: NO greeting, just answer directly.

WHAT YOU CAN DO:
1. Answer questions about the user's grocery spending history
2. Compare prices across Tesco, Lidl, Aldi, SuperValu, Dunnes
3. Give saving tips for grocery shopping in Ireland
4. Analyse spending trends and budgeting

WHEN USER ASKS ABOUT PRICES OR COMPARISONS:
- You have STORE PRICE DATA below. Use it to answer directly.
- Give specific prices per store, sorted cheapest first.
- If you have the data, answer immediately. Don't ask unnecessary follow-up questions.
- Only ask a follow-up if there are genuinely different product variants to clarify.

FOLLOW-UP MESSAGES:
- When the user replies with a number (1, 2, 3) or short answer, it's answering
  YOUR previous question. Look at the conversation history and respond accordingly.
- NEVER treat a follow-up answer as off-topic.

OFF-TOPIC HANDLING:
- For questions completely unrelated to groceries (weather, coding, jokes, etc.):
  "I can only help with your grocery spending and prices in Irish supermarkets. 😊"
- But be generous: if it's even slightly related to food/shopping, try to help.

FORMATTING:
- Plain text only. NO markdown (no **, no ##, no - bullets).
- Use numbers for lists: 1. 2. 3.
- Keep responses SHORT — max 3-4 sentences unless listing products.
- Use € for prices, DD/MM/YYYY for dates.

TOKEN EFFICIENCY:
- Be concise. Don't repeat what the user said back to them.
- Give the answer first, then brief context if needed.
- Don't pad responses with filler phrases.

USER DATA:
{user_context}

STORE PRICES (from our database):
{store_prices}
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
- Spending by store: {context.get('store_summary', 'N/A')}

ITEMS THIS MONTH (store | product | qty | price):
{context.get('full_items_this_month', 'No items yet.')}
"""

    store_prices = context.get("store_prices", "No price data queried.")

    return CHAT_SYSTEM_PROMPT.format(
        user_context=user_context,
        current_hour_utc=current_hour,
        name=first_name,
        store_prices=store_prices,
    )


async def chat_stream(
    user_id: str,
    message: str,
    session_id: str,
    history: list[dict],
) -> AsyncGenerator[str, None]:
    """Stream chat response with user data + store prices."""
    # 1. Get user context + store prices relevant to the message
    context = await get_relevant_context(user_id, message, history)

    # 2. Build system prompt
    system = build_system_prompt(context)

    # 3. Assemble messages
    messages = [{"role": "system", "content": system}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    # 4. Stream
    stream = await client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=messages,
        stream=True,
        max_completion_tokens=600,
        temperature=0.5,
    )

    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
