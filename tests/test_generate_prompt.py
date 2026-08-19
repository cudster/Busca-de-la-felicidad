import generate_content as gc


def test_build_user_prompt_includes_fact_and_news():
    skeleton = [
        {"id": "P01", "date": "2026-09-01", "type": "image", "pillar": "technical_awe",
         "cta": "none", "source_kind": "fact", "source_text": "titanium from USSR", "source_detail": "detail"},
        {"id": "P02", "date": "2026-09-02", "type": "reel", "pillar": "spotting",
         "cta": "none", "source_kind": "news", "source_text": "777X milestone", "source_detail": "test target"},
    ]
    prompt = gc.build_user_prompt(skeleton, "September 2026")
    assert "titanium from USSR" in prompt
    assert "777X milestone" in prompt
    assert "React" in prompt  # la nota de reacción para el post de noticia
