import textwrap
from datetime import datetime

from lecture_detector import LectureDetector


def _write_xml(tmp_path, started, cur_dur, next_dur):
    content = textwrap.dedent(
        f"""
        <PLAYER>
            <TRACK ARTIST="A" STARTED="{started}" DURATION="{cur_dur}" />
            <NEXTTRACK>
                <TRACK ARTIST="B" DURATION="{next_dur}" />
            </NEXTTRACK>
        </PLAYER>
        """
    )
    xml_file = tmp_path / "np.xml"
    xml_file.write_text(content)
    return xml_file


def test_next_lecture_within_hour_true(tmp_path):
    xml_file = _write_xml(
        tmp_path, "2024-01-01 14:00:00", "00:10:00", "00:20:00"
    )
    detector = LectureDetector(str(xml_file))
    now = datetime(2024, 1, 1, 14, 0, 0)
    assert detector.next_lecture_starts_within_hour(now) is True


def test_next_lecture_within_hour_false(tmp_path):
    xml_file = _write_xml(
        tmp_path, "2024-01-01 14:00:00", "00:40:00", "00:30:00"
    )
    detector = LectureDetector(str(xml_file))
    now = datetime(2024, 1, 1, 14, 0, 0)
    assert detector.next_lecture_starts_within_hour(now) is False
