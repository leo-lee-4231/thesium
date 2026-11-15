from app.application.conversation_service import read_only_guard_triggered


def test_guard_catches_claimed_writes() -> None:
    assert read_only_guard_triggered("已帮你把 Thesis 改成看多。")
    assert read_only_guard_triggered("我已经下单买入 0.1 BTC。")
    assert read_only_guard_triggered("我为你记录了这笔成交。")


def test_guard_allows_read_only_language() -> None:
    assert not read_only_guard_triggered("我不能修改 Thesis；请在编辑器中确认。")
    assert not read_only_guard_triggered("建议你重新审视 70,000 的失效条件。")
    assert not read_only_guard_triggered("这条 Decision 已经记录在时间线里。")
