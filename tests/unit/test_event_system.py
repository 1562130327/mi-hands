"""事件系统测试"""

import pytest
import asyncio
from core.event_system import EventBus


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.mark.asyncio
async def test_register_and_emit(event_bus):
    """测试注册事件和触发事件"""
    received = []

    async def handler(data):
        received.append(data)

    event_bus.register("test_event", handler)
    await event_bus.emit("test_event", {"key": "value"})

    assert len(received) == 1
    assert received[0] == {"key": "value"}


@pytest.mark.asyncio
async def test_multiple_handlers(event_bus):
    """测试多个处理器"""
    received1 = []
    received2 = []

    async def handler1(data):
        received1.append(data)

    async def handler2(data):
        received2.append(data)

    event_bus.register("test_event", handler1)
    event_bus.register("test_event", handler2)
    await event_bus.emit("test_event", {"key": "value"})

    assert len(received1) == 1
    assert len(received2) == 1


@pytest.mark.asyncio
async def test_no_handlers(event_bus):
    """测试没有处理器的情况"""
    await event_bus.emit("test_event", {"key": "value"})  # 不应该报错
