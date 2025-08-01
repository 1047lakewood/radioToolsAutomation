import utils

def test_parse_time_string_range():
    result = utils.parse_time_string('13-16, 18')
    assert result == [
        {'hour': 13},
        {'hour': 14},
        {'hour': 15},
        {'hour': 16},
        {'hour': 18},
    ]

def test_parse_time_string_invalid():
    result = utils.parse_time_string('25, -1, a, 5-3')
    # Should ignore invalid entries and return empty list except valid numbers
    assert result == []

