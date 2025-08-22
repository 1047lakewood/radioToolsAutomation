import textwrap
from datetime import datetime

from lecture_detector import LectureDetector


def _write_xml(tmp_path, start_time, duration):
    content = textwrap.dedent(f"""
    <ROOT>
        <TRACK ARTIST="A">
            <DURATION>00:05</DURATION>
        </TRACK>
        <NEXTTRACK>
            <TRACK ARTIST="B" STARTTIME="{start_time}">
                <DURATION>{duration}</DURATION>
            </TRACK>
        </NEXTTRACK>
    </ROOT>
    """)
    xml_file = tmp_path / "np.xml"
    xml_file.write_text(content)
    return xml_file


def test_next_lecture_within_hour_true(tmp_path):
    xml_file = _write_xml(tmp_path, "14:10:00", "20:00")
    detector = LectureDetector(str(xml_file))
    now = datetime(2024, 1, 1, 14, 0, 0)
    assert detector.next_lecture_starts_within_hour(now) is True


def test_next_lecture_within_hour_false(tmp_path):
    xml_file = _write_xml(tmp_path, "14:40:00", "30:00")
    detector = LectureDetector(str(xml_file))
    now = datetime(2024, 1, 1, 14, 0, 0)
    assert detector.next_lecture_starts_within_hour(now) is False
