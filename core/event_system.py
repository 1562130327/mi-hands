"""事件系统"""

from typing import Dict, List, Callable, Any
import asyncio


class EventBus:
    """事件总线"""

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def register(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unregister(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    async def emit(self, event_type: str, data: Any = None):
        """触发事件"""
        if event_type in self._handlers:
            tasks = [handler(data) for handler in self._handlers[event_type]]
            await asyncio.gather(*tasks)
