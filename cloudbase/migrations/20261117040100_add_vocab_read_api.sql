CREATE FUNCTION public.wordnet_vocab_health() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$ SELECT jsonb_build_object('database', 'postgresql', 'api_version', 1) $$;

CREATE FUNCTION public.wordnet_vocab_books() RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
    SELECT coalesce(jsonb_agg(jsonb_build_object(
        'book_id', book_id, 'title', title, 'content_version', content_version
    ) ORDER BY book_id), '[]'::jsonb)
    FROM vocab.wordbooks WHERE enabled
$$;

CREATE FUNCTION public.wordnet_vocab_word(p_lemma text) RETURNS jsonb
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = ''
AS $$
    SELECT jsonb_build_object(
        'word_id', w.word_id, 'lemma', w.lemma, 'content_version', w.content_version,
        'senses', jsonb_agg(jsonb_build_object(
            'sense_id', s.sense_id, 'pos', s.pos, 'definition_en', s.definition_en,
            'examples_en', s.examples_en, 'is_primary', s.is_primary,
            'display_order', s.display_order, 'source', s.source
        ) ORDER BY s.display_order)
    )
    FROM vocab.words w
    JOIN vocab.word_senses s ON s.word_id = w.word_id AND s.review_status = 'approved'
    WHERE w.lemma = p_lemma AND EXISTS (
        SELECT 1 FROM vocab.wordbook_items i JOIN vocab.wordbooks b USING (book_id)
        WHERE i.word_id = w.word_id AND b.enabled
    )
    GROUP BY w.word_id
$$;

REVOKE ALL ON FUNCTION public.wordnet_vocab_health(), public.wordnet_vocab_books(),
    public.wordnet_vocab_word(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.wordnet_vocab_health(), public.wordnet_vocab_books(),
    public.wordnet_vocab_word(text) TO service_role;
