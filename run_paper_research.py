# run_paper_research.py
import asyncio

from metagpt.config2 import config
from metagpt.context import Context
from metagpt.roles.paper_researcher import PaperResearcher


async def main():
    researcher = PaperResearcher()
    researcher.set_context(Context(config=config))

    report = await researcher.run(topic="机器学习", save_report=True)

    print("\n=== Report ===")
    print(f"Topic: {report.topic}")
    print(f"Papers found: {len(report.papers)}")
    print(f"Research path: {researcher.get_research_path()}")
    print(f"Suggestions: {report.suggestions}")


asyncio.run(main())
