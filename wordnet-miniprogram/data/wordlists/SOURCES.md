# Word list sources

The extra word lists are snapshots from the New General Service List Project and
are redistributed under **Creative Commons Attribution-ShareAlike 4.0
International (CC BY-SA 4.0)**. The full license text is in
`LICENSE-CC-BY-SA-4.0.txt`.

| Book | Source | Version | Authors | URL |
| --- | --- | --- | --- | --- |
| Academic English | New Academic Word List (NAWL) | 1.2 | Browne, Culligan & Phillips | https://www.newgeneralservicelist.com/new-academic-word-list |
| TOEIC English | TOEIC Service List (TSL) | 1.2 | Browne & Culligan | https://www.newgeneralservicelist.com/toeic-service-list |
| Business English | Business Service List (BSL) | 1.2 | Browne & Culligan | https://www.newgeneralservicelist.com/business-service-list |
| Spoken English | NGSL-Spoken | 1.2 | New General Service List Project | https://www.newgeneralservicelist.com/ngsl-spoken |
| Children's English | New Dolch List | 1.1 | New General Service List Project | https://www.newgeneralservicelist.com/new-dolch-list |

The existing General English book uses NGSL 1.2:

- Browne, C., Culligan, B., & Phillips, J. (2013). *New General Service List*.
  https://www.newgeneralservicelist.com/new-general-service-list

## Changes made in this project

- Normalized lemmas to lowercase ASCII for WordNet matching.
- Removed duplicate lemmas and words without a matching WordNet sense.
- Re-ranked the matched words sequentially for unit generation.
- Joined WordNet 3.0 definitions, examples, synonyms, antonyms and derivatives.
- Licensed the derived catalog under CC BY-SA 4.0 as required by the source
  licenses.

WordNet 3.0 is © Princeton University and is used under the WordNet 3.0 license:
https://wordnet.princeton.edu/license-and-commercial-use

## Exam word lists

| Book | Source | License | URL |
| --- | --- | --- | --- |
| CET-4 | KyleBing/english-vocabulary | BSD-3-Clause | https://github.com/KyleBing/english-vocabulary |
| CET-6 | KyleBing/english-vocabulary | BSD-3-Clause | https://github.com/KyleBing/english-vocabulary |
| Postgraduate (考研) | KyleBing/english-vocabulary | BSD-3-Clause | https://github.com/KyleBing/english-vocabulary |
| TOEFL | KyleBing/english-vocabulary | BSD-3-Clause | https://github.com/KyleBing/english-vocabulary |
| IELTS | hefengxian/ielts-vocabulary | MIT | https://github.com/hefengxian/ielts-vocabulary |

Only the headwords and their order are retained in `exam_*.csv`. The upstream
translations/examples are not copied. Run `python scripts/fetch_exam_wordlists.py`
to refresh the compact snapshots. License texts are stored next to the CSVs:

- `LICENSE-CC-BY-SA-4.0.txt`
- `LICENSE-KyleBing-BSD-3-Clause.txt`
- `LICENSE-hefengxian-MIT.txt`

## Collocations (词组搭配)

`phrases.json` contains up to four collocations per headword extracted from the
`phrases` field of KyleBing/english-vocabulary (BSD-3-Clause). Only the English
phrase and its Chinese translation are kept. The upstream project states that
the data is for learning purposes; see
https://github.com/KyleBing/english-vocabulary for details.

The runtime package keeps up to six phrases per word and is built with
`python scripts/build_content_package.py`.

## Word roots (词根)

`morphemes.csv` and `decode.csv` are snapshots from
[jupsh/anki-word-roots](https://github.com/jupsh/anki-word-roots), licensed under
**CC BY-SA 4.0**. The morpheme data is adapted from Wikipedia's
*List of Greek and Latin roots in English* by Wikipedia contributors, also
CC BY-SA 4.0; the upstream `LICENSE.md` lists the exact revisions.

`scripts/roots_data.py` combines those snapshots with a curated list of common
learnable prefixes, suffixes and roots, then `scripts/prepare_data.py` embeds
matches in the main catalog. The same roots are also included in the shared
content package built by `python scripts/build_content_package.py`.

The derived phrases/roots data is distributed under CC BY-SA 4.0.


