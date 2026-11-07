from ledgerly_shared.stock_available import available_stock


def test_reserved_units_are_taken_off():
    assert available_stock(10, 3) == 7


def test_never_below_zero():
    assert available_stock(2, 5) == 0
