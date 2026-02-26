import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
from bot.bot import main

if __name__ == '__main__':
    asyncio.run(main())