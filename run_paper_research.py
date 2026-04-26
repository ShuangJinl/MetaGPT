# run_paper_research.py
import asyncio
from metagpt.roles.paper_researcher import PaperResearcher, ResearchConfig
from metagpt.context import Context
from metagpt.config2 import config

async def main():
    researcher = PaperResearcher()
    researcher.set_context(Context(config=config))
    
    report = await researcher.run(
        topic="机器学习",
        save_report=True
    )
    
    print(f"\n=== Report ===")
    print(f"Topic: {report.topic}")
    print(f"Papers found: {len(report.papers)}")
    print(f"Research path: {researcher.get_research_path()}")
    print(f"Suggestions: {report.suggestions}")

asyncio.run(main())