from agents.deadline import Deadline


class FakeClock:
    def __init__(self, now: float = 100.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_left_shrinks_and_goes_negative_after_the_deadline():
    clock = FakeClock()
    deadline = Deadline.after(10, clock)
    assert deadline.left() == 10
    clock.now += 4
    assert deadline.left() == 6
    clock.now += 10
    assert deadline.left() == -4


def test_should_skip_is_false_with_plenty_of_time_and_true_below_threshold():
    clock = FakeClock()
    deadline = Deadline.after(60, clock)
    assert deadline.should_skip(30) is False
    clock.now += 31
    assert deadline.should_skip(30) is True


def test_should_skip_is_false_when_exactly_at_threshold():
    clock = FakeClock()
    deadline = Deadline.after(30, clock)
    assert deadline.should_skip(30) is False


def test_after_uses_the_clock_it_is_given():
    clock = FakeClock(now=500.0)
    deadline = Deadline.after(20, clock)
    assert deadline.at == 520.0
    assert deadline.clock is clock


def test_default_clock_is_monotonic():
    deadline = Deadline.after(60)
    assert 0 < deadline.left() <= 60
