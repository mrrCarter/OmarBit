"""Dev server entrypoint — sets the correct event loop policy on Windows before uvicorn starts."""
import asyncio
import platform
import sys

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
