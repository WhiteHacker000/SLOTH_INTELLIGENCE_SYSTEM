from app.processing.text import clean_markdown, split_into_chunks


def test_removes_template_comments_and_images() -> None:
    text = "<!-- Describe your change -->\nFixes the bug.\n![badge](x.svg)"

    assert clean_markdown(text) == "Fixes the bug."


def test_code_blocks_are_left_untouched() -> None:
    code = "```python\n<!-- not a comment -->\n\n\n\nx = 1\n```"

    assert clean_markdown(f"Example:\n\n{code}") == f"Example:\n\n{code}"


def test_collapses_extra_blank_lines() -> None:
    assert clean_markdown("one\n\n\n\n\ntwo") == "one\n\ntwo"


def test_short_text_stays_in_one_chunk() -> None:
    assert split_into_chunks("first\n\nsecond") == ["first\n\nsecond"]


def test_paragraphs_are_grouped_under_the_limit() -> None:
    paragraphs = ["a" * 40, "b" * 40, "c" * 40]

    chunks = split_into_chunks("\n\n".join(paragraphs), max_chars=90, overlap=10)

    assert chunks == [f"{'a' * 40}\n\n{'b' * 40}", "c" * 40]


def test_long_paragraph_is_cut_with_overlap() -> None:
    text = "".join(str(i % 10) for i in range(250))

    chunks = split_into_chunks(text, max_chars=100, overlap=20)

    assert [len(chunk) for chunk in chunks] == [100, 100, 90]
    assert chunks[0][-20:] == chunks[1][:20]
    assert chunks[-1].endswith(text[-10:])


def test_code_block_is_not_split_on_blank_lines() -> None:
    code = "```\nline one\n\nline two\n```"

    assert split_into_chunks(code) == [code]
