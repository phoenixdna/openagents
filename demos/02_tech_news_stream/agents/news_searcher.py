import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from openagents.agents.worker_agent import WorkerAgent
from tools.news_fetcher import search_hackernews


class NewsSearcherAgent(WorkerAgent):
    default_agent_id = "news-searcher"
    default_channel = "user_questions"

    async def on_channel_post(self, context):
        await self._handle_user_question(context)

    async def on_channel_mention(self, context):
        await self._handle_user_question(context)

    async def _handle_user_question(self, context):
        if getattr(context, "channel", None) != self.default_channel:
            return

        question_text = (getattr(context, "text", "") or "").strip()
        if not question_text:
            return

        count = self._extract_count(question_text) or 5
        query = self._extract_query(question_text)
        if not query:
            return

        results_text = search_hackernews(query=query, count=count)

        original_event_id = None
        incoming_payload = getattr(getattr(context, "incoming_event", None), "payload", None)
        if isinstance(incoming_payload, dict):
            original_event_id = incoming_payload.get("original_event_id")

        message = (
            "[HN_SEARCH_RESULTS]\n"
            f"Question: {question_text}\n"
            f"Requested: {count} result(s)\n\n"
            f"{results_text}\n"
            "Next: @analyzer please summarize and answer the user question."
        )

        if original_event_id:
            await self.reply_to_message(
                channel=self.default_channel, message_id=original_event_id, text=message
            )
        else:
            await self.post_to_channel(channel=self.default_channel, text=message)

    def _extract_count(self, text: str) -> int | None:
        match = re.search(r"(?:top|TOP|Top)\s*(\d{1,2})", text)
        if match:
            value = int(match.group(1))
            return min(max(1, value), 10)
        match = re.search(r"\b(\d{1,2})\b", text)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 10:
                return value
        return None

    def _extract_query(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^@\S+\s*", "", cleaned)
        cleaned = re.sub(r"(?:top|TOP|Top)\s*\d{1,2}", "", cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="News Searcher Agent")
    parser.add_argument("--host", default="localhost", help="Network host")
    parser.add_argument("--port", type=int, default=8700, help="Network port")
    args = parser.parse_args()

    agent = NewsSearcherAgent(mod_names=["openagents.mods.workspace.messaging"])
    try:
        await agent.async_start(network_host=args.host, network_port=args.port)
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        await agent.async_stop()


if __name__ == "__main__":
    asyncio.run(main())
